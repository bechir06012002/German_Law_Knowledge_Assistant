<div align="center">

# ⚖️ Judges Said

**AI-powered German labour-law precedent explorer.**

Describe an employment situation in German or English and retrieve relevant German court decisions with their **court, Aktenzeichen, date, and cited laws**.

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python\&logoColor=white)](#)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi\&logoColor=white)](#)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react\&logoColor=white)](#)
[![OpenAI](https://img.shields.io/badge/AI-OpenAI%20API-412991?logo=openai\&logoColor=white)](#)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-4169E1?logo=postgresql\&logoColor=white)](#)
[![License](https://img.shields.io/badge/License-MIT-yellow)](#)

**[🌐 Live App](https://judges-said-l49g.onrender.com)**

</div>

---

## 📖 Table of Contents

* [✨ Features](#-features)
* [🧠 How It Works](#-how-it-works)
* [📚 Corpus](#-corpus)
* [🛠️ Tech Stack](#️-tech-stack)
* [📁 Project Structure](#-project-structure)
* [⚙️ Getting Started](#️-getting-started)
* [⚖️ Legal Boundaries](#️-legal-boundaries)
* [🎬 Demo](#-demo)

---

## ✨ Features

|                              |                                                                     |
| ---------------------------- | ------------------------------------------------------------------- |
| 🔎 **Hybrid Retrieval**      | Combines semantic search with pgvector and German lexical search    |
| 🌍 **Bilingual Queries**     | Search in both German and English                                   |
| 📑 **Grounded Answers**      | Claims are verified against retrieved court sources                 |
| 📌 **Evidence Preservation** | Court names, Aktenzeichen, dates, and § references remain unchanged |
| 🛡️ **Compliance by Design** | Outcome predictions and person searches are rejected                |

> ⚖️ **Precedent, not predictions.** The system provides evidence from real court decisions and does not predict outcomes.

---

## 🧠 How It Works

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

The system retrieves relevant legal sources, validates the generated claims against them, and preserves the original court references and legal citations.

---

## 📚 Corpus

The system uses labour-law decisions and statutes from **Open Legal Data**:

| Dataset              |      Count |
| -------------------- | ---------: |
| 🏛️ Court decisions  |  **1,070** |
| 📜 Statute sections  |  **5,680** |
| 🔍 Searchable chunks | **41,425** |

---

## 🛠️ Tech Stack

| Layer      | Technology                               |
| ---------- | ---------------------------------------- |
| Backend    | Python 3.12, FastAPI, PydanticAI         |
| LLM        | OpenAI API                               |
| Embeddings | `multilingual-e5-base` locally           |
| Database   | Supabase PostgreSQL + pgvector           |
| Frontend   | React 19, TypeScript, Vite, Tailwind CSS |
| Auth       | Supabase Auth                            |
| Deployment | Docker, Render, Hetzner                  |

---

## 📁 Project Structure

```text
backend/
├── app/
├── alembic/
├── tests/
└── .env.example

frontend/
└── src/
```

---

## ⚙️ Getting Started

### Backend

```bash
cd backend
cp .env.example .env

uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

### Tests

```bash
cd backend
uv run pytest
```

> ⚠️ Configure the required environment variables before running the application.

---

## ⚖️ Legal Boundaries

The application provides **legal information, not legal advice**.

It surfaces comparable court decisions but does not assess individual cases or predict outcomes.

**Non-goals:**

* ❌ Legal advice
* ❌ Outcome prediction
* ❌ Person searches
* ❌ Court-portal crawling
* ❌ Automated case assessment

---

## 🎬 Demo

https://github.com/user-attachments/assets/2d5cdd74-fc47-4f59-b494-bd001cca3fee

```

<div align="center">

**⚖️ Precedent, not predictions.**

**[🌐 Try the Live App](https://judges-said-l49g.onrender.com)**

</div>
```
