from __future__ import annotations

from models.schemas import Intent, Product


def filter_products(products: list[Product], intent: Intent) -> list[Product]:
    """Filter products based on extracted intent.

    Applies filters in order: category, dietary, then tag relevance.
    Returns products that pass all hard filters.
    """
    filtered = list(products)

    # Filter by category if specified
    if intent.category:
        category_match = [p for p in filtered if p.category == intent.category]
        # If category filter yields results, use them; otherwise keep all
        # (fallback for better UX)
        if category_match:
            filtered = category_match

    # Filter by dietary constraints (hard filter — must not contain allergens)
    if intent.dietary:
        filtered = _apply_dietary_filter(filtered, intent.dietary)

    return filtered


def _apply_dietary_filter(
    products: list[Product], dietary_requirements: list[str]
) -> list[Product]:
    """Remove products that conflict with dietary requirements."""
    result = []
    for product in products:
        if _passes_dietary_check(product, dietary_requirements):
            result.append(product)
    return result


def _passes_dietary_check(product: Product, dietary_requirements: list[str]) -> bool:
    """Check if a product is compatible with dietary requirements."""
    for req in dietary_requirements:
        if req == "vegan":
            if "vegan" not in product.dietary:
                return False
        elif req == "halal":
            if "halal" not in product.dietary and product.dietary:
                # If product has no dietary tags at all, we can't confirm halal
                pass
            elif product.dietary and "halal" not in product.dietary:
                return False
        elif req == "gluten_free":
            if "gluten" in product.allergens:
                return False
        elif req == "dairy_free":
            if "dairy" in product.allergens:
                return False
    return True
