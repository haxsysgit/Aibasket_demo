# AI Basket Builder — Implementation Detail

## 1. What This Is

A working demo of an AI-powered shopping assistant. A customer tells it what they want in natural language, and the system recommends products, asks one clarifying question, suggests a complementary item, and handles a simulated checkout.

It runs across four store types — café, pub, bakery, corner shop — each with its own product catalog. Switch the store dropdown and the entire experience changes: different products, different chips, different upsells.

The backend is a Python FastAPI server with an optional OpenAI LLM layer. The frontend is Vue 3 with Tailwind CSS. There is no database, no authentication, and no real payment. Every product decision the system makes is deterministic. The LLM handles understanding (intent extraction) and speaking (response generation) — it never picks, ranks, or invents products.

---

## 2. Architecture

```
┌──────────────────────────────────────────────────┐
│  Browser (Vue 3 + Tailwind CSS)                  │
│                                                  │
│  IntentSelector → ClarificationStep              │
│       → ProductCards → UpsellPrompt              │
│       → BasketPanel → CheckoutScreen             │
│                                                  │
│  api.js — fetch('/api/...')                       │
└──────────────┬───────────────────────────────────┘
               │ HTTP POST (JSON)
               ▼
┌──────────────────────────────────────────────────┐
│  FastAPI Backend (:8000)                         │
│                                                  │
│  POST /api/classify-intent                       │
│  POST /api/recommend                             │
│  POST /api/upsell                                │
│                                                  │
│  ┌────────────┐  ┌──────────┐  ┌─────────────┐  │
│  │ Intent     │  │ Filter   │  │ Ranker      │  │
│  │ Extraction │→ │ Engine   │→ │ (weighted   │  │
│  │            │  │          │  │  scoring)   │  │
│  └────────────┘  └──────────┘  └─────────────┘  │
│                                                  │
│  ┌────────────────────────────────────────────┐  │
│  │ products.json — 60+ products, 4 stores     │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

### Why This Split

The frontend handles presentation and user interaction. It knows nothing about products, ranking, or business logic. The backend handles all decisions. This separation means:

- The product catalog and ranking logic never reach the browser
- The API contract is clean — three endpoints, JSON in, JSON out
- Swapping the frontend (to a widget, mobile app, or chatbot) requires zero backend changes

---

## 3. Design Decisions

### 3.1 Deterministic Engine, Not an LLM

The system uses keyword matching and weighted scoring — not a language model. This was deliberate.

An LLM would introduce latency, cost, and unpredictability. For a recommendation engine, you need **consistency**: the same input should always produce the same output. A customer saying "quick light lunch" should get the same top pick every time, not whatever the model feels like generating.

The architecture is designed so an LLM can be layered on top later — to handle the conversational phrasing — without changing any product decisions. The engine decides *what* to recommend; the AI (when added) would decide *how to say it*.

### 3.2 Store Type as a First-Class Filter

Every product has a `store_type` field. The entire catalog is partitioned: café products never leak into pub results. This was implemented at the API layer, not the frontend.

```python
def _filter_by_store(products, store_type):
    return [p for p in products if p.store_type == store_type]
```

This runs before any other filtering or ranking. It means the engine operates on a completely isolated product set per store — as if each store type is its own deployment.

### 3.3 Weighted Scoring Over Simple Matching

Products aren't just "matched" — they're scored on a weighted formula:

| Factor | Weight | Why |
|---|---|---|
| Intent match | 30% | Does the product fit what they asked for? |
| Dietary safety | 20% | Hard filter — non-negotiable |
| Behaviour fit | 15% | Are they rushed, browsing, on a budget? |
| Prep speed | 10% | Operational: faster items score higher |
| Popularity | 10% | Social proof — popular items convert better |
| Conversion rate | 10% | Historical performance |
| Margin | 5% | Business value — subtle tiebreaker |

Two-thirds customer-focused, one-third business-focused. This balance means the system is helpful first, commercial second — but it still gently steers toward items that are good for the business.

### 3.4 Behaviour-Adaptive Output

The system doesn't always show the same number of results:

| Behaviour | Products shown | Reasoning |
|---|---|---|
| Rushed | 1 | They want speed, not choice |
| Budget | 2, cheapest first | Price-sensitive, need comparison |
| Health-focused | 2 | Focused interest, moderate choice |
| Exploring | 3 | Browsing, show variety |

This is a small detail but it matters. Dumping 10 results on a rushed customer is bad UX. Showing one result to a browser feels stingy.

### 3.5 Single Clarification, Not an Interrogation

When a customer gives a bare intent ("lunch"), the system asks *one* clarifying question — not three. "Are you in a rush, or taking your time?" is enough to dramatically improve the recommendation without feeling like a survey.

```python
CLARIFICATION_MAP = {
    "lunch": "Are you in a rush, or taking your time?",
    "breakfast": "Something light and quick, or a bigger meal?",
    "snack": "Sweet or savoury?",
    "drink": "Hot or cold?",
}
```

If the customer already provided preferences or modifiers, the clarification is skipped entirely. The system only asks when it genuinely doesn't know enough.

### 3.6 Upsell by Complementarity, Not Random

Each product has explicit `upsell_pairs` — curated pairings:

```json
"upsell_pairs": [
  {"product_id": "cafe_012", "type": "drink"},
  {"product_id": "cafe_015", "type": "side"}
]
```

The system picks the pairing with the highest popularity score that isn't already in the basket. The framing uses social proof: *"Most people pair this with a Flat White"* — which works better than a naked "Add a coffee?"

### 3.7 Dark Theme Matching Strivonex.com

The UI mirrors the Strivonex brand: slate-950 backgrounds, fuchsia-to-cyan gradients, clean typography. This wasn't cosmetic — it demonstrates that the widget can be white-labelled to match any retailer's brand with Tailwind utility classes.

---

## 4. File Structure

```
├── api/
│   ├── main.py              # FastAPI app factory, loads .env
│   ├── routes.py             # 4 endpoints: recommend, upsell, classify-intent, chat
│   └── models.py             # Pydantic request/response schemas
│
├── engine/
│   ├── intent.py             # Keyword-based intent extraction (fallback)
│   ├── filter.py             # Category + dietary filtering
│   ├── ranker.py             # Weighted scoring and ranking
│   └── upsell.py             # Complementary product selection
│
├── llm/
│   ├── openai_client.py      # OpenAI: intent extraction + response generation
│   └── simulated.py          # Static response templates (pre-LLM)
│
├── models/
│   └── schemas.py            # Core data models (Product, Intent, etc.)
│
├── data/
│   └── products.json         # 60+ products across 4 store types
│
├── frontend/
│   ├── src/
│   │   ├── App.vue           # Main orchestrator — stage machine
│   │   ├── api.js            # HTTP client for 3 endpoints
│   │   ├── engine.js         # Client-side engine (for static deploy)
│   │   └── components/
│   │       ├── IntentSelector.vue    # Chips + free text input
│   │       ├── ClarificationStep.vue # Single clarifying question
│   │       ├── ProductCards.vue      # Ranked product display
│   │       ├── UpsellPrompt.vue      # Complementary suggestion
│   │       ├── BasketPanel.vue       # Basket with clear + checkout
│   │       └── CheckoutScreen.vue    # Simulated order flow
│   └── data/
│       └── products.json     # Copy for static deployment
│
├── tests/
│   └── test_api.py           # 21 pytest tests covering all endpoints
│
├── deploy/
│   ├── setup.sh              # One-command Ubuntu deploy
│   ├── basket-builder.service # systemd unit for FastAPI
│   ├── basket-builder.nginx   # nginx reverse proxy config
│   └── expose-tunnel.sh      # Cloudflare tunnel for public access
│
├── render.yaml               # Render deployment blueprint
├── build.sh                  # Build script (Python deps + Vue frontend)
├── requirements.txt          # Python dependencies for Render
└── pyproject.toml            # Python dependencies (uv, local dev)
```

---

## 5. The Data Model

Each product carries enough information for the engine to make decisions without guessing:

```python
class Product(BaseModel):
    id: str                        # e.g. "cafe_001"
    name: str                      # "Flat White"
    store_type: str                # "cafe" | "pub" | "bakery" | "corner_shop"
    category: str                  # "drink" | "lunch" | "breakfast" | "snack"
    sub_category: list[str]        # ["hot_drinks", "coffee"]
    price: float                   # 3.40
    tags: list[str]                # ["classic", "hot", "milk"]
    dietary: list[str]             # ["vegetarian"]
    allergens: list[str]           # ["dairy"]
    taste_profile: list[str]       # ["bitter", "creamy"]
    portion_size: str              # "standard"
    calories_band: str             # "low"
    prep_time_minutes: int         # 3
    intent_signals: dict           # {"light": 0.9, "rushed": 0.8, ...}
    upsell_pairs: list[UpsellPair] # [{product_id: "cafe_007", type: "food"}]
    popularity_score: int          # 92
    conversion_score: int          # 88
    margin_score: int              # 72
```

**Intent signals** are the key innovation. They're floating-point scores (0.0–1.0) for how well a product matches common customer intents. A "Flat White" might score 0.9 for "rushed" and 0.2 for "indulgent". A "Full English Breakfast" scores the opposite. This lets the engine translate vague language into precise product matches.

---

## 6. API Contract

### `POST /api/classify-intent`

Turns free text into structured intent.

```json
// Request
{"text": "I want a quick light lunch"}

// Response
{
  "category": "lunch",
  "preferences": ["light"],
  "modifiers": ["quick"],
  "dietary": [],
  "behaviour": "rushed"
}
```

### `POST /api/recommend`

Returns ranked products for a given intent and store.

```json
// Request
{
  "intent": "lunch",
  "preferences": ["light"],
  "modifiers": ["quick"],
  "behaviour": "rushed",
  "store_type": "cafe"
}

// Response
{
  "products": [
    {
      "id": "cafe_005",
      "name": "Grilled Chicken Wrap",
      "store_type": "cafe",
      "price": 8.50,
      "tags": ["light", "high_protein", "quick"],
      "dietary": ["halal"],
      "calories_band": "medium",
      "prep_time_minutes": 5,
      "reason": "Light, quick to prepare, very popular"
    }
  ],
  "clarification": null
}
```

### `POST /api/upsell`

Returns one complementary product.

```json
// Request
{"product_id": "cafe_005", "basket_ids": ["cafe_005"], "store_type": "cafe"}

// Response
{
  "products": [{"id": "cafe_012", "name": "Fresh Orange Juice", ...}],
  "message": "Most people pair this with a Fresh Orange Juice"
}
```

---

## 7. Frontend Flow

The frontend is a **stage machine** with six states:

```
intent → loading → clarifying → results → upsell → checkout
                       ↑            │
                       └────────────┘ (restart)
```

Each state renders one component. The stage transitions are driven by API responses — if the API returns a `clarification` string, the stage moves to `clarifying`. If the user clicks "Add to basket" and the upsell API returns a product, it moves to `upsell`.

The store type dropdown resets everything — basket, recommendations, stage — because products from different stores are completely isolated.

---

## 8. Testing

21 automated tests cover the three endpoints:

- **Intent classification** — light lunch, quick snack, vegan request, budget signal, vague input
- **Recommendations** — correct count per behaviour, clarification logic, required fields, category filtering
- **Store isolation** — pub products never appear in café results and vice versa
- **Upsell** — returns complementary product, excludes basket items, handles invalid IDs

```bash
uv run pytest tests/ -v   # 21 passed
```

---

## 9. Deployment

### Render (Live Demo)

The app runs as a single Render web service. FastAPI serves both the API and the built Vue frontend from `frontend/dist/`. The LLM features work because the backend makes server-side OpenAI calls.

Live at: `https://ai-basket-builder.onrender.com`

**How it works:**
- `render.yaml` defines the service blueprint
- `build.sh` installs Python deps and builds the Vue frontend
- `uvicorn api.main:app` starts the server
- `OPENAI_API_KEY` is set as an environment variable in Render's dashboard

The free tier sleeps after 15 minutes of inactivity. A loading screen is shown while the server wakes up on first visit.

### Self-Hosted (Ubuntu + nginx)

For a more permanent setup. nginx serves the static frontend and proxies `/api/*` to FastAPI running on port 8000 via systemd.

```bash
bash deploy/setup.sh           # Install everything
bash deploy/expose-tunnel.sh   # Get a public URL via Cloudflare Tunnel
```

---

## 10. LLM Integration Layer

### Where the LLM Is Used

The LLM (GPT-4o-mini) has exactly two jobs:

**1. Intent Extraction** — Turn free text like "something sweet but not too heavy" into structured JSON:
```json
{"category": "snack", "preferences": ["sweet", "light"], "modifiers": [], "dietary": [], "behaviour": "exploring"}
```

**2. Response Generation** — Take the engine's ranked products and phrase them naturally:
> "I recommend the Chocolate Brownie! It's sweet and indulgent, yet still light enough. Most people also grab a Flat White Coffee."

### Where the LLM Is NOT Used

- Product filtering (deterministic: category + dietary + store type)
- Product ranking (deterministic: weighted scoring formula)
- Upsell selection (deterministic: curated pairs sorted by popularity)
- Clarification questions (deterministic: hardcoded per category)

### Why This Hybrid Approach

A pure LLM approach would let the model choose products. This is dangerous:
- It can **hallucinate products** that don't exist in the catalog
- It **ignores business rules** (margin, conversion, popularity)
- It's **unpredictable** — same input can give different outputs
- It's **untestable** — you can't write deterministic assertions

The hybrid approach gives you:
- **Reliability** — the engine always picks valid, well-scored products
- **Testability** — 21 automated tests verify product decisions
- **Natural language** — the LLM makes the interaction feel human
- **Controllability** — business rules are in code, not in prompts

### Prompt Design

Both prompts are exposed in the UI via "Show AI reasoning":

**Intent extraction prompt** constrains the model to a fixed schema with allowed values. Temperature is set to 0.1 for consistency. The model returns JSON only — no explanation, no markdown.

**Response generation prompt** receives only the engine-selected products. The model is told: "Recommend ONLY from the products provided below. Do not invent products." This prevents hallucination structurally — the model can only reference what the engine chose.

### Fallback Behaviour

If `OPENAI_API_KEY` is missing or any API call fails:
- Intent extraction falls back to keyword matching (`engine/intent.py`)
- Response generation falls back to static template strings
- A warning is logged — no error shown to the user
- The demo works identically, just without LLM phrasing

---

## 11. How This Becomes Production

This demo is a proof of concept. Here's what changes — and what doesn't — when moving to production.

### What Stays the Same

- **The ranking formula.** Weighted scoring is the right architecture. The weights get tuned with real data, but the approach is sound.
- **The API contract.** Three endpoints, JSON in/out. This interface works for a widget, mobile app, or chatbot.
- **Store isolation.** Products partitioned by store type. In production, each store would have its own catalog in a database.

### What Changes

| Demo | Production |
|---|---|
| `products.json` (60 items) | PostgreSQL or Redis with thousands of products per store |
| GPT-4o-mini for intent (demo) | Fine-tuned model or GPT-4 for higher accuracy |
| Static ranking weights | A/B tested weights, updated from conversion data |
| Hardcoded upsell pairs | ML model trained on purchase history (association rules, collaborative filtering) |
| No auth | OAuth / API keys per retailer |
| Single process | Kubernetes pods behind a load balancer |
| No analytics | Event pipeline → warehouse → dashboards |
| Mock checkout | Stripe/payment provider integration |

### Production Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Retailer's Website / App                               │
│  ┌───────────────────────────┐                          │
│  │  Strivonex Widget (JS)    │  ← embedded <script>     │
│  └───────────┬───────────────┘                          │
└──────────────┼──────────────────────────────────────────┘
               │ HTTPS
               ▼
┌──────────────────────────────────────────────────────────┐
│  API Gateway (rate limiting, auth, routing)              │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Intent       │  │ Recommend    │  │ Upsell        │  │
│  │ Service      │  │ Service      │  │ Service        │  │
│  │ (LLM + NLP)  │  │ (Ranker)    │  │ (ML model)    │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬────────┘  │
│         │                 │                  │           │
│  ┌──────▼─────────────────▼──────────────────▼────────┐  │
│  │  Product Catalog DB    │  Event Stream (Kafka)     │  │
│  │  (per retailer)        │  → Analytics Warehouse    │  │
│  └────────────────────────┴───────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### The Key Insight

The demo proves that the **decision architecture** works: structured intent → filtered candidates → weighted ranking → complementary upsell. That pipeline is the same at 60 products or 60,000. What scales is the data sources and the intelligence of each step — not the flow itself.

The LLM doesn't replace the engine. It sits alongside it: the engine decides *what* to recommend, the LLM decides *how to say it*. That separation is what makes the system reliable, testable, and controllable — properties you need in production but can't get from a pure AI approach.
