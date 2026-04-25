# 🛒 AI Basket Builder

An AI-powered shopping assistant that recommends products through guided conversation. Supports multiple store types (café, pub, bakery, corner shop) with adaptive recommendations, single-question clarification, and complementary upsells.

**Live demo**: [ai-basket-builder.netlify.app](https://ai-basket-builder.netlify.app)

## Architecture

- **Backend**: Python + FastAPI — hybrid LLM + deterministic engine
- **LLM Layer**: OpenAI GPT-4o-mini — intent extraction from free text + natural response generation
- **Decision Engine**: Deterministic — filtering, weighted ranking, upsell selection (no LLM involved)
- **Frontend**: Vue 3 + Tailwind CSS — dark-themed guided shopping flow with AI reasoning panel
- **Data**: 60+ products across 4 store types with intent signals, dietary info, and business metrics

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
uv run pytest tests/ -v   # 21 tests
```

## How It Works

1. Customer picks a store type and states what they want (chips or free text)
2. **LLM** extracts structured intent from free text (or keyword fallback if no API key)
3. **Deterministic engine** filters by store → category → dietary, then ranks by weighted scoring
4. **Deterministic engine** selects top N products (N adapts to behaviour: 1 for rushed, 3 for browsing)
5. **Deterministic engine** picks a complementary upsell from curated pairs
6. **LLM** generates a natural response mentioning only the engine-selected products
7. Customer sees products + AI message + optional "Show AI reasoning" panel
8. Simulated checkout completes the flow

> The LLM never chooses, ranks, or invents products. It only understands and speaks.

## Project Structure

```
api/          FastAPI endpoints (recommend, upsell, classify-intent, chat)
engine/       Deterministic: intent extraction, filtering, ranking, upsell
llm/          OpenAI integration: intent extraction + response generation
models/       Pydantic schemas (Product, Intent, API models)
data/         Product catalog (60+ items, 4 store types)
frontend/     Vue 3 + Tailwind CSS app with AI reasoning panel
tests/        21 automated API tests
```

## Key Design Decisions

- **Hybrid architecture** — LLM for understanding + speaking, deterministic engine for all decisions
- **LLM never picks products** — the engine decides what, the LLM decides how to say it
- **Graceful fallback** — no API key? Demo works with keyword matching and static templates
- **Prompt transparency** — UI shows exact prompts, model outputs, and decision flow
- **Store isolation** — products partitioned by store type at the API layer
- **Behaviour-adaptive** — rushed users see 1 result, browsers see 3
- **Weighted ranking** — 65% customer intent, 35% business factors (popularity, conversion, margin)
- **Curated upsells** — explicit product pairings with social proof framing

See [implementation_detail.md](implementation_detail.md) for the full technical breakdown and production roadmap.

## Stack

- Python 3.12, FastAPI, Pydantic
- OpenAI GPT-4o-mini (optional — falls back to deterministic)
- Vue 3, Vite 8, Tailwind CSS v4
- uv (package management)
- pytest (testing)
