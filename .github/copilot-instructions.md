# HappyDog Backend — AI Agent Notes

Goal: Practical rules to work productively in this Flask backend without breaking conventions.

## Big picture
- Flask app factory (`app/__init__.py:create_app`) launched by `python run.py` from `pet_project_backend/`.
- Domains via blueprints under `app/api/**` (auth, users, posts, comments, cartoon_jobs, breeds, pets, pet_care, notifications).
- Dependency injection: services are created in `create_app()` and stored on `current_app.services[...]` (e.g., 'storage', 'openai', 'breeds', 'pets', 'pet_care_records').
- Data: Firestore + Storage via Firebase Admin SDK; access happens inside services (no ORM).
- ML: optional `nose_models`/`eyes_models`; init may fail → service is `None` (callers must guard).

## Run & env
- Run from `pet_project_backend/`; conda envs defined in `environment.yml` or `envs/*.yml`.
- `.env` required; key vars include `FLASK_ENV`, `JWT_SECRET_KEY`, `DEV/TEST_FIREBASE_CREDENTIALS_PATH`, `FIREBASE_STORAGE_BUCKET`, `OPENAI_API_KEY`, and ML paths. Secrets live in `secrets/`.

## Conventions
- Time: UTC only. Convert ms<->datetime with `app.utils.datetime_utils.DateTimeUtils`. Persist timezone-aware datetimes; maintain `searchDate` (YYYY-MM-DD) for querying.
- Errors: `{ error_code, message?, details? }` JSON; `ValidationError` is globally handled.
- Auth: protect endpoints with `@jwt_required()`; validate with Marshmallow schemas next to routes.

## Firestore patterns
- Filter by `pet_id` + (`searchDate` eq/range) and optionally `record_type` (`in` up to 10 values).
- Sort by `timestamp` asc/desc; paginate with cursor doc ID + `start_after()` and `limit+1` for `has_more`.
- Ensure composite indexes per README (e.g., `(pet_id, searchDate, timestamp)`).

## Example: Pet Care Records
- Files: `app/api/pet_care/records/{routes,services}.py`.
- Create: body `{ record_type, timestamp(ms), data, notes? }` → ms→UTC, set `searchDate`, upsert by `log_id` (idempotent via `request_id`).
- List: `GET /api/pet-care/{pet_id}/records?date=YYYY-MM-DD&record_types=weight,meal&limit=20&cursor=...` (supports `start_date/end_date`, `grouped`, `sort`). Types: `weight, water, activity, meal, bcs`.

## Adding a feature
1) Implement service in `app/api/<feature>/services.py` (Firestore, time, pagination patterns above).
2) Add blueprint in `app/api/<feature>/routes.py` with Marshmallow schemas and standard error payloads.
3) Wire in `app/__init__.py`: create service(s) → `app.services[...]`, `register_blueprint(..., url_prefix='/api/<feature>')`.

## OpenAI
- `app/services/openai_service.py` (GPT‑4o analysis + DALL·E 3). Fetch via `current_app.services['openai']`. Needs `OPENAI_API_KEY`.

## Tests
- Pytest example: `python -m pytest app\utils\test_datetime_utils.py -v`.

## Safety
- Never commit secrets/weights; keep `.env` in sync with `secrets/`. Guard ML services for `None`. Avoid logging sensitive values.
