# syntax=docker/dockerfile:1
#
# Multi-stage build (ADR 0004): stage 1 builds the SPA, stage 2 is the Python
# runtime with the rendering toolchain (LibreOffice, ffmpeg, RU fonts). The
# same final image runs as both `app` (uvicorn) and `worker` (arq) — only the
# command differs; see docker-compose.yml.

# ---------------------------------------------------------------------------
# Stage 1: build the SPA
# ---------------------------------------------------------------------------
FROM node:22-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2: backend runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS backend

# `ttf-mscorefonts-installer` lives in Debian's `contrib` component, which the
# slim base image's sources don't enable by default — add it before installing.
RUN (sed -i 's/^Components: main$/Components: main contrib/' /etc/apt/sources.list.d/debian.sources 2>/dev/null || true) \
    && (sed -i 's/ main$/ main contrib/' /etc/apt/sources.list 2>/dev/null || true)

# LibreOffice headless (PPTX→PDF), poppler (PDF→PNG for pdf2image), ffmpeg
# (audio extraction), RU-capable fonts (critical — Cyrillic decks render as
# tofu boxes without them, ADR 0004), and WeasyPrint's native Pango/Cairo
# runtime (report.pdf export). `curl` is used by the container HEALTHCHECK.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libreoffice-impress \
        poppler-utils \
        ffmpeg \
        fonts-paratype \
        fontconfig \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        curl \
    && echo "ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true" | debconf-set-selections \
    && apt-get install -y --no-install-recommends ttf-mscorefonts-installer \
    && fc-cache -f \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

# uv's venv lives outside /app/backend (keeps the project env path stable
# if the source tree is ever bind-mounted for debugging).
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1

WORKDIR /app
# backend/pyproject.toml declares `readme = "../README.md"` — `uv sync` builds
# the project itself (hatchling) and hard-fails if that path doesn't resolve.
COPY README.md ./README.md

WORKDIR /app/backend

# Dependencies first (cached layer; only invalidated by lockfile changes).
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Then the rest of the source, and install the project itself.
COPY backend/ ./
RUN uv sync --frozen --no-dev

# Built SPA — not yet served by FastAPI (StaticFiles mount is #26 И2's job,
# single-domain prod serving); present in the image so that ticket is a
# one-line change, not a rebuild-the-image change.
COPY --from=frontend /frontend/dist /app/static

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
