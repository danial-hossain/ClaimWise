# ClaimWise frontend

Next.js App Router application. Run commands from this directory or use the repository-root wrappers.

```powershell
npm ci
npm run dev            # Starts backend and frontend
npm run dev:frontend   # Frontend only
npm run dev:backend    # Backend only
npm run typecheck
npm run lint
npm test
npm run test:wizard
npm run build
npm start
```

Copy `.env.example` to `.env.local` only for a new checkout. The Next.js rewrite targets
`CLAIMWISE_BACKEND_URL`, then `NEXT_PUBLIC_API_URL`, then `http://127.0.0.1:8000`.
Browser requests stay on the frontend origin, including cookie and CSRF handling.

- `src/app`: existing public routes and global stylesheet imports. Keep route filenames in place.
- `src/components/features`: authentication, dashboard, homepage, and preparation wizard UI.
- `src/components/ui`: genuinely reusable presentation components.
- `src/context`, `src/lib`, `src/types`: session/scenario state, API/workflow helpers, and contracts.
- `scripts`: launchers and shared interpreter discovery.
- `tests/unit`: Node tests; no application server is required.
- `tests/browser`: existing manual browser checks; these require an isolated Chrome debugging
  session on port 9235 and a running local application. See each script before running it.

`npm run verify:wizard`, `npm run verify:wizard:basic`, and `npm run verify:surfaces` invoke the
manual checks. Some create scenario or claim preparation records; they are not part of unit tests.
Verification evidence remains in `../docs/screenshots/`.

See the [main README](../README.md), [setup guide](../docs/development/SETUP.md), and
[refactor report](../docs/development/REPOSITORY_REFACTOR.md).
