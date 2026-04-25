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


class ConversationMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    store_type: str = "cafe"
    basket_ids: list[str] = []
    history: list[ConversationMessage] = []


class ChatResponse(BaseModel):
    products: list[ProductOut]
    ai_message: str = ""
    clarification: str | None = None
    upsell: ProductOut | None = None
    upsell_message: str = ""
    intent_used: ClassifyResponse | None = None
    llm_used: bool = False
    prompts: dict = {}
    can_follow_up: bool = True
    turn_count: int = 0
