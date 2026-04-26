from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from api.models import (
    ChatRequest,
    ChatResponse,
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
from llm.openai_client import (
    MAX_TURNS,
    extract_intent_llm,
    generate_clarification_llm,
    recommend_from_catalog,
    is_llm_available,
    get_recommend_system_prompt,
    get_recommend_yaml_raw,
    INTENT_EXTRACTION_SYSTEM,
    CLARIFICATION_SYSTEM,
    build_recommend_prompt,
)
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


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """LLM-first chat: pass product catalog to LLM, let it pick + explain.

    The LLM receives the full store catalog and recommends products directly.
    Falls back to deterministic engine if LLM is unavailable or returns invalid output.
    """
    all_products = _load_products()
    products = _filter_by_store(all_products, req.store_type)
    product_map = {p.id: p for p in products}
    llm_active = is_llm_available()
    prompts: dict = {}
    history = [{"role": m.role, "content": m.content} for m in req.history]
    turn_count = len([m for m in req.history if m.role == "user"]) + 1
    can_follow_up = turn_count < MAX_TURNS

    # Build basket context
    basket_context = None
    if req.basket_ids:
        basket_context = [
            {"name": product_map[bid].name, "id": bid, "price": product_map[bid].price}
            for bid in req.basket_ids if bid in product_map
        ]

    # Convert products to dicts for LLM
    product_dicts = [_product_to_dict(p) for p in products]

    # ===================================================================
    # LLM PATH: Send full catalog, let LLM pick products + write response
    # ===================================================================
    store = req.store_type or "shop"

    if llm_active:
        llm_result = recommend_from_catalog(
            req.message, product_dicts, basket_context, history, store
        )

        if llm_result is not None:
            # Record prompt transparency
            user_prompt = build_recommend_prompt(
                req.message, product_dicts, basket_context, history, store
            )
            rendered_system = get_recommend_system_prompt(store)
            prompts["recommendation"] = {
                "system_yaml_template": get_recommend_yaml_raw(),
                "system_rendered": rendered_system,
                "user": user_prompt,
                "model_output": {
                    "recommended_ids": llm_result["recommended_ids"],
                    "cross_sell_id": llm_result.get("cross_sell_id"),
                    "reasoning": llm_result["reasoning"],
                    "message": llm_result["message"],
                    "needs_clarification": llm_result["needs_clarification"],
                },
            }

            # Handle clarification from LLM
            if llm_result["needs_clarification"] and llm_result["clarification_question"]:
                return ChatResponse(
                    products=[],
                    clarification=llm_result["clarification_question"],
                    llm_used=True,
                    prompts=prompts,
                    can_follow_up=True,
                    turn_count=turn_count,
                )

            # Build product outputs from LLM-selected IDs
            rec_products = [product_map[pid] for pid in llm_result["recommended_ids"] if pid in product_map]
            product_outs = [_product_to_out(p) for p in rec_products]

            # Cross-sell: LLM suggested a complementary product (validated)
            cross_sell_out = None
            cross_sell_id = llm_result.get("cross_sell_id")
            if cross_sell_id and cross_sell_id in product_map and cross_sell_id not in set(req.basket_ids):
                cross_sell_out = _product_to_out(product_map[cross_sell_id])

            # Upsell: deterministic selection from the first recommended product
            upsell_out = None
            upsell_msg = ""
            if rec_products:
                basket_set = set(req.basket_ids)
                rec_ids_set = set(llm_result["recommended_ids"])
                if cross_sell_id:
                    rec_ids_set.add(cross_sell_id)
                upsell_product = get_upsell(rec_products[0], list(product_map.values()), basket_set | rec_ids_set)
                if upsell_product:
                    upsell_out = _product_to_out(upsell_product)
                    upsell_msg = f"Most people pair this with a {upsell_product.name}"

            # Extract intent for transparency (lightweight, parallel to LLM)
            intent = extract_intent(req.message)
            intent_response = ClassifyResponse(
                category=intent.category,
                preferences=intent.preferences,
                modifiers=intent.modifiers,
                dietary=intent.dietary,
                behaviour=intent.behaviour,
            )

            ai_msg = llm_result["message"] or _static_message([p.name for p in rec_products])

            return ChatResponse(
                products=product_outs,
                ai_message=ai_msg,
                cross_sell=cross_sell_out,
                upsell=upsell_out,
                upsell_message=upsell_msg,
                intent_used=intent_response,
                llm_used=True,
                prompts=prompts,
                can_follow_up=can_follow_up,
                turn_count=turn_count,
            )

    # ===================================================================
    # FALLBACK PATH: Deterministic engine (no LLM or LLM failed)
    # ===================================================================
    intent = extract_intent(req.message)
    intent_response = ClassifyResponse(
        category=intent.category,
        preferences=intent.preferences,
        modifiers=intent.modifiers,
        dietary=intent.dietary,
        behaviour=intent.behaviour,
    )

    # Clarification check (first turn, bare intent)
    if (
        not intent.preferences and not intent.modifiers and not intent.dietary
        and intent.category and intent.category in CLARIFICATION_MAP
        and turn_count == 1
    ):
        clarification = CLARIFICATION_MAP.get(intent.category)
        if clarification:
            filtered = filter_products(products, intent)
            recs = get_top_recommendations(filtered, intent) if filtered else []
            product_outs = [_product_to_out(p, intent) for p in recs]
            return ChatResponse(
                products=product_outs,
                clarification=clarification,
                intent_used=intent_response,
                llm_used=False,
                prompts=prompts,
                can_follow_up=True,
                turn_count=turn_count,
            )

    # Deterministic filtering + ranking
    filtered = filter_products(products, intent)
    if not filtered:
        return ChatResponse(
            products=[],
            ai_message="I couldn't find an exact match for that. Could you tell me a bit more about what you're looking for?",
            intent_used=intent_response,
            llm_used=False,
            prompts=prompts,
            can_follow_up=can_follow_up,
            turn_count=turn_count,
        )

    recs = get_top_recommendations(filtered, intent)
    product_outs = [_product_to_out(p, intent) for p in recs]

    # Upsell
    upsell_out = None
    upsell_msg = ""
    if recs:
        basket_set = set(req.basket_ids)
        upsell_product = get_upsell(recs[0], list(product_map.values()), basket_set)
        if upsell_product:
            upsell_out = _product_to_out(upsell_product)
            upsell_msg = f"Most people pair this with a {upsell_product.name}"

    ai_msg = _static_message([p.name for p in product_outs])

    return ChatResponse(
        products=product_outs,
        ai_message=ai_msg,
        upsell=upsell_out,
        upsell_message=upsell_msg,
        intent_used=intent_response,
        llm_used=False,
        prompts=prompts,
        can_follow_up=can_follow_up,
        turn_count=turn_count,
    )


def _product_to_dict(p: Product) -> dict:
    """Convert a Product schema to a dict suitable for the LLM prompt."""
    return {
        "id": p.id,
        "name": p.name,
        "store_type": p.store_type,
        "category": p.category,
        "sub_category": p.sub_category,
        "price": p.price,
        "tags": p.tags,
        "dietary": p.dietary,
        "allergens": p.allergens,
        "taste_profile": p.taste_profile,
        "portion_size": p.portion_size,
        "calories_band": p.calories_band,
        "prep_time_minutes": p.prep_time_minutes,
        "upsell_pairs": [{"product_id": u.product_id, "type": u.type} for u in p.upsell_pairs],
    }


def _static_message(names: list[str]) -> str:
    """Build a static fallback message from product names."""
    if not names:
        return "I couldn't find an exact match. Could you tell me more about what you're looking for?"
    if len(names) == 1:
        return f"I'd recommend the {names[0]} — it's a great fit for what you described."
    return f"Based on what you're looking for, I'd suggest the {', '.join(names[:-1])} or the {names[-1]}."
