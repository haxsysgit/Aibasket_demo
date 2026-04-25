# 🛒 AI Basket Builder

An AI-powered shopping assistant that recommends products through guided conversation. Supports multiple store types (café, pub, bakery, corner shop) with adaptive recommendations, single-question clarification, and complementary upsells.

**Live demo**: [ai-basket-builder.onrender.com](https://ai-basket-builder.onrender.com)

## Architecture

- **Backend**: Python + FastAPI — hybrid LLM + deterministic engine
- **LLM Layer**: OpenAI GPT-4o-mini — receives full product catalog, picks products, explains reasoning, handles multi-turn conversation
- **Decision Engine**: Deterministic — filtering, weighted ranking, upsell selection (no LLM involved)
- **Frontend**: Vue 3 + Tailwind CSS — dark-themed guided shopping flow with AI reasoning panel
- **Data**: 71 products across 4 store types with intent signals, dietary info, and business metrics

## Quick Start

### Backend

```bash
cp .env.example .env
# Add your OPENAI_API_KEY to .env (optional — demo works without it)

uv sync
uv run uvicorn api.main:app --reload
# → http://localhost:8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

### Tests

```bash
uv run pytest tests/ -v   # 41 tests
```

## How It Works

1. Customer picks a store type and states what they want (chips or free text)
2. Backend sends the **full product catalog** (store-filtered) to the LLM along with the user's message
3. **LLM browses the catalog**, picks 1-3 best-matching products, and explains its reasoning
4. **Validation layer** checks every product ID the LLM returns exists in the real catalog — hallucinated products are stripped
5. **Deterministic engine** picks a complementary upsell from curated product pairs
6. **LLM** writes a natural, basket-aware response with per-product reasoning
7. Customer can refine, pivot, or follow up (up to 4 turns)
8. If LLM is unavailable → **deterministic fallback** (keyword matching + weighted scoring)

> The LLM recommends from real product data. Every recommendation is validated against the catalog.

## Project Structure

```
api/          FastAPI endpoints (recommend, upsell, classify-intent, chat)
engine/       Deterministic: intent extraction, filtering, ranking, upsell
llm/          OpenAI integration: intent extraction + response generation
models/       Pydantic schemas (Product, Intent, API models)
data/         Product catalog (71 items, 4 store types)
frontend/     Vue 3 + Tailwind CSS app with AI reasoning panel
tests/        41 automated tests (API, chat, validation, catalog formatting)
```

## Key Design Decisions

- **LLM-first architecture** — LLM receives product catalog, picks products, and explains reasoning
- **Validated recommendations** — every product ID the LLM returns is checked against the real catalog
- **Multi-turn conversation** — up to 4 turns: refine, pivot, or explore alternatives naturally
- **Deterministic fallback** — no API key? Demo works with keyword matching and weighted scoring
- **Prompt transparency** — UI shows exact prompts, product catalog sent to model, and decision flow
- **Basket-aware** — LLM knows what's in the basket and adjusts responses accordingly
- **Store isolation** — products partitioned by store type at the API layer
- **Behaviour-adaptive** — rushed users see 1 result, browsers see 3
- **Weighted ranking** — 65% customer intent, 35% business factors (popularity, conversion, margin)
- **Curated upsells** — explicit product pairings with natural social proof phrasing

See [implementation_detail.md](implementation_detail.md) for the full technical breakdown and production roadmap.

## Stack

- Python 3.12, FastAPI, Pydantic
- OpenAI GPT-4o-mini (optional — falls back to deterministic)
- Vue 3, Vite 8, Tailwind CSS v4
- uv (package management)
- pytest (testing)
