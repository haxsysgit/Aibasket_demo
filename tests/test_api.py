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
