"""Lightweight OpenAI integration for intent extraction and response generation.

All product decisions remain in the deterministic engine.
The LLM handles two things only:
  1. Turning free text into structured intent (extract_intent_llm)
  2. Phrasing the engine's recommendations naturally (generate_response_llm)
"""

from __future__ import annotations

import json
import logging
import os

from openai import OpenAI

logger = logging.getLogger(__name__)

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

Given a customer message, extract structured intent as JSON. Return ONLY valid JSON, no markdown, no explanation.

Schema:
{
  "category": "lunch" | "breakfast" | "snack" | "drink" | "unknown",
  "preferences": [],    // from: "light", "healthy", "sweet", "filling", "indulgent"
  "modifiers": [],      // from: "quick", "budget", "premium"
  "dietary": [],        // from: "vegan", "vegetarian", "halal", "gluten_free", "dairy_free"
  "behaviour": "rushed" | "budget" | "exploring" | "health_focused"
}

Rules:
- If the category is unclear, use "unknown".
- Only use values from the allowed lists above.
- Prefer "unknown" over guessing.
- Return valid JSON only."""

RESPONSE_GENERATION_SYSTEM = """You are a friendly shop assistant. Keep responses concise (2-4 sentences).

Rules:
- Recommend ONLY from the products provided below. Do not invent products.
- Briefly explain why each product fits the customer's request.
- Be warm and helpful, not pushy.
- If there's an upsell item, mention it naturally using social proof (e.g. "Most people also grab a...").
- Do not use markdown formatting. Use plain text only."""


def _build_response_user_prompt(
    user_message: str,
    products: list[dict],
    upsell: dict | None = None,
) -> str:
    product_lines = []
    for i, p in enumerate(products, 1):
        product_lines.append(
            f"{i}. {p['name']} — £{p['price']:.2f} ({', '.join(p.get('tags', [])[:3])})"
        )

    prompt = f"""Customer said: "{user_message}"

The recommendation engine selected these products (present ONLY these):
{chr(10).join(product_lines)}"""

    if upsell:
        prompt += f"""

Upsell suggestion (mention naturally if appropriate):
- {upsell['name']} — £{upsell['price']:.2f}"""

    return prompt


# ---------------------------------------------------------------------------
# LLM calls
# ---------------------------------------------------------------------------

def extract_intent_llm(text: str) -> dict | None:
    """Ask the LLM to extract structured intent from free text.

    Returns parsed dict on success, None on failure (caller should fall back).
    """
    client = _get_client()
    if client is None:
        return None

    try:
        response = client.chat.completions.create(
            model=_get_model(),
            messages=[
                {"role": "system", "content": INTENT_EXTRACTION_SYSTEM},
                {"role": "user", "content": text},
            ],
            temperature=0.1,
            max_tokens=200,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if model wraps output
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        parsed = json.loads(raw)
        logger.info("LLM intent extraction: %s", parsed)
        return parsed

    except Exception as e:
        logger.error("LLM intent extraction failed: %s", e)
        return None


def generate_response_llm(
    user_message: str,
    products: list[dict],
    upsell: dict | None = None,
) -> str | None:
    """Ask the LLM to phrase the recommendation naturally.

    Returns response string on success, None on failure (caller uses static text).
    """
    client = _get_client()
    if client is None:
        return None

    try:
        user_prompt = _build_response_user_prompt(user_message, products, upsell)

        response = client.chat.completions.create(
            model=_get_model(),
            messages=[
                {"role": "system", "content": RESPONSE_GENERATION_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=300,
        )
        text = response.choices[0].message.content.strip()
        logger.info("LLM response generated (%d chars)", len(text))
        return text

    except Exception as e:
        logger.error("LLM response generation failed: %s", e)
        return None
