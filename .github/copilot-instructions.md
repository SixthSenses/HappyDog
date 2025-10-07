## HappyDog AI Agent Instructions
Fast, codebasespecific rules so an AI can ship safe changes without guesswork.

### 1) Big picture (what goes where)
- Monolith Flask backend in `pet_project_backend/app` with strict domains under `api/` (auth, users, posts, comments, pets, pet_care, notifications, cartoon_jobs, breeds, uploads, translator, guidebook, survey, common).
- Per domain: `routes.py` = HTTP only; `services/` = business logic; optional `schemas.py` = Marshmallow Schemas. Never call Firestore/OpenAI/ML from routes.
- Shared infra: `app/services/` (storage, notification, openai, idempotency), `app/utils/` (error_catalog, problem_details, path_utils, metrics). DI container is `app.services[...]` created in `app/__init__.py`.
- Services use constructor injection: pass dependencies explicitly (e.g., `PostService(db_client)`, `PetProfileService(pet_care_setting_service, storage_service, db_client)`).

### 2) App wiring (order matters)  see `app/__init__.py`
- Firestore client created once (`initialize_firestore()`), then core services in `_init_core_services()`: storage  openai (or stub if `DOCS_MODE`)  notifications  idempotency  breeds  auth  optional ML (nose_pipeline, eye_analyzer via `resolve_ml_paths`).
- Then dependent services in `_init_dependent_services()`: pet_care  pets (profile + biometrics)  users  posts  comments  cartoon_jobs (with ThreadPoolExecutor only when not docs mode).
- Feature-gate optional ML: always check `if app.services['nose_pipeline']:` etc. Use `SKIP_ML=1` or `DOCS_MODE=1` to skip heavy model init.
- ML path resolution: `resolve_ml_paths()` from `app/utils/path_utils.py` handles cross-machine paths; set `STRICT_ML_PATHS=1` to raise on missing paths (default: warn and skip).

### 3) Requests, validation, errors
- Validate JSON with Marshmallow before services; `ValidationError` is mapped to 400 globally.
- Use the catalog: `app.utils.error_catalog.build_error('CODE')`  `(status, body)` with fields `{error_code, category, retriable, message, details}`. Don't handcraft JSON.
- Error codes consolidated (see `error_catalog.py`): use `NOT_FOUND` (not `*_NOT_FOUND` variants), `RECORD_CREATION_FAILED`/`UPDATE_FAILED`/`DELETE_FAILED` (not per-domain codes), `UNAUTHORIZED` (not `INVALID_JWT`/`MISSING_JWT`).
- Idempotency for POST/PUT/PATCH/DELETE: use `@idempotent_endpoint(apply_when_methods=('POST',))` and the `X-Idempotency-Key` header. Replay is signaled via `Idempotent-Replay: true` (new) + `Idempotency-Replay: true` (legacy, will deprecate).
- Rate limiting: reuse helpers in `middleware/rate_limit_middleware.py`; don't duplicate logic.

### 4) API docstyle  OpenAPI
- Route docstrings drive the spec. First line = summary (Korean, imperative verb, <50 chars); body = description. Add meta tags (see `docs/API_DOCSTYLE.md`):
- `RequestSchema: <SchemaName>` (required for POST/PUT/PATCH, use `EmptyRequestSchema` if no body)
- `ResponseSchema: <SchemaName>` (defaults to 200) or `ResponseSchema[201]: <SchemaName>` for multiple status codes
- Use `NoContentSchema` for 204 responses; always explicit about empty bodies
- Schemas are autocollected from `app/api/*/schemas.py`. Builder injects standard error responses from `error_catalog` and BearerAuth when enabled.
- Schema naming: `*RequestSchema` for requests, `*Schema` for single entities, `*ListSchema` for collections.

### 5) Swagger build (use VS Code tasks on Windows)
- Preferred: run task "Rebuild Swagger (docs mode)"  deterministic and fast (skips Firebase/ML):
- `--app pet_project_backend.app:create_app --out openapi.json --pretty-out openapi_pretty.json --docs-mode --add-tags --add-security --add-servers --strict-doc-tags`
- Direct command (if not using tasks): `conda activate happydog-backend` (or `dog`), then `python pet_project_backend/scripts/swagger_build.py` with args above.
- Strict mode will warn/fail when required Request/ResponseSchema tags are missing; use for CI validation.

### 6) Run, test, and envs
- Conda env file: `pet_project_backend/environment.yml` (name: `dog`). Create with: `conda env create -f pet_project_backend/environment.yml`.
- VS Code tasks may assume `happydog-backend` env. If your env name differs, update the task or activate manually.
- Run app: `python pet_project_backend/run.py` (env: `FLASK_ENV=development`, `DOCS_MODE=1` to skip ML). Health check at `/health` returns metrics and Firestore status.
- Tests: `pytest -k <filter>` from repo root. Avoid real GCP in tests; prefer Firestore emulator and `DOCS_MODE=1` or injected stubs. Test directory exists but minimal tests currently.
- Config: `app/core/config.py` has `DevelopmentConfig`/`TestingConfig`; set `FLASK_ENV` to select. Firebase credentials fallback: `FIREBASE_CREDENTIALS_PATH`  `DEV_FIREBASE_CREDENTIALS_PATH`/`TEST_FIREBASE_CREDENTIALS_PATH`.

### 7) Adding or changing a domain (checklist)
1) Create/modify `app/api/<domain>/routes.py`, `services/`, and optional `schemas.py`.
2) Register services in `app/__init__.py` respecting the order above (`_init_core_services` vs `_init_dependent_services`); register blueprint under `/api/<domain>`.
3) Add any new error codes in `app/utils/error_catalog.py` only; do not invent perroute JSON. Prefer generic codes (`NOT_FOUND`, `RECORD_CREATION_FAILED`) over domain-specific ones.
4) Update route docstrings with Request/ResponseSchema tags; rebuild Swagger (docs mode task).
5) If service needs dependencies, inject via constructor and wire in `_init_dependent_services()`.

### 8) Examples (projectspecific)
- Error response in a route/service: `status, body = build_error('NOT_FOUND'); return jsonify(body), status`.
- Idempotent POST: `@idempotent_endpoint(apply_when_methods=('POST',))` above route, client sends `X-Idempotency-Key` header.
- OpenAI: always call through `app.services['openai']` (stub is injected automatically in docs mode).
- ML feature gate: `nose_pipeline = current_app.services['nose_pipeline']; if nose_pipeline: result = nose_pipeline.analyze(...)`.
- Service with DI: `class PetService: def __init__(self, storage_service, db_client): ...` then wire in `app/__init__.py`: `app.services['pets'] = PetService(app.services['storage'], app.firestore_client)`.

### 9) Key docs & deep dive
- `docs/API_DOCSTYLE.md`: Full docstring rules, meta tag syntax, anti-patterns
- `docs/DEEPLINKS_AND_IDEMPOTENCY.md`: Idempotency header contract, applied endpoints list, OAuth flow
- `pet_project_backend/scripts/swagger_build.py`: OpenAPI generation logic (introspects routes, parses docstrings, injects error_catalog)

Hard rules: no Firestore/ML/OpenAI logic in routes; centralize errors via catalog; guard optional ML; keep routes thin and schemadriven; use generic error codes from catalog (no new domain-specific codes unless business-critical). If you need new infra (cache, schedulers, external APIs), call it out explicitly in the PR.
