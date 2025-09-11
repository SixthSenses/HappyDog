## HappyDog Backend – Focused AI Instructions (2025-09 Refactor Sprint)

Minimal set – anything else: read `final_refactor_plan.md`.

### A. Current Sprint Scope (authoritative plan: `final_refactor_plan.md`)
PR1-Critical → Fix comment route bugs, remove pet weight fields, gender lowercase→Enum, drop deprecated pet public endpoint.
PR2-PresenterPolicy → Add pets presenter/policy, comment is_liked enrichment, introduce `text_utils.truncate_summary`.
PR3-CartoonState → Add CANCELLED status & distinct notification, helper for fail/cancel, apply error catalog in cartoon domain.
PR4-ErrorUnify → Global error catalog adoption, remove duplicate `_sanitize_summary`, add central constants (SUMMARY_MAX_LEN=80, LIKE_BATCH=30).
PR5-Integrity (optional) → user↔pet link verification script.

Edit ONLY files needed per PR. If plan & code diverge: update plan first.

### B. Core Runtime & DI
Framework: Flask + Firestore/Storage. Access services ONLY via `current_app.services['key']` inside request context. Do not instantiate services directly.

### C. Key Utilities / Files
`app/__init__.py` (service registration order), `app/utils/error_catalog.py`, `app/middleware/idempotency_middleware.py`, `app/utils/api_documentation.py`.
New expected: `app/api/pets/presenters.py`, `app/api/pets/policy.py`, `app/utils/text_utils.py`, `app/core/constants.py`.

### D. Hard-Coding Elimination Targets
Move literals: summary length=80, like batch size=30 → constants module.
Use Error Catalog codes (no raw strings). Enum conversions (gender, job status) centralized.

### E. Immediate Bug Fix Priorities (PR1)
1) Comment list route passes user_id into limit param.
2) Comment created event signature mismatch (needs mention data).
3) Remove pet weight fields & deprecated public endpoint.

### F. Testing (Micro each PR)
PR1: create comment (no TypeError), create pet (gender case-insensitive), verify weight fields absent.
PR2: social vs mypage access policy, comment is_liked after like toggle.
PR3: job create→cancel status CANCELLED.
PR4: error response shape `{code, message}` sample endpoints.

### G. Non-Authoritative / Legacy
Ignore `docs/api/*.md` (stale). Source of truth: code decorators + schemas + `final_refactor_plan.md`.

### H. Sanity Checklist Before Commit
- Only planned domain touched.
- No new dependencies.
- Error responses via `build_error` (except untouched future-refactor code).
- Util functions referenced by at least one call site.

### I. If Unsure
1. Read `final_refactor_plan.md`.
2. Keep change minimal & PR-scoped.
3. Add constant / util rather than inlining magic values.

End.
