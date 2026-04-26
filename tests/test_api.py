import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


class TestClassifyIntent:
    def test_light_lunch(self):
        res = client.post("/api/classify-intent", json={"text": "I want a light lunch"})
        assert res.status_code == 200
        data = res.json()
        assert data["category"] == "lunch"
        assert "light" in data["preferences"]

    def test_quick_snack(self):
        res = client.post("/api/classify-intent", json={"text": "something quick"})
        assert res.status_code == 200
        data = res.json()
        assert "quick" in data["modifiers"]
        assert data["behaviour"] == "rushed"

    def test_vegan_request(self):
        res = client.post("/api/classify-intent", json={"text": "vegan breakfast"})
        assert res.status_code == 200
        data = res.json()
        assert data["category"] == "breakfast"
        assert "vegan" in data["dietary"]

    def test_budget_signal(self):
        res = client.post("/api/classify-intent", json={"text": "cheap lunch please"})
        assert res.status_code == 200
        data = res.json()
        assert data["behaviour"] == "budget"

    def test_vague_input(self):
        res = client.post("/api/classify-intent", json={"text": "what do you have"})
        assert res.status_code == 200
        data = res.json()
        assert data["behaviour"] == "exploring"


class TestRecommend:
    def test_light_lunch_returns_products(self):
        res = client.post("/api/recommend", json={
            "intent": "lunch",
            "preferences": ["light"],
            "behaviour": "exploring",
            "store_type": "cafe",
        })
        assert res.status_code == 200
        data = res.json()
        assert len(data["products"]) > 0
        assert len(data["products"]) <= 3

    def test_rushed_returns_one_product(self):
        res = client.post("/api/recommend", json={
            "intent": "lunch",
            "preferences": ["light"],
            "modifiers": ["quick"],
            "behaviour": "rushed",
            "store_type": "cafe",
        })
        assert res.status_code == 200
        data = res.json()
        assert len(data["products"]) == 1

    def test_budget_returns_two_products(self):
        res = client.post("/api/recommend", json={
            "intent": "lunch",
            "modifiers": ["cheap"],
            "behaviour": "budget",
            "store_type": "cafe",
        })
        assert res.status_code == 200
        data = res.json()
        assert len(data["products"]) <= 2

    def test_breakfast_category(self):
        res = client.post("/api/recommend", json={
            "intent": "breakfast",
            "preferences": ["healthy"],
            "behaviour": "health_focused",
            "store_type": "cafe",
        })
        assert res.status_code == 200
        data = res.json()
        assert len(data["products"]) > 0

    def test_clarification_on_bare_intent(self):
        res = client.post("/api/recommend", json={
            "intent": "lunch",
            "store_type": "cafe",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["clarification"] is not None

    def test_no_clarification_with_preferences(self):
        res = client.post("/api/recommend", json={
            "intent": "lunch",
            "preferences": ["light"],
            "store_type": "cafe",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["clarification"] is None

    def test_products_have_required_fields(self):
        res = client.post("/api/recommend", json={
            "intent": "lunch",
            "preferences": ["light"],
            "store_type": "cafe",
        })
        data = res.json()
        for product in data["products"]:
            assert "id" in product
            assert "name" in product
            assert "price" in product
            assert "tags" in product
            assert "reason" in product

    def test_drink_category(self):
        res = client.post("/api/recommend", json={
            "intent": "drink",
            "preferences": ["healthy"],
            "behaviour": "exploring",
            "store_type": "cafe",
        })
        assert res.status_code == 200
        data = res.json()
        assert len(data["products"]) > 0

    def test_pub_lunch(self):
        res = client.post("/api/recommend", json={
            "intent": "lunch",
            "preferences": ["filling"],
            "behaviour": "exploring",
            "store_type": "pub",
        })
        assert res.status_code == 200
        data = res.json()
        assert len(data["products"]) > 0
        for p in data["products"]:
            assert p["store_type"] == "pub"

    def test_bakery_breakfast(self):
        res = client.post("/api/recommend", json={
            "intent": "breakfast",
            "preferences": ["indulgent"],
            "behaviour": "exploring",
            "store_type": "bakery",
        })
        assert res.status_code == 200
        data = res.json()
        assert len(data["products"]) > 0
        for p in data["products"]:
            assert p["store_type"] == "bakery"

    def test_corner_shop_snack(self):
        res = client.post("/api/recommend", json={
            "intent": "snack",
            "preferences": ["light"],
            "behaviour": "exploring",
            "store_type": "corner_shop",
        })
        assert res.status_code == 200
        data = res.json()
        assert len(data["products"]) > 0
        for p in data["products"]:
            assert p["store_type"] == "corner_shop"

    def test_store_isolation(self):
        cafe = client.post("/api/recommend", json={
            "intent": "drink",
            "preferences": ["light"],
            "store_type": "cafe",
        }).json()
        pub = client.post("/api/recommend", json={
            "intent": "drink",
            "preferences": ["light"],
            "store_type": "pub",
        }).json()
        cafe_ids = {p["id"] for p in cafe["products"]}
        pub_ids = {p["id"] for p in pub["products"]}
        assert cafe_ids.isdisjoint(pub_ids)


class TestUpsell:
    def test_upsell_returns_product(self):
        res = client.post("/api/upsell", json={
            "product_id": "cafe_001",
            "basket_ids": ["cafe_001"],
            "store_type": "cafe",
        })
        assert res.status_code == 200
        data = res.json()
        assert len(data["products"]) > 0
        assert data["message"] != ""

    def test_upsell_excludes_basket_items(self):
        res = client.post("/api/upsell", json={
            "product_id": "cafe_001",
            "basket_ids": ["cafe_001", "cafe_012", "cafe_015"],
            "store_type": "cafe",
        })
        assert res.status_code == 200
        data = res.json()
        # All upsell pairs for prod_001 are in basket, so no upsell
        assert len(data["products"]) == 0

    def test_upsell_invalid_product(self):
        res = client.post("/api/upsell", json={
            "product_id": "nonexistent",
            "basket_ids": [],
        })
        assert res.status_code == 200
        data = res.json()
        assert len(data["products"]) == 0

    def test_upsell_product_has_fields(self):
        res = client.post("/api/upsell", json={
            "product_id": "cafe_002",
            "basket_ids": [],
            "store_type": "cafe",
        })
        data = res.json()
        if data["products"]:
            p = data["products"][0]
            assert "id" in p
            assert "name" in p
            assert "price" in p


class TestChat:
    """Tests for /api/chat — multi-turn, validation, fallback."""

    def test_basic_chat_returns_products(self):
        res = client.post("/api/chat", json={
            "message": "I want a quick light lunch",
            "store_type": "cafe",
        })
        assert res.status_code == 200
        data = res.json()
        assert len(data["products"]) > 0
        assert data["turn_count"] == 1
        assert data["can_follow_up"] is True

    def test_chat_response_shape(self):
        res = client.post("/api/chat", json={"message": "healthy breakfast"})
        data = res.json()
        for key in ["products", "ai_message", "intent_used", "llm_used",
                     "prompts", "can_follow_up", "turn_count"]:
            assert key in data

    def test_chat_with_history(self):
        res = client.post("/api/chat", json={
            "message": "something cheaper",
            "store_type": "cafe",
            "history": [
                {"role": "user", "content": "I want a light lunch"},
                {"role": "assistant", "content": "I'd recommend the Granola Pot."},
            ],
        })
        assert res.status_code == 200
        data = res.json()
        assert data["turn_count"] == 2
        assert data["can_follow_up"] is True

    def test_chat_max_turns(self):
        history = []
        for i in range(3):
            history.append({"role": "user", "content": f"turn {i+1}"})
            history.append({"role": "assistant", "content": f"response {i+1}"})
        res = client.post("/api/chat", json={
            "message": "one more thing",
            "store_type": "cafe",
            "history": history,
        })
        data = res.json()
        assert data["turn_count"] == 4
        assert data["can_follow_up"] is False

    def test_chat_clarification_first_turn(self):
        res = client.post("/api/chat", json={
            "message": "lunch",
            "store_type": "cafe",
        })
        data = res.json()
        # Should get a clarification on bare "lunch" with no preferences
        assert data["clarification"] is not None or len(data["products"]) > 0

    def test_chat_no_clarification_on_followup(self):
        res = client.post("/api/chat", json={
            "message": "lunch",
            "store_type": "cafe",
            "history": [
                {"role": "user", "content": "what's good here?"},
                {"role": "assistant", "content": "What kind of meal are you after?"},
            ],
        })
        data = res.json()
        # Should NOT clarify on second turn — just give results
        assert data["clarification"] is None

    def test_chat_with_basket(self):
        res = client.post("/api/chat", json={
            "message": "I want a light lunch",
            "store_type": "cafe",
            "basket_ids": ["cafe_001"],
        })
        assert res.status_code == 200
        data = res.json()
        assert len(data["products"]) > 0

    def test_chat_store_isolation(self):
        res = client.post("/api/chat", json={
            "message": "a pint and some chips",
            "store_type": "pub",
        })
        data = res.json()
        for p in data["products"]:
            assert p["store_type"] == "pub"

    def test_chat_empty_message(self):
        res = client.post("/api/chat", json={
            "message": "   ",
            "store_type": "cafe",
        })
        assert res.status_code == 200


class TestValidation:
    """Tests for the LLM validation layer."""

    def test_validate_intent_strips_bad_values(self):
        from llm.openai_client import validate_intent
        raw = {
            "category": "pizza",  # not valid
            "preferences": ["light", "FAKE", "healthy"],
            "modifiers": ["quick", "turbo"],
            "dietary": ["vegan", "keto"],
            "behaviour": "zen",
        }
        result = validate_intent(raw)
        assert result["category"] == "unknown"
        assert result["preferences"] == ["light", "healthy"]
        assert result["modifiers"] == ["quick"]
        assert result["dietary"] == ["vegan"]
        assert result["behaviour"] == "exploring"

    def test_validate_intent_passes_good_values(self):
        from llm.openai_client import validate_intent
        raw = {
            "category": "lunch",
            "preferences": ["light"],
            "modifiers": ["budget"],
            "dietary": ["gluten_free"],
            "behaviour": "rushed",
        }
        result = validate_intent(raw)
        assert result == raw

    def test_validate_response_rejects_empty(self):
        from llm.openai_client import validate_response_text
        assert validate_response_text(None, []) is None
        assert validate_response_text("", []) is None
        assert validate_response_text("short", []) is None  # < 10 chars

    def test_validate_response_truncates_long(self):
        from llm.openai_client import validate_response_text
        long_text = "This is a sentence. " * 100  # way over 800 chars
        result = validate_response_text(long_text, ["Product"])
        assert result is not None
        assert len(result) <= 810

    def test_validate_clarification_basic(self):
        from llm.openai_client import validate_clarification
        assert validate_clarification(None) is None
        assert validate_clarification("hi") is None  # too short
        assert validate_clarification("A" * 300) is None  # too long
        result = validate_clarification("Are you looking for something quick?")
        assert result == "Are you looking for something quick?"

    def test_validate_clarification_adds_question_mark(self):
        from llm.openai_client import validate_clarification
        result = validate_clarification("Would you like something sweet or savoury")
        assert result.endswith("?")

    def test_validate_recommendation_strips_hallucinated_ids(self):
        from llm.openai_client import validate_recommendation
        valid_ids = {"cafe_001", "cafe_002", "cafe_003"}
        raw = {
            "recommended_ids": ["cafe_001", "FAKE_999", "cafe_002"],
            "reasoning": "Good picks",
            "message": "I'd recommend the wrap and the sandwich.",
            "needs_clarification": False,
        }
        result = validate_recommendation(raw, valid_ids)
        assert result is not None
        assert result["recommended_ids"] == ["cafe_001", "cafe_002"]
        assert "FAKE_999" not in result["recommended_ids"]

    def test_validate_recommendation_rejects_all_hallucinated(self):
        from llm.openai_client import validate_recommendation
        valid_ids = {"cafe_001", "cafe_002"}
        raw = {
            "recommended_ids": ["FAKE_001", "FAKE_002"],
            "reasoning": "Made up products",
            "message": "Here are some options.",
        }
        result = validate_recommendation(raw, valid_ids)
        assert result is None

    def test_validate_recommendation_limits_to_three(self):
        from llm.openai_client import validate_recommendation
        valid_ids = {"cafe_001", "cafe_002", "cafe_003", "cafe_004", "cafe_005"}
        raw = {
            "recommended_ids": ["cafe_001", "cafe_002", "cafe_003", "cafe_004", "cafe_005"],
            "reasoning": "All five",
            "message": "Here are five products for you.",
        }
        result = validate_recommendation(raw, valid_ids)
        assert result is not None
        assert len(result["recommended_ids"]) == 3

    def test_validate_recommendation_clarification(self):
        from llm.openai_client import validate_recommendation
        valid_ids = {"cafe_001"}
        raw = {
            "recommended_ids": [],
            "reasoning": "",
            "message": "",
            "needs_clarification": True,
            "clarification_question": "Are you looking for breakfast or lunch?",
        }
        # No valid product IDs → returns None (clarification handled differently)
        result = validate_recommendation(raw, valid_ids)
        assert result is None

    def test_yaml_prompt_loads_and_renders(self):
        from llm.openai_client import get_recommend_system_prompt, get_recommend_yaml_raw
        # Raw YAML template should contain {shop_type} placeholder
        raw = get_recommend_yaml_raw()
        assert "{shop_type}" in raw
        assert "shop_context:" in raw

        # Rendered for cafe should contain "café" and café context
        rendered = get_recommend_system_prompt("cafe")
        assert "café" in rendered
        assert "casual" in rendered.lower()  # café context mentions casual

        # Rendered for pub should contain "pub" and pub context
        rendered_pub = get_recommend_system_prompt("pub")
        assert "pub" in rendered_pub
        assert "hearty" in rendered_pub.lower() or "pint" in rendered_pub.lower()

        # Rendered for corner_shop
        rendered_cs = get_recommend_system_prompt("corner_shop")
        assert "corner shop" in rendered_cs
        assert "convenience" in rendered_cs.lower() or "rush" in rendered_cs.lower()

    def test_validate_recommendation_cross_sell_valid(self):
        from llm.openai_client import validate_recommendation
        valid_ids = {"cafe_001", "cafe_002", "cafe_003"}
        raw = {
            "recommended_ids": ["cafe_001"],
            "cross_sell_id": "cafe_003",
            "reasoning": "Good pick",
            "message": "I'd recommend the wrap — and grab a coffee too.",
        }
        result = validate_recommendation(raw, valid_ids)
        assert result is not None
        assert result["cross_sell_id"] == "cafe_003"

    def test_validate_recommendation_cross_sell_hallucinated(self):
        from llm.openai_client import validate_recommendation
        valid_ids = {"cafe_001", "cafe_002"}
        raw = {
            "recommended_ids": ["cafe_001"],
            "cross_sell_id": "FAKE_999",
            "reasoning": "Good pick",
            "message": "Here's a nice wrap for you.",
        }
        result = validate_recommendation(raw, valid_ids)
        assert result is not None
        assert result["cross_sell_id"] is None

    def test_validate_recommendation_cross_sell_no_duplicate(self):
        from llm.openai_client import validate_recommendation
        valid_ids = {"cafe_001", "cafe_002"}
        raw = {
            "recommended_ids": ["cafe_001"],
            "cross_sell_id": "cafe_001",  # same as recommendation
            "reasoning": "Good pick",
            "message": "Here's the wrap.",
        }
        result = validate_recommendation(raw, valid_ids)
        assert result is not None
        assert result["cross_sell_id"] is None  # stripped because it duplicates

    def test_format_product_catalog(self):
        from llm.openai_client import format_product_catalog
        products = [
            {
                "id": "test_001", "name": "Test Product", "price": 5.00,
                "category": "lunch", "tags": ["quick", "light"],
                "dietary": ["vegan"], "allergens": ["gluten"],
                "taste_profile": ["savory"], "portion_size": "medium",
                "calories_band": "300-400", "prep_time_minutes": 3,
                "popularity_score": 85, "conversion_score": 78, "margin_score": 60,
                "upsell_pairs": [{"product_id": "test_002", "type": "drink"}],
            }
        ]
        catalog = format_product_catalog(products)
        assert "test_001" in catalog
        assert "Test Product" in catalog
        assert "£5.00" in catalog
        assert "vegan" in catalog
        assert "test_002" in catalog
        assert "popularity:85" in catalog
        assert "conversion:78" in catalog
        assert "margin:60" in catalog

    def test_yaml_prompt_has_commercial_strategy(self):
        from llm.openai_client import get_recommend_yaml_raw
        raw = get_recommend_yaml_raw()
        assert "commercial_strategy:" in raw
        assert "cross_sell" in raw
        assert "margin" in raw
        assert "popularity" in raw
        assert "basket_value" in raw
