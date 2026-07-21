"""Web layer: FastAPI app, auth, HTTP API, DB-aware services.

Knows about HTTP and the database. Must not contain VLM/analyzer logic —
that lives in ``core``. Wired to the review pipeline only via ``worker``.
"""
