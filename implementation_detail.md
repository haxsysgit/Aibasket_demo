# AI Basket Builder — Implementation Detail

## 1. What This Is

A working demo of an AI-powered shopping assistant. A customer tells it what they want in natural language, and the LLM browses the product catalog, picks the best-matching items, explains its reasoning, and handles multi-turn conversation — all within a validated pipeline that prevents hallucinations.

It runs across four store types — café, pub, bakery, corner shop — each with its own product catalog (71 items total). Switch the store dropdown and the entire experience changes: different products, different prompts, different context. The system prompt itself is dynamic — loaded from a YAML template and rendered per shop type.

The backend is a Python FastAPI server with an LLM-first recommendation flow (GPT-4o-mini). The frontend is Vue 3 with Tailwind CSS. There is no database, no authentication, and no real payment. The LLM receives the full product catalog for the selected store, picks products, and writes the response. A validation layer checks every product ID the LLM returns against the real catalog — hallucinated products are stripped before they reach the user. If the LLM is unavailable, the system falls back to a deterministic keyword-matching engine.

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
│  api.js — fetch('/api/chat')                     │
│  Prompt Transparency Panel (shows YAML + output) │
└──────────────┬───────────────────────────────────┘
               │ HTTP POST (JSON)
               ▼
┌──────────────────────────────────────────────────┐
│  FastAPI Backend (:8000)                         │
│                                                  │
│  POST /api/chat (main LLM-first endpoint)        │
│  POST /api/classify-intent                       │
│  POST /api/recommend                             │
│  POST /api/upsell                                │
│                                                  │
│  ┌────────────────────────────────────────────┐  │
│  │  LLM PATH (GPT-4o-mini)                   │  │
│  │                                            │  │
│  │  1. Load prompt YAML (recommend.yaml)      │  │
│  │  2. Render with {shop_type} substitution   │  │
│  │  3. Inject full product catalog            │  │
│  │  4. LLM picks products + writes response   │  │
│  │  5. Validation: check IDs against catalog  │  │
│  │  6. Deterministic upsell from curated pairs│  │
│  └────────────────────────────────────────────┘  │
│                                                  │
│  ┌────────────────────────────────────────────┐  │
│  │  FALLBACK PATH (no API key / LLM failure)  │  │
│  │  Keyword intent → filter → weighted rank   │  │
│  └────────────────────────────────────────────┘  │
│                                                  │
│  ┌────────────────────────────────────────────┐  │
│  │ products.json — 71 products, 4 stores      │  │
│  │ prompts/recommend.yaml — YAML template     │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

### Why This Split

The frontend handles presentation and user interaction. It knows nothing about products, ranking, or business logic. The backend handles all decisions. This separation means:

- The product catalog and ranking logic never reach the browser
- The API contract is clean — JSON in, JSON out
- Swapping the frontend (to a widget, mobile app, or chatbot) requires zero backend changes
- The prompt transparency panel shows the full YAML template, rendered prompt, and LLM output

---

## 3. Design Decisions

### 3.1 LLM-First Recommendations with Deterministic Fallback

The LLM (GPT-4o-mini) receives the **full product catalog** for the selected store and recommends products directly. It browses the catalog, matches on category/tags/dietary/taste/price/portion, picks 1-3 products, and explains its reasoning — all in a single API call.

This is deliberate. The product catalog is small enough (15-20 items per store) that the LLM can reason over every item. Passing the full catalog means the LLM doesn't need a separate filtering step — it sees everything and makes informed choices.

**Why not pure deterministic?** A keyword-matching engine can't understand "I'm hungover and need something greasy" or "something my vegan girlfriend would like". The LLM handles natural language nuance that deterministic rules can't.

**Why not pure LLM?** Without validation, the LLM could hallucinate products. The validation layer checks every product ID the LLM returns against the real catalog. Hallucinated IDs are stripped. If all IDs are fake, the system falls back to the deterministic engine — keyword matching + weighted scoring. The demo always works.

**The fallback engine** uses the same weighted scoring formula as before (65% customer intent, 35% business factors). It activates when `OPENAI_API_KEY` is missing or the LLM call fails.

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
│   ├── openai_client.py      # LLM-first: catalog recommendation + intent extraction
│   ├── prompts/
│   │   └── recommend.yaml    # YAML prompt template with {shop_type} substitution
│   └── simulated.py          # Static response templates (pre-LLM)
│
├── models/
│   └── schemas.py            # Core data models (Product, Intent, etc.)
│
├── data/
│   └── products.json         # 71 products across 4 store types
│
├── frontend/
│   ├── src/
│   │   ├── App.vue           # Main orchestrator — stage machine
│   │   ├── api.js            # HTTP client for chat + legacy endpoints
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
│   └── test_api.py           # 42 pytest tests (API, chat, validation, YAML prompts)
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

42 automated tests cover all endpoints, the chat flow, and the validation layer:

- **Intent classification** — light lunch, quick snack, vegan request, budget signal, vague input
- **Recommendations** — correct count per behaviour, clarification logic, required fields, category filtering
- **Store isolation** — pub products never appear in café results and vice versa
- **Upsell** — returns complementary product, excludes basket items, handles invalid IDs
- **Multi-turn chat** — basic chat, response shape, history handling, max turns (4), basket awareness, clarification on first turn only, empty messages
- **Validation layer** — intent stripping (bad categories/preferences/modifiers/dietary/behaviour), response text rejection (empty, too short, too long), clarification sanitisation
- **Recommendation validation** — hallucinated product IDs stripped, all-hallucinated returns None, limits to 3 products, clarification pass-through
- **YAML prompt** — template loads correctly, `{shop_type}` substitution works per store type, rendered prompts contain correct shop context
- **Catalog formatting** — product catalog renders with all fields (id, name, price, dietary, upsells)

```bash
uv run pytest tests/ -v   # 42 passed
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

### How It Works

The LLM (GPT-4o-mini) is the **primary recommendation engine**. On every `/api/chat` request:

1. The backend loads the store-filtered product catalog (15-20 items)
2. The YAML prompt template (`llm/prompts/recommend.yaml`) is loaded and rendered with the customer's `{shop_type}` — substituting role, context, and instructions
3. The rendered YAML system prompt + the product catalog + the user's message are sent to the LLM
4. The LLM browses the catalog, picks 1-3 products by ID, writes a reasoning string, and composes a natural response
5. The validation layer checks every returned product ID against the real catalog
6. Hallucinated IDs are stripped. If zero valid IDs remain, the system falls back to the deterministic engine
7. Deterministic upsell logic checks the first recommended product's curated pairs

### YAML Prompt Architecture

The system prompt is defined in `llm/prompts/recommend.yaml` — not as a Python string constant. This is deliberate:

- **Structured YAML > unstructured prose.** LLMs parse structured input more reliably. Sections like `product_selection`, `message_rules`, `multi_turn`, and `clarification` are clearly delineated.
- **Dynamic `{shop_type}` substitution.** The role field reads `"You are an AI shopping assistant for a {shop_type}."` At runtime, `{shop_type}` becomes "café", "pub", "bakery", or "corner shop".
- **Per-store context injection.** The YAML contains a `shop_context` map with descriptions for each store type. Only the relevant one is injected:
  - *café*: "A casual café serving fresh food, hot drinks, and light bites..."
  - *pub*: "A traditional British pub serving hearty meals, bar snacks, and drinks..."
  - *bakery*: "A high-street bakery selling fresh bread, pastries, cakes..."
  - *corner shop*: "A convenience store selling prepacked food, drinks, and snacks..."
- **Editable without code changes.** Prompt tuning is a YAML edit, not a Python deploy.
- **Visible in the UI.** The prompt transparency panel shows both the raw YAML template and the rendered version with shop type substituted.

### What the LLM Sees

The user prompt sent to the model contains:

```
Customer said: "I want something healthy and light"

--- PRODUCT CATALOG (20 items) ---
- id:cafe_001 | Flat White | £3.40 | cat:drink | tags:[classic, hot, milk] | dietary:[vegetarian] | ...
- id:cafe_002 | Avocado Toast | £7.50 | cat:lunch | tags:[healthy, light, fresh] | dietary:[vegan] | ...
... (all store products)

--- ALREADY IN BASKET (do not recommend these) ---
  - Flat White (id:cafe_001)
```

The LLM returns structured JSON:

```json
{
  "recommended_ids": ["cafe_002", "cafe_016"],
  "reasoning": "Avocado Toast is light, fresh, and vegan. The Acai Bowl is a healthy option with fruit.",
  "message": "The Avocado Toast would be perfect — it's light, fresh, and only £7.50. If you're after something a bit different, the Acai Bowl is packed with fruit and is naturally vegan too.",
  "needs_clarification": false,
  "clarification_question": null
}
```

### Validation Layer

Every LLM response passes through `validate_recommendation()`:

| Check | Action |
|---|---|
| Product ID not in catalog | Stripped from results |
| All product IDs hallucinated | Returns `None` → deterministic fallback |
| More than 3 products | Truncated to 3 |
| Message too short (<10 chars) | Set to `None` → static template used |
| Message too long (>800 chars) | Truncated at last sentence boundary |
| Clarification question too short/long | Rejected |

This means the LLM can never surface a product that doesn't exist in the real catalog. The worst case is a fallback to the deterministic engine — the demo never breaks.

### Multi-Turn Conversation

The `/api/chat` endpoint supports up to 4 conversation turns. On each follow-up:

- The full conversation history is sent to the LLM alongside the product catalog
- The LLM sees what was previously recommended and can adjust
- **Refinements** ("something cheaper", "make it vegan") → LLM adjusts picks from the same catalog
- **Pivots** ("forget that, I want a drink") → LLM starts fresh from a different category
- Basket awareness prevents re-recommending items already added

### Fallback Behaviour

If `OPENAI_API_KEY` is missing or any LLM call fails:

- The deterministic engine activates: keyword-based intent extraction → category/dietary filtering → weighted scoring
- Clarification uses hardcoded questions per category
- Response uses static template strings
- A warning is logged — no error shown to the user
- The demo works identically, just without LLM reasoning

---

## 11. How This Becomes Production

This demo is a proof of concept. Here's what changes — and what doesn't — when moving to production.

### What Stays the Same

- **The LLM-first recommendation approach.** Passing the product catalog to the LLM works well for small-to-medium catalogs. The architecture scales with prompt engineering and model improvements.
- **YAML prompt templates.** Structured prompts with dynamic substitution. In production, prompts become versioned and A/B tested.
- **Validation layer.** Every LLM output must be checked against the real catalog. This pattern is essential at any scale.
- **Store isolation.** Products partitioned by store type. In production, each store would have its own catalog in a database.
- **The API contract.** JSON in/out. This interface works for a widget, mobile app, or chatbot.

### What Changes

| Demo | Production |
|---|---|
| `products.json` (71 items) | PostgreSQL or Redis with thousands of products per store |
| Full catalog in prompt | RAG retrieval for large catalogs (embed + retrieve top-N, then pass to LLM) |
| GPT-4o-mini | Fine-tuned model or GPT-4 for higher accuracy |
| Single YAML prompt | Versioned prompts, A/B tested per store type |
| Static upsell pairs | ML model trained on purchase history (association rules, collaborative filtering) |
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

The demo proves that an **LLM can be a reliable recommendation engine** when you give it the right structure:

1. **Ground it in real data.** The LLM sees the actual product catalog — not a vague instruction to "recommend food". It can only pick from what exists.
2. **Validate everything.** The validation layer catches hallucinations before they reach the user. The worst case is a fallback to deterministic logic — the demo never breaks.
3. **Structure the prompt.** YAML templates with dynamic substitution produce more consistent LLM behaviour than unstructured prose. Each shop type gets its own context, tone, and product knowledge.
4. **Keep an escape hatch.** The deterministic engine sits behind the LLM. No API key, bad response, rate limit? The system still works.

This architecture scales: for larger catalogs, swap "full catalog in prompt" for RAG retrieval (embed products → retrieve top-N → pass to LLM). The prompt template, validation layer, and multi-turn conversation all remain the same.
