# Development and validation

Start with the [repository README](../../README.md). No package-manager or framework change
is required for this refactor. The frontend lockfile remains authoritative for npm installation;
Python dependencies remain in `backend/requirements.txt`.

## Environments

The service launchers run FastAPI from `backend/`, which loads `backend/.env`.
Next.js loads `frontend/.env.local`. A repository-root `.env` is preserved but is not implicitly
merged into either process. Existing environment variable names are unchanged.

`DATABASE_URL` points at PostgreSQL. The application's current store initializes its tables
and extensions on first access; it does not run the SQL migration directory as a migration
runner. Read the migrations before applying them manually: older files describe earlier
Supabase-era schemas and do not replace current store initialization.

The two local launchers retain their interpreter discovery order. `npm run dev` checks an
active virtual environment, `backend/venv`, `backend/.venv`, repository `.venv`, then the parent
workspace `.venv`. The standalone backend launcher retains its narrower original candidate
list: active environment, `backend/venv`, then parent workspace `.venv`. Both fall back to the
platform Python command.

## Automated checks

From the repository root:

```powershell
npm run typecheck
npm run lint
npm run test:frontend
npm run build
```

From `backend/`, configure `TEST_DATABASE_URL` to a disposable PostgreSQL database and
`CLAIMWISE_TEST_DB_CONFIRM` to its exact database name before running integration tests:

```powershell
$env:TEST_DATABASE_URL='<disposable PostgreSQL URL>'
$env:CLAIMWISE_TEST_DB_CONFIRM='<exact claimwise_test_ database name>'
./venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider
```

The test harness requires both database and role names to start with `claimwise_test_`,
checks an explicit disposable-database marker and pgvector availability, and refuses any
database matching the configured application URLs before routing tests to `DATABASE_URL`.
The integration suite persists fixtures and can clear stores. Never use an account's working
database. No isolated PostgreSQL server is bundled with this checkout.

Without a verified disposable database, select only independent tests:

```powershell
./venv/Scripts/python.exe -m pytest tests -m "not database" -q -p no:cacheprovider
```

For isolated/offline checks, use process-local overrides before pytest:

```powershell
$env:DATABASE_URL='placeholder'
$env:GEMINI_API_KEY='placeholder'
$env:JWT_SECRET='claimwise-isolated-test-secret-key-32-characters'
$env:ENVIRONMENT='development'
$env:DEBUG='false'
./venv/Scripts/python.exe -m pytest tests -m "not database" -q --tb=short -p no:cacheprovider
```

Run those overrides in a dedicated terminal/process. They do not edit `.env` files, and they
are not production configuration. The test harness blocks database-marked tests without a
verified disposable database and has an additional connection guard for other tests. Earlier
verification reports record results from their respective historical snapshots.

The deterministic benchmark CLI remains `backend/scripts/run_qa_benchmark.py`; its default
reports still go to `docs/QA_40_BENCHMARK_REPORT.md` and `docs/qa_benchmark_results.json`.
Pass alternate `--out-md`/`--out-json` paths when preserving submission evidence.

## Manual browser checks

`frontend/tests/browser/` contains the existing Chrome debugging scripts. They require a
running app and an isolated browser listening on port 9235. Read each script before running:
the wizard scripts can create preparation records, while surfaces verification reads existing
account state. Unit tests do not launch these scripts. Their screenshot/report destinations
remain under `docs/screenshots/`.
