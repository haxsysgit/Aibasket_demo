from __future__ import annotations

from pydantic import BaseModel


class UpsellPair(BaseModel):
    product_id: str
    type: str


class Product(BaseModel):
    id: str
    name: str
    store_type: str = "cafe"
    category: str
    sub_category: list[str]
    price: float
    tags: list[str]
    dietary: list[str]
    allergens: list[str]
    taste_profile: list[str]
    portion_size: str
    calories_band: str
    prep_time_minutes: int
    intent_signals: dict[str, float]
    upsell_pairs: list[UpsellPair]
    popularity_score: int
    conversion_score: int
    margin_score: int


class Intent(BaseModel):
    category: str | None = None
    preferences: list[str] = []
    modifiers: list[str] = []
    dietary: list[str] = []
    behaviour: str = "exploring"


class BasketItem(BaseModel):
    product: Product
    quantity: int = 1


class RecommendationResult(BaseModel):
    products: list[Product]
    upsell: Product | None = None
    behaviour: str = "exploring"
    num_options: int = 3
