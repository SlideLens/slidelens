# Alembic migrations for the application database.

Migrations:
```bash
cd backend
# Ensure DB_* (or DATABASE_URL) and other required ENV are set, then:
uv run alembic revision --autogenerate -m "msg"
uv run alembic upgrade head
```
