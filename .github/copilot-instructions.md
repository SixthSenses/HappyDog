## HappyDog AI Agent Instructions
Concise, codebase‑specific rules so an AI can safely ship changes fast.

### 1. Architecture Snapshot
Monolith Flask backend at `pet_project_backend/app` with strict domain folders under `api/` (auth, users, posts, comments, pets, pet_care, notifications, cartoon_jobs, breeds, uploads, translator, guidebook, survey, common). Pattern per domain: `routes.py` (HTTP only) + `services/` (business logic) + optional `schemas.py`. Never put Firestore or ML logic in routes. Shared infra in `app/services/` (storage, notification, openai, idempotency) and `app/utils/` (datetime, error catalog, path utils, metrics). Central composition + DI live in `app/__init__.py` using `app.services[...]` as the container.

### 2. Service Initialization Order (Critical)
`create_app()` builds Firestore (once), then `_init_core_services()` (storage -> openai or stub if `DOCS_MODE` -> notifications -> idempotency -> breeds -> auth -> optional ML pipelines) then `_init_dependent_services()` (pet care, pets, users, posts, comments, cartoon_jobs). Respect this layering: new service must appear in the earliest phase where its dependencies are already registered. For docs or lightweight environments set `DOCS_MODE=1` to skip Firebase + ML + external network; tests relying on no heavy setup should mimic this.

### 3. Environment / Flags
Primary env vars: `FLASK_ENV`, `DOCS_MODE`, `SKIP_ML`, `STRICT_ML_PATHS`, Firebase creds paths (`FIREBASE_CREDENTIALS_PATH`, `FIREBASE_STORAGE_BUCKET`). ML models resolved via `utils.path_utils.resolve_ml_paths`; if assets missing and not strict, pipeline is silently skipped (service set to None). Never assume ML services are non‑null—feature gate in code.

### 4. Data & Firestore Usage
All persistence via injected `app.firestore_client`. Convert outgoing datetime structures with `DateTimeUtils.for_firestore`. Keep collection naming consistent—inspect existing domain services before adding new collections. Batch or structure queries like `PostService` / `CommentService` to avoid N+1 reads. No Firestore calls from routes: delegate to service method.

### 5. Validation & Schemas
Every request body validated with Marshmallow before hitting services (raise `ValidationError` => mapped to uniform 400). Place schemas near the domain (`schemas.py`) or inline file if small; keep JSON field naming consistent (camelCase currently prevalent). Reject ad‑hoc validation logic in services.

### 6. Error Contract
Central catalog: `app.utils.error_catalog` (`ERRORS`, `build_error`). Routes and middleware return `(status, body)` from `build_error('CODE')`; never hand‑craft JSON. When adding an error: extend catalog with code, http status, message, optional detail schema, then regenerate Swagger. Map not-found & authorization failures explicitly; no raw exception leakage.

### 7. Idempotency & Rate Limiting
For POST endpoints susceptible to duplicate writes wrap with idempotency middleware patterns (see `middleware/idempotency_middleware.py`) and use `app.services['idempotency']`. For burst‑prone endpoints reference bucket config in `rate_limit_middleware.py`; do not clone logic—reuse helpers.

### 8. External / OpenAI / ML
Never instantiate OpenAI client directly; use `app.services['openai']` (stub automatically injected in `DOCS_MODE`). Guard ML dependent code: `if app.services['nose_pipeline']:` etc. Background cartoon job processing uses a `ThreadPoolExecutor` only when not in docs mode—avoid adding blocking tasks to request thread; schedule through existing job services.

### 9. API Documentation Workflow
Specs: `openapi.json`, `openapi_pretty.json`. Rebuild after adding/modifying routes or error codes: `python pet_project_backend/scripts/swagger_build.py` (or use VS Code task). The builder auto-injects error responses from catalog; ensure new endpoints refer only to catalog codes. Use `DOCS_MODE=1` for deterministic spec generation (skips heavy init).

### 10. Testing Conventions
Use `pytest`. Prefer dependency injection to allow stubbing; for OpenAI rely on stub via `DOCS_MODE` or direct stub injection. Firestore emulator required for integration tests—never call real GCP in tests. Structure tests Arrange / Act / Assert; stable timestamps via `DateTimeUtils.now()` mocking if determinism needed.

### 11. Adding / Modifying a Domain
1) Create `app/api/<domain>/` with `routes.py`, `services/`, optional `schemas.py`. 2) Implement services DI-ing Firestore + other services. 3) Register service(s) in the correct phase inside `app/__init__.py`. 4) Register blueprint with `/api/<domain>` prefix. 5) Add error codes (if needed) then regenerate Swagger. 6) Provide unit test (service) + minimal integration test (route success + one catalog error).

### 12. Performance & Consistency Rules
Keep route handlers thin: parse -> validate -> delegate -> format plain dict response. Avoid per-item Firestore fetch loops; design query methods returning already aggregated data. Use idempotency for mutation endpoints creating records or side effects. Prefer explicit service methods over util singletons.

### 13. Commits & PRs
Conventional Commits (`feat:`, `fix:`, etc.). Include domain or error code context, e.g. `feat(pets): add biometric enrollment ERR-PET-BIOMETRIC-NOTREADY`.

### 14. Quick Commands (Windows)
Activate env: `conda activate dog`
Run app: `python pet_project_backend/run.py`
Run selective tests: `pytest -k post_service`
Rebuild Swagger: `python pet_project_backend/scripts/swagger_build.py`

### 15. Do / Don't (Enforced Patterns)
Do: Centralize errors; validate all inputs; inject services; guard optional ML; rebuild spec after route changes.
Don't: Perform Firestore or OpenAI calls in routes; craft ad-hoc JSON errors; assume ML services exist; duplicate rate-limit logic.

Questions / gaps: if adding caching layer, background scheduling beyond current executors, or new external API patterns, flag in PR description—no hidden architectural shifts.
