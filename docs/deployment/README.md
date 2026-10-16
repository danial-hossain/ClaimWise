# Deployment

This checkout contains no verified Docker, CI, or hosting deployment configuration. The steps
below describe the existing entry points; they are not a record of a successful deployment.

Build/install using the existing manifests:

```powershell
npm --prefix frontend ci
npm run build
python -m pip install -r backend/requirements.txt
```

Run the frontend with `npm run start`. Run the API separately from `backend/`:

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Use an HTTPS reverse proxy or hosting platform. Route browser `/api/v1` requests to the API
without dropping cookies or CSRF headers. Set the Next.js server-side rewrite target with
`CLAIMWISE_BACKEND_URL` or the existing `NEXT_PUBLIC_API_URL`; provide it when building/running
as required by your hosting process. Frontend secrets must never be exposed through public env vars.

Configure API `ENVIRONMENT=production`, `DEBUG=false`, a strong unique `JWT_SECRET`, a valid
`DATABASE_URL`, and the intended `CORS_ORIGINS`. Supply Gemini credentials through secret
management when AI functionality is required. Verify sign-in, session restoration, cookie
attributes, Origin/CSRF rejection, and account isolation on the final HTTPS origin.

Existing PostgreSQL tables/extensions are initialized lazily. Review application-role privileges
and the preserved SQL migrations before deployment; no automatic migration command was added.
Ensure uploads/evidence and database backups use persistent storage appropriate for the host.

Use `/api/v1/health` for process liveness and `/api/v1/ready` for subsystem diagnostics. Readiness
currently reports operational/partial status according to the existing implementation; do not
assume a 200 response alone means every dependency is configured.
