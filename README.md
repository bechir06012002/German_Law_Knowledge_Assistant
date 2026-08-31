# Judges Said

An AI-powered **German labour-law precedent explorer**. Describe an employment situation in German or English and retrieve relevant German court decisions with their **court, Aktenzeichen, date, and cited laws**.

**Live:** [judges-said-l49g.onrender.com](https://judges-said-l49g.onrender.com)

> **Precedent, not predictions.** The system only provides evidence from real court decisions and refuses outcome predictions.

## Features

* **Hybrid retrieval** — semantic search with pgvector + German lexical search
* **Bilingual queries** — German and English
* **Grounded answers** — claims are verified against retrieved court sources
* **Evidence preservation** — court names, Aktenzeichen, dates, and § references remain unchanged
* **Compliance by design** — outcome predictions and person searches are rejected

## Tech Stack

| Layer      | Technology                               |
| ---------- | ---------------------------------------- |
| Backend    | Python 3.12, FastAPI, PydanticAI         |
| LLM        | OpenAI API                               |
| Embeddings | `multilingual-e5-base` locally           |
| Database   | Supabase PostgreSQL + pgvector           |
| Frontend   | React 19, TypeScript, Vite, Tailwind CSS |
| Auth       | Supabase Auth                            |
| Deployment | Docker, Render, Hetzner                  |

## Architecture

```text
User
 │
 ▼
React Frontend
 │
 ▼
FastAPI Backend
 │
 ├──► Hybrid Retrieval
 │      ├── pgvector
 │      └── Full-text Search
 │
 ├──► Grounding Validator
 │
 ▼
OpenAI
 │
 ▼
Cited Court Decisions
```

## Corpus

The system uses labour-law decisions and statutes from **Open Legal Data**:

* **1,070** court decisions
* **5,680** statute sections
* **41,425** searchable chunks

## Running Locally

```bash
cd backend
cp .env.example .env

uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

```bash
cd frontend
pnpm install
pnpm dev
```

Run tests with:

```bash
cd backend
uv run pytest
```

## Legal Boundaries

The application provides **legal information, not legal advice**. It surfaces comparable court decisions but does not assess individual cases or predict outcomes.

**Non-goals:** legal advice, outcome prediction, person searches, court-portal crawling, and automated case assessment.

## Demo
https://github.com/user-attachments/assets/2d5cdd74-fc47-4f59-b494-bd001cca3fee
