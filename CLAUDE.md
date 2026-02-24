# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered multi-tenant web application for German public procurement (Vergabe) tender document management. Two major features:

- **3.2 Project Management Tool** — Upload tenders, AI-generated to-do lists, track completion, dashboard
- **3.1 Tender Fill Tool** — Knowledge database from filled tenders, AI-powered fill suggestions

**Stack:** Next.js frontend, Flask API backend, Supabase (PostgreSQL + Auth + Storage)

## Commands

```bash
# CLI (still works standalone)
python tender_manager.py path/to/tender --scan
python tender_manager.py path/to/tender --process [--full]
python tender_manager.py path/to/tender --todo / --critical / --actionable
python tender_manager.py path/to/tender --export
python visualize_graph.py path/to/tender --html --open

# Backend (Flask)
cd backend && pip install -r requirements.txt
python run.py                        # Dev server on :5001

# Frontend (Next.js — requires Node 22+)
cd frontend && npm install
npm run dev                          # Dev server on :3000
npm run build                        # Production build

# Supabase (local)
supabase start                       # Starts local Supabase
supabase db reset                    # Re-apply migrations
supabase migration new <name>        # Create new migration

# Docker
docker-compose up                    # All services
```

## Architecture

```
Next.js (:3000)  →  Flask API (:5001)  →  Supabase (PostgreSQL + Auth + Storage)
    ↓                                           ↑
    └───────────── (auth, realtime, CRUD) ──────┘
```

### Core Processing Pipeline (core/ — shared by CLI and web backend)

1. **Scan** — `DocumentReader` extracts text from PDF, DOCX, XLSX, XML, GAEB, etc.
2. **Extract** — `RequirementExtractor` sends text to LLM with flattened JSON schema
3. **Graph Build** — Items become `Node` objects; relationships become `Edge` objects
4. **To-Do Generation** — `TodoGenerator` creates prioritized, categorized action items
5. **Visualization** — Mermaid diagrams with zoom/pan

### Module Layout

**Shared modules (root):**
- `core/` — Graph, document reader, extractor, todo generator, logging
- `ai/` — OpenRouter LLM client (reads `OPENROUTER_API_KEY` from env)
- `tender_manager.py` — CLI entry point
- `visualize_graph.py` — Mermaid HTML report generator

**Backend (`backend/`):**
- `backend/run.py` — Adds project root to sys.path so `core/` and `ai/` resolve
- `backend/app/__init__.py` — Flask app factory
- `backend/app/config.py` — Settings from env vars
- `backend/app/routes/` — Flask blueprints (projects, documents, processing, graph, todos)
- `backend/app/services/graph_service.py` — Adapter: `RequirementGraph` ↔ Supabase DB
- `backend/app/services/extraction_service.py` — Wraps core extractor for web
- `backend/app/middleware/auth.py` — Supabase JWT verification

**Frontend (`frontend/`):**
- `frontend/src/app/` — Next.js App Router pages
- `frontend/src/lib/api.ts` — Flask API client with typed endpoints
- `frontend/src/lib/supabase.ts` — Supabase browser client

**Database (`supabase/`):**
- `supabase/migrations/` — SQL migrations
- Tables: organizations, org_members, projects, documents, nodes, edges, processing_jobs, knowledge_entries, fill_suggestions
- Row-Level Security for multi-tenancy

### Data Model

**Node types:** DOCUMENT, REQUIREMENT, CONDITION, CHECKBOX, SIGNATURE, FIELD, ATTACHMENT, DEADLINE
**Edge types:** REQUIRES, REQUIRED_BY, CONDITIONAL_ON, TRIGGERS, PART_OF, REFERENCES, MUTUALLY_EXCLUSIVE, DEPENDS_ON
**Completion:** NOT_STARTED → IN_PROGRESS → COMPLETED (also NOT_APPLICABLE, BLOCKED)

### Key Design Patterns

- **Graph adapter:** `GraphService.load_graph()` builds an in-memory `RequirementGraph` from DB rows. `save_graph()` writes it back. Core modules never touch the DB directly.
- **Background processing:** Flask routes start extraction in a background thread. `ProcessingJob` table tracks progress. Frontend polls via SSE.
- **Multi-tenancy:** Supabase RLS policies scope all data by organization. Auth middleware extracts org_id from JWT.

## Conventions

- API key in env var `OPENROUTER_API_KEY` — never hardcode
- Logging: `logger = get_logger("module_name")`
- German-first: LLM prompts target German tender vocabulary
- Document extraction is best-effort: logs warnings, continues on failure
