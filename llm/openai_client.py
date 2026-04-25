"""OpenAI LLM integration — intent extraction, response generation, and validation.

The LLM handles understanding and communication:
  1. Multi-turn intent extraction (with pivot detection)
  2. Contextual clarification questions
  3. Product-specific recommendation reasoning
  4. Basket-aware, context-aware response generation
  5. Natural upsell phrasing

All product decisions remain in the deterministic engine.
Every LLM output is validated before use — hallucinations get caught and fall back to
deterministic text.
"""

from __future__ import annotations

import json
import logging
import os

from openai import OpenAI

logger = logging.getLogger(__name__)

MAX_TURNS = 4

# ---------------------------------------------------------------------------
# Allowed value sets (used for validation)
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

RESPONSE_GENERATION_SYSTEM = """You are a friendly shop assistant. Keep responses concise (2-4 sentences).

Rules:
- Recommend ONLY from the products listed below. NEVER invent, guess, or name products not in the list.
- Explain WHY each product fits the customer's specific request — reference what they actually said.
- Be warm and conversational, not robotic or pushy.
- If the customer has items in their basket, be aware of them. Don't re-recommend basket items.
- If there's an upsell item listed, mention it naturally with social proof ("Most people also grab a...").
- If this is a follow-up, acknowledge the context ("Since you wanted something cheaper..." etc).
- Do not use markdown formatting. Plain text only.
- Do not mention internal scores, rankings, or algorithms."""

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
# Prompt builders
# ---------------------------------------------------------------------------

def _build_intent_messages(
    text: str,
    history: list[dict] | None = None,
    previous_intent: dict | None = None,
) -> list[dict]:
    """Build message list for intent extraction, including conversation context."""
    messages = [{"role": "system", "content": INTENT_EXTRACTION_SYSTEM}]

    if history:
        # Include last few turns as context (keep it short)
        for msg in history[-6:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

    user_content = text
    if previous_intent:
        user_content += f"\n\n[Previous intent was: {json.dumps(previous_intent)}]"

    messages.append({"role": "user", "content": user_content})
    return messages


def _build_response_user_prompt(
    user_message: str,
    products: list[dict],
    upsell: dict | None = None,
    basket: list[dict] | None = None,
    history: list[dict] | None = None,
) -> str:
    product_lines = []
    for i, p in enumerate(products, 1):
        tags = ", ".join(p.get("tags", [])[:3])
        dietary = ", ".join(p.get("dietary", [])) if p.get("dietary") else ""
        detail = f"{tags}"
        if dietary:
            detail += f", {dietary}"
        product_lines.append(
            f"{i}. {p['name']} — £{p['price']:.2f} ({detail})"
        )

    prompt = f'Customer said: "{user_message}"'

    if history:
        recent = history[-4:]
        convo_lines = [f"  {m['role'].title()}: {m['content'][:120]}" for m in recent]
        prompt += f"\n\nConversation context:\n" + "\n".join(convo_lines)

    prompt += f"""

Recommended products (ONLY mention these by name):
{chr(10).join(product_lines)}"""

    if basket:
        basket_names = [item["name"] for item in basket]
        prompt += f"\n\nAlready in basket: {', '.join(basket_names)}"

    if upsell:
        prompt += f"""

Upsell suggestion (mention naturally if appropriate):
- {upsell['name']} — £{upsell['price']:.2f}"""

    return prompt


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


def generate_response_llm(
    user_message: str,
    products: list[dict],
    upsell: dict | None = None,
    basket: list[dict] | None = None,
    history: list[dict] | None = None,
) -> str | None:
    """Generate a natural recommendation response with product reasoning.

    Includes basket awareness, upsell phrasing, and conversation context.
    Returns validated response string on success, None on failure.
    """
    user_prompt = _build_response_user_prompt(
        user_message, products, upsell, basket, history
    )

    messages = [
        {"role": "system", "content": RESPONSE_GENERATION_SYSTEM},
        {"role": "user", "content": user_prompt},
    ]

    raw = _call_llm(messages, temperature=0.7, max_tokens=300)
    product_names = [p["name"] for p in products]
    return validate_response_text(raw, product_names)
