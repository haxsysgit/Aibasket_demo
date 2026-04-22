from __future__ import annotations

from models.schemas import Intent, Product

# Ranking weights from brain.md
WEIGHTS = {
    "intent_match": 0.30,
    "dietary_match": 0.20,
    "behaviour_match": 0.15,
    "prep_speed_match": 0.10,
    "popularity": 0.10,
    "conversion": 0.10,
    "margin": 0.05,
}

# Maps behaviour types to intent signal keys
BEHAVIOUR_TO_SIGNAL: dict[str, str] = {
    "rushed": "rushed",
    "budget": "budget",
    "health_focused": "healthy",
    "exploring": "light",
}

# Maximum prep time across catalog (for normalization)
MAX_PREP_TIME = 15


def score_product(product: Product, intent: Intent) -> float:
    """Calculate the final weighted score for a product given an intent."""
    intent_score = _calc_intent_match(product, intent)
    dietary_score = _calc_dietary_match(product, intent)
    behaviour_score = _calc_behaviour_match(product, intent)
    prep_score = _calc_prep_speed(product)
    popularity = product.popularity_score / 100.0
    conversion = product.conversion_score / 100.0
    margin = product.margin_score / 100.0

    final = (
        WEIGHTS["intent_match"] * intent_score
        + WEIGHTS["dietary_match"] * dietary_score
        + WEIGHTS["behaviour_match"] * behaviour_score
        + WEIGHTS["prep_speed_match"] * prep_score
        + WEIGHTS["popularity"] * popularity
        + WEIGHTS["conversion"] * conversion
        + WEIGHTS["margin"] * margin
    )
    return round(final, 4)


def rank_products(
    products: list[Product], intent: Intent
) -> list[tuple[Product, float]]:
    """Rank products by score, highest first.

    Returns list of (product, score) tuples.
    """
    scored = [(p, score_product(p, intent)) for p in products]

    # For budget behaviour, secondary sort by price ascending
    if intent.behaviour == "budget":
        scored.sort(key=lambda x: (-x[1], x[0].price))
    else:
        scored.sort(key=lambda x: -x[1])

    return scored


def get_top_recommendations(
    products: list[Product], intent: Intent
) -> list[Product]:
    """Get the top N recommended products based on behaviour type."""
    num_options = {
        "rushed": 1,
        "budget": 2,
        "health_focused": 2,
        "exploring": 3,
    }.get(intent.behaviour, 3)

    ranked = rank_products(products, intent)
    return [p for p, _ in ranked[:num_options]]


def _calc_intent_match(product: Product, intent: Intent) -> float:
    """Dot product of intent preferences against product intent signals."""
    if not intent.preferences:
        # No explicit preferences — use a default mild score
        return 0.5

    total = 0.0
    count = 0
    for pref in intent.preferences:
        signal = product.intent_signals.get(pref, 0.0)
        total += signal
        count += 1

    return total / count if count > 0 else 0.5


def _calc_dietary_match(product: Product, intent: Intent) -> float:
    """1.0 if product passes dietary requirements, 0.0 if conflict."""
    if not intent.dietary:
        return 1.0

    for req in intent.dietary:
        if req == "vegan" and "vegan" not in product.dietary:
            return 0.0
        if req == "gluten_free" and "gluten" in product.allergens:
            return 0.0
        if req == "dairy_free" and "dairy" in product.allergens:
            return 0.0
    return 1.0


def _calc_behaviour_match(product: Product, intent: Intent) -> float:
    """How well product matches the detected behaviour type."""
    signal_key = BEHAVIOUR_TO_SIGNAL.get(intent.behaviour, "light")
    return product.intent_signals.get(signal_key, 0.5)


def _calc_prep_speed(product: Product) -> float:
    """Faster prep = higher score. Normalized to 0-1."""
    if MAX_PREP_TIME == 0:
        return 1.0
    return max(0.0, 1.0 - (product.prep_time_minutes / MAX_PREP_TIME))
