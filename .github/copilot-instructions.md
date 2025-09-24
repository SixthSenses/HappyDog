## HappyDog AI Agent Instructions
Focused guidance for autonomous code changes in this backend.

### 1. Core Domain & Layout
Backend root: `pet_project_backend/app` organized by domain under `api/` (e.g. `auth`, `pets`, `pet_care`, `posts`, `comments`, `notifications`, `uploads`). Each domain keeps: `routes.py` (HTTP only), `services/` (business logic), optional `schemas.py` (Marshmallow), and sometimes sub‑service modules. Never add business logic to `routes`.
Global cross‑cutting modules: `core/` (initialization: Firestore, JWT, app wiring), `middleware/` (idempotency, rate limiting), `utils/` (error catalog, datetime, API docs helpers), `services/` (shared infrastructure: `firestore_service.py`, `storage_service.py`, `notification_service.py`, `openai_service*.py`).

### 2. Dependency & Service Wiring
Application services are instantiated in `app/__init__.py` and injected (DI pattern) into domains via `app.services[...]`. When adding a new service: (1) create implementation in appropriate domain or shared `services/`; (2) register instance in `create_app` near related domain grouping; (3) expose only pure methods (side effects limited to Firestore / Storage). Respect ordering (foundational services like notifications, auth first; dependent domains later).

### 3. Data & Validation
Firestore is the persistence layer; always convert datetime objects using `DateTimeUtils.for_firestore` before writes. All inbound request payloads must be validated at route entry with a Marshmallow schema (place in `schemas.py` or inline schema module). Do not bypass schema even for internal tooling endpoints. Maintain collection naming consistency already used in existing services—inspect similar service before introducing a new collection.

### 4. Error Handling Contract
Use centralized error system: `app.utils.error_catalog` exports `ERRORS`, `build_error`, `ErrorSpec`. In routes: return `build_error(ERRORS['SOME_CODE'])` on known business failures; never craft ad‑hoc JSON. Wrap Firestore lookups; map not-found to catalog codes instead of raw exceptions. When adding new error: extend catalog (provide code, http status, message, detail schema) and reference it; update swagger via `scripts/swagger_build.py` if needed.

### 5. Idempotency & Rate Limits
Long-running or write endpoints that can be retried should integrate idempotency middleware key extraction (see `middleware/idempotency_middleware.py`). For high-frequency endpoints, consult `rate_limit_middleware.py` patterns—reuse helper functions and constant buckets; do not duplicate logic inside routes.

### 6. OpenAPI / Documentation
Primary specs: root `openapi.json` and `openapi_pretty.json`. Regeneration pipeline leverages `scripts/swagger_build.py` and domain route introspection + error catalog injection. After adding/modifying routes: run the swagger build script and ensure new error responses reference catalog codes only.

### 7. Testing Strategy
Use `pytest`. Unit tests: isolate service logic; mock Firestore client (pattern visible in existing `test_*` scripts under `scripts/` and `tests/`). Integration tests must target Firestore Emulator—never real GCP project. Provide Arrange-Act-Assert structure, ensure deterministic timestamps (use helpers). For new domain add minimal smoke test covering happy path + one catalog error.

### 8. Security & Input Sanitation
Authenticate via auth service (Firebase / JWT integration). Never log secrets, tokens, or PII. Validate every external input through schema before reaching service layer. File uploads go through `uploads` domain; reuse existing storage service patterns to enforce size/type constraints.

### 9. OpenAI / External Calls
When using `openai_service.py`, prefer the existing stub for tests (`openai_service_stub.py`). Inject service through `app.services` for testability; do not call external APIs directly inside domain services.

### 10. Performance & Consistency
Avoid N+1 Firestore reads—batch or structure queries like similar services (inspect `PostService`, `CommentService`). Use idempotency for any endpoint where duplicate POST could corrupt counters or duplicated documents. Keep route functions thin: parse + validate + delegate + format response.

### 11. Adding a New Domain (Example Workflow)
1. Create folder `app/api/<domain>/` with `routes.py`, `services/__init__.py`, optional `schemas.py`.
2. Implement service referencing injected Firestore client.
3. Register service instance in `app/__init__.py` (preserve grouping comment style).
4. Define Marshmallow schemas; use camelCase in JSON if consistent with neighboring domain (mirror existing pattern).
5. Add catalog errors if needed; regenerate swagger.
6. Add unit test (service) + integration test (route) using emulator.

### 12. Commit & PR Conventions
Follow Conventional Commits (feat, fix, refactor, chore, test, docs). Reference error code or service name when relevant: `fix(auth): handle expired token revocation using ERR-XYZ`.

### 13. Do / Don't Quick Reference
Do: Centralize errors; validate inputs; inject dependencies; keep routes thin.
Don't: Embed Firestore logic in routes; create ad-hoc JSON errors; skip schema for internal endpoints; call external APIs directly.

### 14. Fast Start Commands (Windows cmd)
conda activate dog
Run app: `python pet_project_backend/run.py`
Run tests (unit): `pytest -k service`
Swagger rebuild: `python pet_project_backend/scripts/swagger_build.py`

Keep this file concise; propose edits via PR if architectural shifts occur.
