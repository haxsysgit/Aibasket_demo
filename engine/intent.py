from __future__ import annotations

from models.schemas import Intent

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "lunch": ["lunch", "midday", "noon", "mid-day"],
    "breakfast": ["breakfast", "morning", "start the day", "brunch"],
    "snack": ["snack", "nibble", "small bite", "something small"],
    "drink": ["drink", "beverage", "thirsty", "juice", "coffee", "tea", "smoothie"],
    "dinner": ["dinner", "evening", "supper"],
}

PREFERENCE_KEYWORDS: dict[str, list[str]] = {
    "light": ["light", "not heavy", "something light"],
    "healthy": ["healthy", "nutritious", "clean", "low calorie", "low-calorie"],
    "filling": ["filling", "big", "hearty", "hungry", "starving"],
    "indulgent": ["indulgent", "treat", "rich", "comfort", "cheat"],
}

MODIFIER_KEYWORDS: dict[str, list[str]] = {
    "quick": ["quick", "fast", "rush", "hurry", "no time", "rushed"],
    "cheap": ["cheap", "affordable", "budget", "low cost", "inexpensive"],
}

DIETARY_KEYWORDS: dict[str, list[str]] = {
    "halal": ["halal"],
    "vegan": ["vegan", "plant-based", "plant based"],
    "gluten_free": ["gluten free", "gluten-free", "no gluten", "coeliac", "celiac"],
    "dairy_free": ["dairy free", "dairy-free", "no dairy", "lactose"],
}

BEHAVIOUR_MAP: dict[str, dict] = {
    "rushed": {
        "triggers": ["quick", "fast", "hurry", "rush", "no time", "rushed"],
        "num_options": 1,
    },
    "budget": {
        "triggers": ["cheap", "affordable", "budget", "low cost", "inexpensive"],
        "num_options": 2,
    },
    "health_focused": {
        "triggers": ["healthy", "light", "low calorie", "clean", "nutritious"],
        "num_options": 2,
    },
    "exploring": {
        "triggers": [],
        "num_options": 3,
    },
}


def _match_keywords(text: str, keyword_map: dict[str, list[str]]) -> list[str]:
    """Return all keys whose keywords appear in the text."""
    text_lower = text.lower()
    matches = []
    for key, keywords in keyword_map.items():
        for kw in keywords:
            if kw in text_lower:
                matches.append(key)
                break
    return matches


def classify_behaviour(text: str) -> str:
    """Classify user behaviour from their message."""
    text_lower = text.lower()
    for behaviour, config in BEHAVIOUR_MAP.items():
        if behaviour == "exploring":
            continue
        for trigger in config["triggers"]:
            if trigger in text_lower:
                return behaviour
    return "exploring"


def extract_intent(user_message: str) -> Intent:
    """Extract structured intent from a user message."""
    categories = _match_keywords(user_message, CATEGORY_KEYWORDS)
    preferences = _match_keywords(user_message, PREFERENCE_KEYWORDS)
    modifiers = _match_keywords(user_message, MODIFIER_KEYWORDS)
    dietary = _match_keywords(user_message, DIETARY_KEYWORDS)
    behaviour = classify_behaviour(user_message)

    return Intent(
        category=categories[0] if categories else None,
        preferences=preferences,
        modifiers=modifiers,
        dietary=dietary,
        behaviour=behaviour,
    )
