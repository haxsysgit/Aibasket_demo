from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from api.models import (
    ClassifyRequest,
    ClassifyResponse,
    ProductOut,
    RecommendRequest,
    RecommendResponse,
    UpsellRequest,
    UpsellResponse,
)
from engine.filter import filter_products
from engine.intent import extract_intent
from engine.ranker import get_top_recommendations
from engine.upsell import get_upsell
from models.schemas import Intent, Product

router = APIRouter()

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "products.json"

_products_cache: list[Product] | None = None


def _load_products() -> list[Product]:
    global _products_cache
    if _products_cache is None:
        with open(DATA_PATH) as f:
            raw = json.load(f)
        _products_cache = [Product(**item) for item in raw]
    return _products_cache


def _filter_by_store(products: list[Product], store_type: str) -> list[Product]:
    return [p for p in products if p.store_type == store_type]


def _product_to_out(product: Product, intent: Intent | None = None) -> ProductOut:
    reason = _build_reason(product, intent) if intent else ""
    return ProductOut(
        id=product.id,
        name=product.name,
        store_type=product.store_type,
        price=product.price,
        tags=product.tags,
        dietary=product.dietary,
        calories_band=product.calories_band,
        prep_time_minutes=product.prep_time_minutes,
        reason=reason,
    )


def _build_reason(product: Product, intent: Intent) -> str:
    parts = []
    if "light" in intent.preferences and product.intent_signals.get("light", 0) > 0.7:
        parts.append("light")
    if "healthy" in intent.preferences and product.intent_signals.get("healthy", 0) > 0.7:
        parts.append("healthy")
    if "filling" in intent.preferences and product.intent_signals.get("filling", 0) > 0.7:
        parts.append("filling")
    if product.prep_time_minutes <= 5:
        parts.append("quick to prepare")
    if product.popularity_score >= 80:
        parts.append("very popular")
    elif product.popularity_score >= 70:
        parts.append("popular")
    if product.price <= 4.0:
        parts.append("great value")
    if not parts:
        parts.append("a great choice")
    return ", ".join(parts[:3]).capitalize()


CLARIFICATION_MAP = {
    "lunch": "Are you in a rush, or taking your time?",
    "breakfast": "Something light and quick, or a bigger meal to start the day?",
    "snack": "Sweet or savoury?",
    "drink": "Hot or cold?",
    "meal": "Are you in a rush, or taking your time?",
}


@router.post("/recommend", response_model=RecommendResponse)
def recommend(req: RecommendRequest):
    products = _filter_by_store(_load_products(), req.store_type)

    intent = Intent(
        category=req.intent,
        preferences=req.preferences,
        modifiers=req.modifiers,
        dietary=req.dietary,
        behaviour=req.behaviour,
    )

    # If no preferences or modifiers, return a clarification question
    if not req.preferences and not req.modifiers and req.intent:
        clarification = CLARIFICATION_MAP.get(req.intent)
        if clarification:
            # Still return some initial products
            filtered = filter_products(products, intent)
            recs = get_top_recommendations(filtered, intent) if filtered else []
            return RecommendResponse(
                products=[_product_to_out(p, intent) for p in recs],
                clarification=clarification,
            )

    filtered = filter_products(products, intent)
    if not filtered:
        return RecommendResponse(products=[], clarification=None)

    recs = get_top_recommendations(filtered, intent)
    return RecommendResponse(
        products=[_product_to_out(p, intent) for p in recs],
        clarification=None,
    )


@router.post("/upsell", response_model=UpsellResponse)
def upsell(req: UpsellRequest):
    products = _filter_by_store(_load_products(), req.store_type)
    product_map = {p.id: p for p in products}

    selected = product_map.get(req.product_id)
    if not selected:
        return UpsellResponse(products=[], message="")

    basket_set = set(req.basket_ids)
    upsell_product = get_upsell(selected, products, basket_set)

    if not upsell_product:
        return UpsellResponse(products=[], message="")

    return UpsellResponse(
        products=[_product_to_out(upsell_product)],
        message=f"Most people pair this with a {upsell_product.name}",
    )


@router.post("/classify-intent", response_model=ClassifyResponse)
def classify_intent(req: ClassifyRequest):
    intent = extract_intent(req.text)
    return ClassifyResponse(
        category=intent.category,
        preferences=intent.preferences,
        modifiers=intent.modifiers,
        dietary=intent.dietary,
        behaviour=intent.behaviour,
    )
