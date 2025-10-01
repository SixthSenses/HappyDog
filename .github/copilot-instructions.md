## HappyDog AI Agent Instructions
Fast, codebase‑specific rules so an AI can ship safe changes without guesswork.

### 1) Big picture (what goes where)
- Monolith Flask backend in `pet_project_backend/app` with strict domains under `api/` (auth, users, posts, comments, pets, pet_care, notifications, cartoon_jobs, breeds, uploads, translator, guidebook, survey, common).
- Per domain: `routes.py` = HTTP only; `services/` = business logic; optional `schemas.py` = Marshmallow Schemas. Never call Firestore/OpenAI/ML from routes.
- Shared infra: `app/services/` (storage, notification, openai, idempotency), `app/utils/` (error_catalog, problem_details, path_utils, metrics). DI container is `app.services[...]` created in `app/__init__.py`.

### 2) App wiring (order matters) — see `app/__init__.py`
- Firestore client created once (`initialize_firestore()`), then core services: storage → openai (or stub if `DOCS_MODE`) → notifications → idempotency → breeds → auth → optional ML (nose_pipeline, eye_analyzer via `resolve_ml_paths`).
- Then dependent services: pet_care → pets (profile + biometrics) → users → posts → comments → cartoon_jobs (with ThreadPoolExecutor only when not docs mode).
- Feature-gate optional ML: always check `if app.services['nose_pipeline']:` etc.

### 3) Requests, validation, errors
- Validate JSON with Marshmallow before services; `ValidationError` is mapped to 400 globally.
- Use the catalog: `app.utils.error_catalog.build_error('CODE')` → `(status, body)` with fields `{error_code, category, retriable, message, details}`. Don’t handcraft JSON.
- Idempotency for POST/PUT/PATCH: use `middleware/idempotency_middleware.idempotent_endpoint` and the `X-Idempotency-Key` header. Replay is signaled via `Idempotent-Replay: true`.
- Rate limiting: reuse helpers in `middleware/rate_limit_middleware.py`; don’t duplicate logic.

### 4) API docstyle → OpenAPI
- Route docstrings drive the spec. First line = summary; body = description. Add meta tags (see `docs/API_DOCSTYLE.md`):
	- `RequestSchema: <SchemaName>`
	- `ResponseSchema: <SchemaName>` (defaults to 200) or `ResponseSchema[201]: <SchemaName>`
- Schemas are auto‑collected from `app/api/*/schemas.py`. Builder injects standard error responses from `error_catalog` and BearerAuth when enabled.

### 5) Swagger build (use VS Code tasks on Windows)
- Preferred: run task “Rebuild Swagger (docs mode)” — deterministic and fast (skips Firebase/ML):
	- `--app pet_project_backend.app:create_app --out openapi.json --pretty-out openapi_pretty.json --docs-mode --add-tags --add-security --add-servers --strict-doc-tags`
- Direct command (if not using tasks): activate your conda env then run the same args. Strict mode will warn/fail when required Request/ResponseSchema tags are missing.

### 6) Run, test, and envs
- Conda env file: `pet_project_backend/environment.yml` (name: `dog`). README also uses `conda activate dog`.
- VS Code tasks may assume a different env name (e.g., `happydog-backend`). If your env name differs, update the task or activate manually before running.
- Run app: `python pet_project_backend/run.py` (env: `FLASK_ENV=development`). Health check at `/health` returns metrics and Firestore status.
- Tests: `pytest -k <filter>`. Avoid real GCP in tests; prefer Firestore emulator and `DOCS_MODE=1` or injected stubs.

### 7) Adding or changing a domain (checklist)
1) Create/modify `app/api/<domain>/routes.py`, `services/`, and optional `schemas.py`.
2) Register services in `app/__init__.py` respecting the order above; register blueprint under `/api/<domain>`.
3) Add any new error codes in `app/utils/error_catalog.py` only; do not invent per‑route JSON.
4) Update route docstrings with Request/ResponseSchema tags; rebuild Swagger (docs mode task).

### 8) Examples (project‑specific)
- Error response in a route/service: `status, body = build_error('NOT_FOUND'); return jsonify(body), status`.
- Idempotent POST: decorate with `@idempotent_endpoint()` and read `X-Idempotency-Key` from headers (middleware handles persistence via `app.services['idempotency']`).
- OpenAI: always call through `app.services['openai']` (stub is injected automatically in docs mode).

Hard rules: no Firestore/ML/OpenAI logic in routes; centralize errors via catalog; guard optional ML; keep routes thin and schema‑driven. If you need new infra (cache, schedulers, external APIs), call it out explicitly in the PR.
