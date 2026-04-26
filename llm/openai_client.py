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
from pathlib import Path

import yaml
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
# Prompts — loaded from YAML for structure + dynamic shop_type substitution
# ---------------------------------------------------------------------------

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

_recommend_yaml_cache: dict | None = None


def _load_recommend_yaml() -> dict:
    """Load and cache the recommend prompt YAML."""
    global _recommend_yaml_cache
    if _recommend_yaml_cache is not None:
        return _recommend_yaml_cache
    yaml_path = PROMPTS_DIR / "recommend.yaml"
    with open(yaml_path, "r") as f:
        _recommend_yaml_cache = yaml.safe_load(f)
    return _recommend_yaml_cache


def get_recommend_system_prompt(shop_type: str = "shop") -> str:
    """Render the recommend system prompt from YAML, substituting {shop_type}.

    The YAML structure is sent as-is (serialized) because LLMs parse structured
    YAML more reliably than unstructured prose. The shop_type is substituted
    into the role and the matching shop_context is injected.
    """
    prompt_data = _load_recommend_yaml()

    # Map store_type to display name
    shop_names = {
        "cafe": "café",
        "pub": "pub",
        "bakery": "bakery",
        "corner_shop": "corner shop",
    }
    shop_display = shop_names.get(shop_type, shop_type)

    # Substitute {shop_type} in the role
    role = prompt_data["role"].replace("{shop_type}", shop_display)

    # Pick the right shop context
    shop_context = prompt_data.get("shop_context", {}).get(shop_type, "")

    # Build the rendered prompt: YAML structure with resolved values
    rendered = dict(prompt_data)
    rendered["role"] = role
    rendered["shop_context"] = shop_context  # only the relevant one

    return yaml.dump(rendered, default_flow_style=False, sort_keys=False, allow_unicode=True)


def get_recommend_yaml_raw() -> str:
    """Return the raw YAML template (for prompt transparency display)."""
    yaml_path = PROMPTS_DIR / "recommend.yaml"
    return yaml_path.read_text()

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

        pop = p.get("popularity_score", 0)
        conv = p.get("conversion_score", 0)
        margin = p.get("margin_score", 0)

        lines.append(
            f'- id:{p["id"]} | {p["name"]} | £{p["price"]:.2f} | '
            f'cat:{p["category"]} | tags:[{tags}] | dietary:[{dietary}] | '
            f'allergens:[{allergens}] | taste:[{taste}] | '
            f'size:{p.get("portion_size","?")} | cal:{p.get("calories_band","?")} | '
            f'prep:{p.get("prep_time_minutes","?")}min | '
            f'popularity:{pop} | conversion:{conv} | margin:{margin} | '
            f'upsells:[{upsell_str}]'
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
    shop_type: str = "shop",
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

    # Validate cross_sell_id
    cross_sell_id = raw.get("cross_sell_id")
    if cross_sell_id and cross_sell_id not in valid_ids:
        logger.warning("Stripped hallucinated cross_sell_id: %s", cross_sell_id)
        cross_sell_id = None
    # Don't cross-sell something already recommended or in basket
    if cross_sell_id and cross_sell_id in valid_rec_ids:
        cross_sell_id = None

    # Validate clarification
    clarification = None
    if raw.get("needs_clarification"):
        q = raw.get("clarification_question", "")
        if q and 10 <= len(q) <= 200:
            clarification = q if "?" in q else q + "?"

    return {
        "recommended_ids": valid_rec_ids[:3],
        "cross_sell_id": cross_sell_id,
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
    shop_type: str = "shop",
) -> dict | None:
    """Main LLM call: receives the product catalog, picks products, and explains why.

    Returns validated dict with recommended_ids, message, reasoning, and optional
    clarification — or None on failure (triggers deterministic fallback).
    """
    user_prompt = build_recommend_prompt(user_message, products, basket, history, shop_type)
    system_prompt = get_recommend_system_prompt(shop_type)

    messages = [
        {"role": "system", "content": system_prompt},
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
