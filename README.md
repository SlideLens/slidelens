# SlideLens

Web platform for senior-designer-level presentation reviews (Дека → Разбор).

## Layout

- `backend/` — Python project (uv): `app` (HTTP/DB), `core` (pure review library), `worker` (bridge)
- `frontend/` — React / Vite / TypeScript SPA (scaffold)

## Architecture

Product specs, ADRs, OpenAPI, and backlog live in [`../achitecture/`](../achitecture/). Start with [`../achitecture/README.md`](../achitecture/README.md) and [`../achitecture/CONTEXT.md`](../achitecture/CONTEXT.md).

## Docker quickstart

One compose file for local MVP and production: Caddy + `app` + `worker` +
Postgres + Redis. SPA is baked into the image and served by FastAPI; Caddy is
the public entrypoint (LibreOffice / ffmpeg / RU fonts included — no host
toolchain needed).

```bash
cp backend/.env.example backend/.env   # fill LLM_API_KEY; on a VPS also SECRET_KEY
# Local: SITE_ADDRESS=:80, PUBLIC_APP_URL/PUBLIC_API_URL=http://localhost
# Prod:  SITE_ADDRESS=your.domain.com, PUBLIC_*=https://your.domain.com
docker compose --env-file backend/.env up -d --build
docker compose --env-file backend/.env exec app alembic upgrade head
```

One env file: `backend/.env` (Compose + local backend). Tip: export
`COMPOSE_ENV_FILES=backend/.env` so plain `docker compose up` also interpolates
`${POSTGRES_PASSWORD}` / `${SITE_ADDRESS}` from it.

| URL | What |
|---|---|
| `http://localhost/` | SPA + API (via Caddy) |
| `http://localhost:8000/health` | API health (DB/Redis) |

Frontend HMR while iterating UI: keep the stack up, then
[Frontend quickstart](#frontend-quickstart) on the host (`npm run dev` proxies
`/api` → `:8000`). Set `CORS_ALLOW_ORIGINS=http://localhost:5173` in
`backend/.env` for that workflow. See also [CLAUDE.md](CLAUDE.md) and
[DEPLOY.md](../achitecture/docs/DEPLOY.md).

## Backend quickstart (without Docker)

```bash
cd backend
uv sync --group dev
uv run pytest
uv run ruff check .
# With DB_* (+ required ENV) set:
uv run alembic upgrade head
```

Core contracts: `backend/core/schemas.py` (`Category`, `Severity`, `Finding`, …).
ORM: `backend/app/models/`, Settings: `backend/app/config.py`.

## Try it: run a Review from the CLI

The full web flow (upload → background worker → poll → report) works end to
end via the API — see [docs/API.md](../achitecture/docs/API.md). The CLI below
is still useful for iterating on the pipeline itself without the web/DB layer
in the loop, which is deliberate ([ADR 0001](../achitecture/adr/0001-pipeline-pure-library.md)):
`core/` runs standalone, no web app or DB required.

### 1. Install

```bash
cd backend
uv sync --group dev
```

### 2. Set an LLM key

The pipeline calls an OpenAI-compatible vision API. Minimum config — a
`backend/.env` file (see `.env.example`) or exported env vars:

```bash
LLM_API_KEY=sk-...
```

Defaults to `LLM_BASE_URL=https://api.openai.com/v1` and
`LLM_MODEL_FULL=gpt-4o`; override both if you're pointing at a different
OpenAI-compatible provider. See `.env.example` for the full list
(`LLM_MODEL_SCREENING`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_ZOOMS_PER_SLIDE`).
Optional: `LANGFUSE_*`, `SENTRY_DSN`, `SMTP_*` (commented in `.env.example`).

### 3. Rendering prerequisites

- **PDF decks** — work out of the box via `pdf2image`/poppler. Make sure
  `pdftoppm` is on PATH (Windows builds: https://github.com/oschwartz10612/poppler-windows/releases).
- **PPTX decks** — additionally need LibreOffice (`soffice` on PATH) to
  convert PPTX→PDF before rendering.
- **`--audio`** (pitch recording) — needs `ffmpeg` on PATH.

Don't have LibreOffice/ffmpeg installed? Feed the CLI a `.pdf` export of your
deck and skip `--audio` — the full analyzer pipeline still runs.

> **Windows + `report.pdf`:** PDF export uses WeasyPrint, which needs native
> Pango/GObject libraries that aren't present on Windows by default. If
> `report.pdf` isn't produced and you see an error mentioning
> `libgobject-2.0-0`, either install the GTK3 runtime WeasyPrint needs (see
> https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation)
> or run the CLI inside WSL2/Docker (Linux), where `apt install libpango-1.0-0
> libpangoft2-1.0-0` resolves it cleanly. `findings.json` and `report.html`
> are written before the PDF step, so they're unaffected either way.

### 4. Run it

```bash
uv run python -m core.run --deck path/to/your-deck.pdf --out ./out
```

Optional flags: `--audio path/to/pitch.mp4` (pitch recording), `--data
path/to/data.xlsx` (source data behind the deck's charts).

### 5. Inspect the output

`./out/` will contain:

- `slide_NNN.png` — rendered slides
- `slide_NNN_zoom_NN.png`, `contact_sheet_NN.png` — analyzer working images
- `slide_NNN_annotated.png` — bbox-annotated slides (severity-colored frames)
- `findings.json` — every Находка (deduped, capped, ordered)
- `report.html` / `report.pdf` — the full report
- `fixed.pptx` + `fix_log.json` — only when the input was `.pptx` and had
  auto-fixable findings

The console prints a one-line summary: slide count, findings by severity,
elapsed time, cost in USD.

### 6. (Optional) golden eval

```bash
uv run python tests/golden/eval.py --out ./golden-run --prompt-version v1
```

Runs the pipeline against `backend/tests/golden/decks/*.pptx` and prints
recall / junk-rate / cost, appending a row to `../achitecture/docs/quality-log.md`.

## Frontend quickstart

For UI work with HMR against Dockerized API (`app` on `:8000`):

```bash
cd frontend
npm install
npm run gen:api   # → src/api/types.gen.ts from ../achitecture/api/openapi.yaml
npm run dev       # proxy /api → http://localhost:8000
npm run build
npm test
```

Production UI is the Vite build baked into the image (`docker compose up --build`).
