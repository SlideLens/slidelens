# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this directory.

## What this directory is

This is the **application code** for **SlideLens** — a web platform where a user uploads a presentation (Дека, PPTX/PDF), optionally a pitch recording and an Excel of the underlying data, and a multimodal agent returns a senior-designer-level review: annotated slide problems, honesty checks on charts, a "speech ↔ slides" cross-check, and an auto-fixed copy of the file.

Product specs, ADRs, OpenAPI, backlog, and task tickets live in [`../achitecture/`](../achitecture/). This directory is the implementation that must follow those specs. Terminology is binding from [`../achitecture/CONTEXT.md`](../achitecture/CONTEXT.md) (e.g. always «Разбор» never «анализ/аудит»; «Находка» never «замечание/issue»; «Дека» never «презентация» as a field name).

## Spec map (read before inventing)

Start from [`../achitecture/README.md`](../achitecture/README.md). When changing behavior, check the matching docs:

1. [`../achitecture/CONTEXT.md`](../achitecture/CONTEXT.md) — glossary (binding)
2. [`../achitecture/docs/PRD.md`](../achitecture/docs/PRD.md) — user stories, MVP scope
3. [`../achitecture/api/openapi.yaml`](../achitecture/api/openapi.yaml) — REST contract (**source of truth**); [`../achitecture/docs/API.md`](../achitecture/docs/API.md) is the prose companion
4. [`../achitecture/docs/PROMPTS.md`](../achitecture/docs/PROMPTS.md) — analyzer prompts / schemas
5. [`../achitecture/docs/DEPLOY.md`](../achitecture/docs/DEPLOY.md) — Docker / VPS / Caddy
6. [`../achitecture/docs/DESIGN.md`](../achitecture/docs/DESIGN.md) — UI (Report page is the storefront)
7. [`../achitecture/adr/`](../achitecture/adr/) — architectural decisions (below)
8. [`../achitecture/tasks/`](../achitecture/tasks/) — implementation tickets

When OpenAPI and code disagree, **fix the code or regenerate types** — do not silently diverge. Frontend types: `npm run gen:api` in `frontend/` (reads `../achitecture/api/openapi.yaml` → `src/api/types.gen.ts`). Never hand-edit `types.gen.ts`.

## Commands

### Docker (local + prod: Caddy + app + worker + db + redis)

```bash
cp backend/.env.example backend/.env   # SITE_ADDRESS=:80 locally; domain in prod
docker compose --env-file backend/.env up -d --build
docker compose --env-file backend/.env exec app alembic upgrade head
# SPA+API: http://localhost/   health: http://localhost:8000/health
```

Single env file: `backend/.env`. SPA is baked into the image; Caddy is the
public entrypoint (`deploy/Caddyfile`). For frontend HMR:
`cd frontend && npm run dev` against `:8000` (set
`CORS_ALLOW_ORIGINS=http://localhost:5173`). Observability configs under
`deploy/` are optional / not wired into compose for MVP.

### Backend (local, without Docker)

```bash
cd backend
uv sync --group dev
uv run pytest
uv run ruff check .
uv run alembic upgrade head   # needs DB_* + required ENV
uv run python -m core.run --deck path/to/deck.pdf --out ./out
uv run python tests/golden/eval.py --out ./golden-run --prompt-version v1
```

### Frontend

```bash
cd frontend
npm install
npm run gen:api
npm run dev
npm run build
npm run lint
npm test
```

## Repository layout

Exactly two top-level modules — **`backend/`** and **`frontend/`**:

- **`backend/`** — Python project (uv + `pyproject.toml` + `uv.lock`). Packages:
  - `app/` — web layer: `main.py`, `config.py`, `db.py`, `deps.py`, `security.py`, `auth.py`, `api/v1/`, `services/`, `schemas/`, `models/`, `seed.py`
  - `core/` — pure review library: `run.py`, `context.py`, `schemas.py`, `llm/`, `ingest.py`, `transcribe.py`, `analyzers/`, `aggregate.py`, `annotate.py`, `fix.py`, `report.py`, `prompts/` (versioned md)
  - `worker/` — `tasks.py`: the **only** bridge between `app` and `core` (`process_review`, cleanup)
  - `observability/` — structlog / Sentry / metrics setup
  - `migrations/` — Alembic
  - `tests/` — `unit/` · `integration/` · `golden/`
  - `templates/email/` — app-layer email HTML (verification, report-ready)
- **`frontend/`** — React / Vite / TS SPA: `src/pages/`, `components/`, `api/`, `hooks/`, `auth/`, `lib/`
- **This directory root** — `Dockerfile`, `docker-compose.yml`, `README.md`, this file (`cp backend/.env.example backend/.env`)

Python import names are `app.*`, `core.*`, `worker.*`, `observability.*` (package root is `backend/`); only filesystem paths carry the `backend/` prefix.

## Core domain rules (don't relitigate without an ADR)

- **`backend/core/` never imports `backend/app/`** and never touches the DB. Wire them only in `backend/worker/tasks.py`. Core must stay runnable via `python -m core.run` without web/DB. ([ADR 0001](../achitecture/adr/0001-pipeline-pure-library.md))
- **Multi-analyzer, graceful degradation.** Independent analyzers on `BaseAnalyzer` (`SlideAnalyzer`, `ZoomAgent`, `DeckAnalyzer`, `ChartChecker`, `CrossModalAnalyzer`). A failing analyzer is skipped and logged; the Review continues — partial report beats `failed`. ZoomAgent: screening → crop ×2 → analyze, capped (cost). ([ADR 0002](../achitecture/adr/0002-vlm-pipeline-hybrid-analyzers.md))
- **All VLM calls go through `LLMClient`.** Do not call provider SDKs from analyzers/routes. Prompts live as versioned md in `backend/core/prompts/` (frontmatter `version`, `tier`); attach version to Langfuse traces.
- **Review is async.** `POST /reviews` → `202 queued`; ARQ + Redis worker runs the pipeline; frontend polls; email on `done`. Not a blocking HTTP request. ([ADR 0003](../achitecture/adr/0003-async-review-worker.md))
- **Shared Finding taxonomy.** `Category` / `Severity` / `Finding` in `backend/core/schemas.py` are the seam across core, DB (`FindingRow`), API, and UI. `bbox` is normalized `0..1`. Converter lives in one place (`app/services/finding_mapper.py`).
- **Auto-fix is narrow.** `PptxFixer`: only `MinFontSizeRule` / `ContrastRule` / `AlignmentRule` on `auto_fixable` findings; no slide re-layout. ([ADR 0006](../achitecture/adr/0006-pptx-autofix-strategy.md))
- **Cost per Review is first-class.** Langfuse from day one; three observability layers (product `Event` / Langfuse / Sentry+metrics). ([ADR 0007](../achitecture/adr/0007-three-layer-observability.md))

## ADRs

- [0001](../achitecture/adr/0001-pipeline-pure-library.md) — `core/` pure library
- [0002](../achitecture/adr/0002-vlm-pipeline-hybrid-analyzers.md) — hybrid analyzer pipeline + zoom
- [0003](../achitecture/adr/0003-async-review-worker.md) — ARQ worker
- [0004](../achitecture/adr/0004-stack-fastapi-react.md) — FastAPI + React stack, single-domain Caddy
- [0005](../achitecture/adr/0005-crossmodal-delivery-analysis.md) — speech↔slides + delivery; rehearsal = later phase
- [0006](../achitecture/adr/0006-pptx-autofix-strategy.md) — minimal autofix strategies
- [0007](../achitecture/adr/0007-three-layer-observability.md) — observability layers + unit economics

New decisions go under `../achitecture/adr/` (`NNNN-slug.md`); do not edit past ADRs — supersede them.

## Stack (as implemented)

FastAPI (`/api/v1`, JWT) + React/Vite/TS/Tailwind/TanStack Query. PostgreSQL + SQLAlchemy 2.0 async + Alembic. Worker: ARQ + Redis (same image as `app`). Rendering: LibreOffice + pdf2image (RU fonts in Docker image). VLM via `LLMClient` (OpenAI-compatible). faster-whisper, python-pptx, Pillow, weasyprint. Compose: `caddy` / `app` / `worker` / `db` / `redis` (SPA baked into image, one domain).

## Coding conventions (this codebase)

- **Pydantic, not dataclasses** for project models / settings (`BaseModel`, `BaseSettings`, `ConfigDict(frozen=True)`). Exception: SQLAlchemy ORM mapped classes.
- **Async-first I/O** in `backend/`: `async def` routes/deps, `AsyncSession`, `await` LLM/HTTP/Redis/SMTP; no `time.sleep` on the event loop; use `asyncio.to_thread` only for unavoidable sync libs.
- **Imports at module top** in `backend/core/` (no function-scoped imports). No `try/except` around imports — missing deps must fail loudly.
- Keep `Category` / `Severity` / `Finding` in sync across `core/schemas.py`, ORM, OpenAPI, and UI labels when you change them.
- Prefer extending existing modules over new parallel abstractions. Do not add docs/markdown the user did not ask for.
