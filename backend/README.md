# ClaimWise backend

FastAPI entry point: `app.main:app`. Run commands from `backend/` so Pydantic settings load
`backend/.env` consistently.

```powershell
./venv/Scripts/python.exe -m pip install -r requirements.txt
./venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

`app/api` contains endpoints; `core` contains configuration/security; `schemas` contains API
contracts; `models` contains domain types; `db` contains connections, repositories, stores,
and existing migrations; `services` contains the application logic. `scripts/` hosts the
benchmark runner and `tests/` hosts the Python suite.

For integration tests, configure `DATABASE_URL` to a disposable PostgreSQL database first:

```powershell
./venv/Scripts/python.exe -m pytest tests -q
```

Tests can write and clear persisted fixtures. Do not run the complete suite against your saved
user data. `DATABASE_URL=placeholder` disables database connectivity for an offline run; those
integration tests will fail rather than silently using a mock database.

The current store creates its tables/extensions lazily; `app/db/migrations/` and the historical
`../docs/schema/` are retained unchanged. Review their assumptions before applying SQL to a
particular deployment. PostgreSQL extension permissions and an application database role are
required; see [setup](../docs/development/SETUP.md) and [deployment](../docs/deployment/README.md).
