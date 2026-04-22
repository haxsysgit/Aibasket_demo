from __future__ import annotations

from models.schemas import Product


def get_upsell(
    recommended: Product,
    all_products: list[Product],
    basket_ids: set[str] | None = None,
) -> Product | None:
    """Select the best complementary product for the recommended item.

    Picks the upsell pair with the highest popularity score that isn't
    already in the basket.
    """
    if basket_ids is None:
        basket_ids = set()

    product_map = {p.id: p for p in all_products}
    candidates = []

    for pair in recommended.upsell_pairs:
        if pair.product_id in basket_ids:
            continue
        product = product_map.get(pair.product_id)
        if product:
            candidates.append(product)

    if not candidates:
        return None

    # Pick highest popularity
    candidates.sort(key=lambda p: p.popularity_score, reverse=True)
    return candidates[0]
