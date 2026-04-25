"""OpenAI LLM integration — product-aware recommendation with validation.

The LLM receives the full product catalog for the selected store and reasons
about which products best match the customer's request. It handles:
  1. Browsing the product dataset to find relevant items
  2. Multi-turn conversation with refinement and pivot detection
  3. Contextual clarification when requests are vague
  4. Product-specific reasoning (dietary, price, taste, portion)
  5. Basket-aware suggestions (avoids re-recommending basket items)
  6. Natural upsell phrasing based on curated product pairs

Validation layer ensures every product ID the LLM returns exists in the real
catalog. Hallucinated products are stripped. Falls back to deterministic engine
if the LLM is unavailable or returns invalid output.
"""

from __future__ import annotations

import json
import logging
import os

from openai import OpenAI

logger = logging.getLogger(__name__)

MAX_TURNS = 4

# ---------------------------------------------------------------------------
# Allowed value sets (used for intent validation)
# ---------------------------------------------------------------------------

VALID_CATEGORIES = {"lunch", "breakfast", "snack", "drink", "unknown"}
VALID_PREFERENCES = {"light", "healthy", "sweet", "filling", "indulgent"}
VALID_MODIFIERS = {"quick", "budget", "premium"}
VALID_DIETARY = {"vegan", "vegetarian", "halal", "gluten_free", "dairy_free"}
VALID_BEHAVIOURS = {"rushed", "budget", "exploring", "health_focused"}

# ---------------------------------------------------------------------------
# Client setup
# ---------------------------------------------------------------------------

_client: OpenAI | None = None


def _get_client() -> OpenAI | None:
    global _client
    if _client is not None:
        return _client
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY not set — LLM features disabled, using deterministic fallback")
        return None
    _client = OpenAI(api_key=api_key)
    return _client


def _get_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def is_llm_available() -> bool:
    return _get_client() is not None


# ---------------------------------------------------------------------------
# Prompts (kept as constants for transparency / display in UI)
# ---------------------------------------------------------------------------

RECOMMEND_SYSTEM = """You are an AI shopping assistant for a food & drink shop.
You will receive the full product catalog for this store. Your job is to:
1. Understand what the customer wants from their message (and conversation history if present)
2. Browse the product catalog and pick the BEST matching products
3. Explain your reasoning — why each product fits what the customer asked for

Return ONLY valid JSON, no markdown, no explanation outside the JSON. Schema:
{
  "recommended_ids": ["id1", "id2"],  // 1-3 product IDs from the catalog
  "reasoning": "...",                  // 1-2 sentences: why you picked these
  "message": "...",                    // 2-4 sentences: friendly response to the customer
  "needs_clarification": false,        // true if the request is too vague to recommend
  "clarification_question": null       // if needs_clarification is true, ask ONE short question
}

Product selection rules:
- Pick 1-3 products. If the customer seems rushed, pick 1. If exploring, pick up to 3.
- ONLY use product IDs that appear in the catalog below. NEVER invent products.
- Match on: category, tags, dietary needs, taste, price, portion size, prep time.
- If the customer has items in their basket, do NOT recommend those again.
- If you find a relevant upsell_pair on a recommended product, mention it naturally in your message
  using social proof (e.g. "Most people also grab a..."). Only suggest upsells from the catalog.

Message rules:
- Be warm and conversational, not robotic.
- Reference what the customer actually said — show you understood.
- Mention specific product details (price, dietary info, taste) that are relevant to their request.
- If this is a follow-up, acknowledge the context ("Since you wanted something lighter...").
- Do not use markdown formatting. Plain text only.
- Do not mention scores, algorithms, or internal data.

Multi-turn rules:
- If the customer REFINES ("something cheaper", "make it vegan"), adjust your picks accordingly.
- If the customer PIVOTS ("forget that, I want a drink"), start fresh — pick from the new category.
- Consider conversation history to understand context.

Clarification rules:
- Only set needs_clarification=true if the request is genuinely too vague (e.g. "food", "anything").
- If you can make reasonable product picks, do so — don't over-clarify.
- Keep clarification questions casual and short (1 sentence)."""

INTENT_EXTRACTION_SYSTEM = """You are an intent classifier for a food & drink shop assistant.

Given a customer message (and optionally conversation history), extract structured intent as JSON.
Return ONLY valid JSON, no markdown, no explanation.

Schema:
{
  "category": "lunch" | "breakfast" | "snack" | "drink" | "unknown",
  "preferences": [],    // from: "light", "healthy", "sweet", "filling", "indulgent"
  "modifiers": [],      // from: "quick", "budget", "premium"
  "dietary": [],        // from: "vegan", "vegetarian", "halal", "gluten_free", "dairy_free"
  "behaviour": "rushed" | "budget" | "exploring" | "health_focused"
}

Multi-turn rules:
- If this is a follow-up, consider the conversation history to understand context.
- If the user REFINES their request ("something cheaper", "make it vegan"), MODIFY the previous intent.
- If the user PIVOTS ("actually forget that, I want a drink"), START FRESH — ignore previous intent.
- If the user asks about a specific product they were shown, keep the intent the same.

General rules:
- If the category is unclear, use "unknown".
- Only use values from the allowed lists above.
- Prefer "unknown" over guessing.
- Return valid JSON only."""

CLARIFICATION_SYSTEM = """You are a friendly shop assistant. The customer's request is vague.
Generate ONE short, natural clarification question (1 sentence max) to help narrow down what they want.

Your question should help determine one of:
- Meal type (breakfast, lunch, snack, or drink)
- Preferences (light, filling, sweet, healthy, indulgent)
- Pace (quick grab or sit-down)

Rules:
- Keep it casual and conversational.
- Do not suggest specific products.
- Do not ask more than one question.
- Do not use markdown. Plain text only."""


# ---------------------------------------------------------------------------
# Product catalog formatting
# ---------------------------------------------------------------------------

def format_product_catalog(products: list[dict]) -> str:
    """Format the product list into a compact text representation for the LLM prompt."""
    lines = []
    for p in products:
        dietary = ", ".join(p.get("dietary", [])) if p.get("dietary") else "none"
        allergens = ", ".join(p.get("allergens", [])) if p.get("allergens") else "none"
        tags = ", ".join(p.get("tags", []))
        taste = ", ".join(p.get("taste_profile", []))
        upsell_ids = [u["product_id"] for u in p.get("upsell_pairs", [])]
        upsell_str = ", ".join(upsell_ids) if upsell_ids else "none"

        lines.append(
            f'- id:{p["id"]} | {p["name"]} | £{p["price"]:.2f} | '
            f'cat:{p["category"]} | tags:[{tags}] | dietary:[{dietary}] | '
            f'allergens:[{allergens}] | taste:[{taste}] | '
            f'size:{p.get("portion_size","?")} | cal:{p.get("calories_band","?")} | '
            f'prep:{p.get("prep_time_minutes","?")}min | upsells:[{upsell_str}]'
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def build_recommend_prompt(
    user_message: str,
    products: list[dict],
    basket: list[dict] | None = None,
    history: list[dict] | None = None,
) -> str:
    """Build the user prompt for the recommendation call, including full product catalog."""
    catalog = format_product_catalog(products)
    prompt = f'Customer said: "{user_message}"'

    if history:
        recent = history[-6:]
        convo_lines = [f"  {m['role'].title()}: {m['content'][:150]}" for m in recent]
        prompt += "\n\nConversation history:\n" + "\n".join(convo_lines)

    prompt += f"\n\n--- PRODUCT CATALOG ({len(products)} items) ---\n{catalog}"

    if basket:
        basket_lines = [f"  - {item['name']} (id:{item['id']})" for item in basket]
        prompt += "\n\n--- ALREADY IN BASKET (do not recommend these) ---\n" + "\n".join(basket_lines)

    return prompt


def _build_intent_messages(
    text: str,
    history: list[dict] | None = None,
    previous_intent: dict | None = None,
) -> list[dict]:
    """Build message list for intent extraction, including conversation context."""
    messages = [{"role": "system", "content": INTENT_EXTRACTION_SYSTEM}]

    if history:
        for msg in history[-6:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

    user_content = text
    if previous_intent:
        user_content += f"\n\n[Previous intent was: {json.dumps(previous_intent)}]"

    messages.append({"role": "user", "content": user_content})
    return messages


# ---------------------------------------------------------------------------
# Validation — catch hallucinations before they reach the user
# ---------------------------------------------------------------------------

def validate_intent(raw: dict) -> dict:
    """Sanitise LLM intent output — strip any values not in allowed sets."""
    validated = {}

    cat = raw.get("category", "unknown")
    validated["category"] = cat if cat in VALID_CATEGORIES else "unknown"

    validated["preferences"] = [
        p for p in raw.get("preferences", []) if p in VALID_PREFERENCES
    ]
    validated["modifiers"] = [
        m for m in raw.get("modifiers", []) if m in VALID_MODIFIERS
    ]
    validated["dietary"] = [
        d for d in raw.get("dietary", []) if d in VALID_DIETARY
    ]

    beh = raw.get("behaviour", "exploring")
    validated["behaviour"] = beh if beh in VALID_BEHAVIOURS else "exploring"

    return validated


def validate_recommendation(raw: dict, valid_ids: set[str]) -> dict | None:
    """Validate LLM recommendation output. Returns sanitised dict or None."""
    if not isinstance(raw, dict):
        logger.warning("LLM recommendation is not a dict")
        return None

    rec_ids = raw.get("recommended_ids", [])
    if not isinstance(rec_ids, list):
        logger.warning("recommended_ids is not a list")
        return None

    # Strip any IDs not in the real catalog
    valid_rec_ids = [pid for pid in rec_ids if pid in valid_ids]
    if not valid_rec_ids:
        logger.warning("LLM recommended zero valid products (raw: %s)", rec_ids)
        return None

    if len(valid_rec_ids) != len(rec_ids):
        stripped = set(rec_ids) - set(valid_rec_ids)
        logger.warning("Stripped hallucinated product IDs: %s", stripped)

    # Validate message
    message = raw.get("message", "")
    if not message or len(message) < 10:
        message = None
    elif len(message) > 800:
        message = message[:800].rsplit(".", 1)[0] + "."

    # Validate clarification
    clarification = None
    if raw.get("needs_clarification"):
        q = raw.get("clarification_question", "")
        if q and 10 <= len(q) <= 200:
            clarification = q if "?" in q else q + "?"

    return {
        "recommended_ids": valid_rec_ids[:3],
        "reasoning": raw.get("reasoning", ""),
        "message": message,
        "needs_clarification": bool(clarification),
        "clarification_question": clarification,
    }


def validate_response_text(
    text: str | None,
    allowed_product_names: list[str],
) -> str | None:
    """Check LLM response for basic sanity. Returns None if invalid (triggers fallback)."""
    if not text:
        return None
    if len(text) > 800:
        logger.warning("LLM response too long (%d chars), truncating", len(text))
        text = text[:800].rsplit(".", 1)[0] + "."
    if len(text) < 10:
        logger.warning("LLM response too short (%d chars), rejecting", len(text))
        return None
    return text


def validate_clarification(text: str | None) -> str | None:
    """Check clarification question for sanity."""
    if not text:
        return None
    text = text.strip().strip('"').strip("'")
    if len(text) > 200 or len(text) < 10:
        return None
    if "?" not in text:
        text += "?"
    return text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_code_fences(raw: str) -> str:
    """Remove markdown code fences from LLM output."""
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()
    return raw


def _call_llm(messages: list[dict], temperature: float = 0.7, max_tokens: int = 300) -> str | None:
    """Make an LLM call with error handling. Returns raw text or None."""
    client = _get_client()
    if client is None:
        return None
    try:
        response = client.chat.completions.create(
            model=_get_model(),
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# LLM calls
# ---------------------------------------------------------------------------

def recommend_from_catalog(
    user_message: str,
    products: list[dict],
    basket: list[dict] | None = None,
    history: list[dict] | None = None,
) -> dict | None:
    """Main LLM call: receives the product catalog, picks products, and explains why.

    Returns validated dict with recommended_ids, message, reasoning, and optional
    clarification — or None on failure (triggers deterministic fallback).
    """
    user_prompt = build_recommend_prompt(user_message, products, basket, history)

    messages = [
        {"role": "system", "content": RECOMMEND_SYSTEM},
        {"role": "user", "content": user_prompt},
    ]

    raw = _call_llm(messages, temperature=0.5, max_tokens=500)
    if raw is None:
        return None

    try:
        raw = _strip_code_fences(raw)
        parsed = json.loads(raw)
        valid_ids = {p["id"] for p in products}
        result = validate_recommendation(parsed, valid_ids)
        if result:
            logger.info("LLM recommended: %s", result["recommended_ids"])
        return result
    except (json.JSONDecodeError, KeyError) as e:
        logger.error("LLM recommendation parsing failed: %s — raw: %s", e, raw[:300])
        return None


def extract_intent_llm(
    text: str,
    history: list[dict] | None = None,
    previous_intent: dict | None = None,
) -> dict | None:
    """Extract structured intent from free text, with multi-turn awareness.

    Returns validated dict on success, None on failure (caller should fall back).
    """
    messages = _build_intent_messages(text, history, previous_intent)
    raw = _call_llm(messages, temperature=0.1, max_tokens=200)
    if raw is None:
        return None

    try:
        raw = _strip_code_fences(raw)
        parsed = json.loads(raw)
        validated = validate_intent(parsed)
        logger.info("LLM intent extraction: %s", validated)
        return validated
    except (json.JSONDecodeError, KeyError) as e:
        logger.error("LLM intent parsing failed: %s — raw: %s", e, raw[:200])
        return None


def generate_clarification_llm(
    user_message: str,
    history: list[dict] | None = None,
) -> str | None:
    """Generate a contextual clarification question for a vague request."""
    messages = [{"role": "system", "content": CLARIFICATION_SYSTEM}]
    if history:
        for msg in history[-4:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    raw = _call_llm(messages, temperature=0.8, max_tokens=80)
    return validate_clarification(raw)
