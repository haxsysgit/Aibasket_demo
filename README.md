# 🛒 AI Basket Builder

An AI-powered shopping assistant that recommends products through guided conversation. Supports multiple store types (café, pub, bakery, corner shop) with adaptive recommendations, single-question clarification, and complementary upsells.

**Live demo**: [ai-basket-builder.onrender.com](https://ai-basket-builder.onrender.com)

## Architecture

- **Backend**: Python + FastAPI — hybrid LLM + deterministic engine
- **LLM Layer**: OpenAI GPT-4o-mini — multi-turn intent extraction, contextual clarification, product reasoning, basket-aware responses
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
uv run pytest tests/ -v   # 36 tests
```

## How It Works

1. Customer picks a store type and states what they want (chips or free text)
2. **LLM** extracts structured intent from free text, with multi-turn awareness (or keyword fallback)
3. If request is vague, **LLM** generates a contextual clarification question
4. **Deterministic engine** filters by store → category → dietary, then ranks by weighted scoring
5. **Deterministic engine** selects top N products (N adapts to behaviour: 1 for rushed, 3 for browsing)
6. **Deterministic engine** picks a complementary upsell from curated pairs
7. **LLM** generates a basket-aware response with per-product reasoning and natural upsell phrasing
8. Customer can refine, pivot, or follow up (up to 4 turns)
9. All LLM outputs are validated — hallucinated values are stripped before they reach the UI

> The LLM never chooses, ranks, or invents products. It only understands and speaks.

## Project Structure

```
api/          FastAPI endpoints (recommend, upsell, classify-intent, chat)
engine/       Deterministic: intent extraction, filtering, ranking, upsell
llm/          OpenAI integration: intent extraction + response generation
models/       Pydantic schemas (Product, Intent, API models)
data/         Product catalog (60+ items, 4 store types)
frontend/     Vue 3 + Tailwind CSS app with AI reasoning panel
tests/        36 automated tests (API, chat multi-turn, validation)
```

## Key Design Decisions

- **Hybrid architecture** — LLM for understanding + speaking, deterministic engine for all decisions
- **LLM never picks products** — the engine decides what, the LLM decides how to say it
- **Multi-turn conversation** — up to 4 turns: refine, pivot, or explore alternatives naturally
- **Validation layer** — every LLM output is validated against allowed value sets before use
- **Graceful fallback** — no API key? Demo works with keyword matching and static templates
- **Prompt transparency** — UI shows exact prompts, model outputs, and decision flow
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
