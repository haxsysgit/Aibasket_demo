from __future__ import annotations

from pydantic import BaseModel


class RecommendRequest(BaseModel):
    intent: str | None = None
    preferences: list[str] = []
    modifiers: list[str] = []
    dietary: list[str] = []
    behaviour: str = "exploring"
    store_type: str = "cafe"


class ProductOut(BaseModel):
    id: str
    name: str
    store_type: str = "cafe"
    price: float
    tags: list[str]
    dietary: list[str]
    calories_band: str
    prep_time_minutes: int
    reason: str = ""


class RecommendResponse(BaseModel):
    products: list[ProductOut]
    clarification: str | None = None


class UpsellRequest(BaseModel):
    product_id: str
    basket_ids: list[str] = []
    store_type: str = "cafe"


class UpsellResponse(BaseModel):
    products: list[ProductOut]
    message: str = ""


class ClassifyRequest(BaseModel):
    text: str
    store_type: str = "cafe"


class ClassifyResponse(BaseModel):
    category: str | None = None
    preferences: list[str] = []
    modifiers: list[str] = []
    dietary: list[str] = []
    behaviour: str = "exploring"
