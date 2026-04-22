# 🛒 AI Basket Builder

An AI-powered shopping assistant that recommends products through guided conversation. Supports multiple store types (café, pub, bakery, corner shop) with adaptive recommendations, single-question clarification, and complementary upsells.

**Live demo**: [ai-basket-builder.netlify.app](https://ai-basket-builder.netlify.app)

## Architecture

- **Backend**: Python + FastAPI — intent extraction, product filtering, weighted ranking, upsell logic
- **Frontend**: Vue 3 + Tailwind CSS — dark-themed guided shopping flow
- **Data**: 60+ products across 4 store types with intent signals, dietary info, and business metrics

## Quick Start

### Backend

```bash
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
uv run pytest tests/ -v   # 21 tests
```

## How It Works

1. Customer picks a store type and states what they want (chips or free text)
2. System classifies intent → category, preferences, modifiers, dietary, behaviour
3. Products filtered by store → category → dietary, then ranked by weighted scoring
4. Top N products returned (N adapts to behaviour: 1 for rushed, 3 for browsing)
5. Customer adds to basket → upsell engine suggests a complementary item
6. Simulated checkout completes the flow

## Project Structure

```
api/          FastAPI endpoints (recommend, upsell, classify-intent)
engine/       Intent extraction, filtering, ranking, upsell logic
models/       Pydantic schemas (Product, Intent, API models)
data/         Product catalog (60+ items, 4 store types)
frontend/     Vue 3 + Tailwind CSS app
tests/        21 automated API tests
```

## Key Design Decisions

- **Deterministic engine** — weighted scoring formula, not LLM picks. Same input = same output.
- **Store isolation** — products partitioned by store type at the API layer
- **Behaviour-adaptive** — rushed users see 1 result, browsers see 3
- **Single clarification** — one question max per interaction
- **Weighted ranking** — 65% customer intent, 35% business factors (popularity, conversion, margin)
- **Curated upsells** — explicit product pairings with social proof framing

See [implementation_detail.md](implementation_detail.md) for the full technical breakdown and production roadmap.

## Stack

- Python 3.12, FastAPI, Pydantic
- Vue 3, Vite 8, Tailwind CSS v4
- uv (package management)
- pytest (testing)
