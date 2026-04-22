from __future__ import annotations

from models.schemas import BasketItem, Intent, Product


def generate_greeting() -> str:
    return (
        "Hi there! Welcome to our café. 😊\n\n"
        "What can I help you find today? Whether it's breakfast, lunch, "
        "a quick snack, or a drink — I'm here to help."
    )


def generate_clarifying_question(intent: Intent) -> str | None:
    """Generate a follow-up question if key info is missing."""
    if not intent.category:
        return (
            "Are you looking for **breakfast**, **lunch**, a **snack**, "
            "or maybe just a **drink**?"
        )

    if not intent.preferences and not intent.modifiers:
        questions = {
            "breakfast": "Are you after something **light and quick**, or a **bigger meal** to start the day?",
            "lunch": "Would you prefer something **light**, or are you looking for something more **filling**?",
            "snack": "Something **sweet** or **savoury**?",
            "drink": "Hot or cold? Any preference?",
        }
        return questions.get(intent.category)

    return None


def generate_recommendation(
    products: list[Product], intent: Intent
) -> str:
    """Generate a natural-sounding recommendation message."""
    if not products:
        return (
            "Hmm, I couldn't find an exact match for that. "
            "Could you tell me a bit more about what you're looking for?"
        )

    if len(products) == 1:
        return _format_single_recommendation(products[0], intent)
    else:
        return _format_multiple_recommendations(products, intent)


def generate_upsell(upsell_product: Product, main_product: Product) -> str:
    """Generate an upsell suggestion."""
    return (
        f"A lot of people enjoy a **{upsell_product.name}** with their "
        f"{main_product.name} — would you like to add one for "
        f"**£{upsell_product.price:.2f}**?"
    )


def generate_basket_update(basket: list[BasketItem]) -> str:
    """Generate a basket summary message."""
    if not basket:
        return "Your basket is empty. What would you like to add?"

    lines = ["Great choice! Here's your basket so far:\n"]
    total = 0.0
    for item in basket:
        line_total = item.product.price * item.quantity
        total += line_total
        qty_str = f" x{item.quantity}" if item.quantity > 1 else ""
        lines.append(f"- **{item.product.name}**{qty_str} — £{line_total:.2f}")

    lines.append(f"\n**Total: £{total:.2f}**")
    lines.append("\nAnything else, or shall we wrap up?")
    return "\n".join(lines)


def generate_no_match_response() -> str:
    return (
        "I'm sorry, I don't have anything that matches that exactly. "
        "Could you tell me a bit more about what you'd like? "
        "I can suggest something close."
    )


def generate_upsell_declined() -> str:
    return "No problem at all! Your basket is looking good. Anything else you'd like?"


def generate_closing(basket: list[BasketItem]) -> str:
    if not basket:
        return "No worries! Feel free to come back anytime. 👋"

    total = sum(item.product.price * item.quantity for item in basket)
    return (
        f"You're all set! Your total comes to **£{total:.2f}**.\n\n"
        "Thanks for stopping by — enjoy your meal! 🎉"
    )


def _format_single_recommendation(product: Product, intent: Intent) -> str:
    reasons = _get_reasons(product, intent)
    reason_str = ", ".join(reasons) if reasons else "a great choice"

    return (
        f"I'd recommend the **{product.name}** — it's {reason_str}. "
        f"Priced at **£{product.price:.2f}**.\n\n"
        "Would you like to add it to your basket?"
    )


def _format_multiple_recommendations(
    products: list[Product], intent: Intent
) -> str:
    lines = ["Here are my top picks for you:\n"]

    for i, product in enumerate(products, 1):
        reasons = _get_reasons(product, intent)
        reason_str = ", ".join(reasons) if reasons else "a solid option"
        lines.append(
            f"**{i}. {product.name}** — £{product.price:.2f} "
            f"({reason_str})"
        )

    lines.append("\nWhich one catches your eye? Or I can tell you more about any of them.")
    return "\n".join(lines)


def _get_reasons(product: Product, intent: Intent) -> list[str]:
    """Build a list of human-readable reasons for recommending this product."""
    reasons = []

    # Intent-based reasons
    if "light" in intent.preferences and product.intent_signals.get("light", 0) > 0.7:
        reasons.append("light")
    if "healthy" in intent.preferences and product.intent_signals.get("healthy", 0) > 0.7:
        reasons.append("healthy")
    if "filling" in intent.preferences and product.intent_signals.get("filling", 0) > 0.7:
        reasons.append("filling")

    # Speed
    if product.prep_time_minutes <= 5:
        reasons.append("quick to prepare")

    # Popularity
    if product.popularity_score >= 80:
        reasons.append("very popular")
    elif product.popularity_score >= 70:
        reasons.append("popular")

    # Price
    if product.price <= 4.0:
        reasons.append("great value")

    # Limit to 3 reasons
    return reasons[:3]
