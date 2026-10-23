# Phase 1 baseline: reliability and security

**Baseline commit:** `b5125473cce906302c9bc65313190c7066ed370e`  
**Baseline branch:** `main`  
**Phase branch:** `phase-1/core-reliability-security`  
**Purpose:** Record the starting point and repeatable verification commands before behavior-changing work. This is a review inventory, not a claim that every listed risk is an existing defect.

## Verification snapshot

- GitHub Actions run [#320](https://github.com/parthiv-doraswamy/pravaah/actions/runs/39949556712) for the baseline commit completed successfully on 23 October 2026.
- The workflow `.github/workflows/backend-ci.yml` defines Python 3.12 backend tests and Ruff lint, PostgreSQL migration/worker smoke checks, SMTP delivery smoke checks using Mailpit, Compose configuration validation, Compose restart/persistence reliability, Playwright browser E2E tests, and a frontend production build.
- CI is configured for pushes to `main` and pull requests targeting `main`. A push to a phase branch alone does not trigger this workflow; opening/updating a PR against `main` does.
- The CI result is repository evidence only. This session inspected repository metadata and source files; it did **not** execute the test suite locally or verify the deployed Render runtime.
- README and backend-development docs explicitly describe the project as a synthetic prototype. Malware scanning and hosted SMTP/runtime delivery still require environment-level verification.

## Reproducible checks

Prerequisites: Python 3.12+, and optionally Docker with Compose; PostgreSQL 16 is used by the CI integration jobs.

### Backend tests and lint

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest
ruff check --select E4,E7,E9,F app tests migrations
```

### Database and worker checks

With a reachable PostgreSQL database configured through `DATABASE_URL`:

```bash
alembic upgrade head
alembic current
python -m scripts.seed_demo
python -m scripts.seed_demo
python -m scripts.postgres_worker_smoke
python -m scripts.notification_worker --once
```

The SMTP smoke test requires a test SMTP service (CI uses Mailpit) and its documented environment variables. Do not point smoke scripts at production data.

### Compose and frontend

```bash
docker compose config --quiet
docker compose up --build
```

In `web/`, install dependencies and run `npm run build`; CI also runs Playwright E2E tests after starting a PostgreSQL-backed API. Compose startup and the hosted Render deployment were not run or validated by this baseline inspection.

## Existing coverage map

| Area | Existing baseline evidence | Follow-up focus in Phase 1 |
|---|---|---|
| Authentication/configuration | `tests/test_security.py`, `tests/test_config_security.py`, `tests/test_auth_applications.py` | Invalid/inactive users, token edge cases, least-privilege checks and resource-scope matrix |
| Workflow/audit | `tests/test_workflow.py` | All role × transition combinations, no partial mutation on rejection, concurrent transition safety, audit integrity |
| Evidence | `tests/test_evidence.py`, `tests/test_evidence_attachments.py` | Cross-institution access, attachment/evidence/application mismatch, storage failure cleanup and finalized-case behavior |
| Compliance/notifications | `tests/test_notifications.py`, `tests/test_notification_worker.py`, `tests/test_notification_worker_logging.py`, `tests/test_notification_delivery.py` | UTC/date boundary consistency, duplicate worker runs, retries, inactive recipients and delivery observability |
| EVC | `tests/test_evc.py` | Role and application scope, legal state changes, eligibility assumptions and report/evidence linkage |
| Startup/database | `tests/test_health.py`, `tests/test_migration_startup.py`, CI PostgreSQL/Compose jobs | Migration upgrade from a clean database, repeat startup, real PostgreSQL differences vs SQLite test fixtures |
| Browser/product flow | `web/e2e/live-workflow.spec.ts`, `web/e2e/live-attachments.spec.ts`, `web/e2e/workspace.spec.ts` | Cross-role denial paths, session expiry, accessibility/usability regressions and production API configuration |

## Regression and risk inventory

Items below are hypotheses or known design boundaries to verify during subsequent chunks. They should not be treated as confirmed defects until reproduced.

1. **Authorization and resource scoping — highest priority.** Confirm every application/evidence/EVC/compliance/report operation enforces the same institution and regional scope at the API/service layer, independently of frontend visibility.
2. **Workflow transition integrity — highest priority.** Verify role authorization, expected-current-status conflicts, state changes, and audit-event creation remain atomic. Map the static transition rules and hard-coded role/status assumptions before changing them.
3. **Date/time correctness — high priority.** Compare expiry scans, compliance summaries, deadlines, and notification scheduling around UTC/local midnight and date boundaries. Establish one documented clock/date convention and deterministic tests.
4. **Background worker reliability — high priority.** Verify repeated runs are idempotent, retries are bounded, failures do not silently disappear, and production has a separately configured worker where needed. Source/CI coverage does not prove a hosted worker is running.
5. **Evidence and audit durability — high priority.** Verify file cleanup on database errors, authorization on every download, hash-chain validation after event tampering, and transaction behavior. Hash chains are tamper-evident, not an externally anchored immutable ledger; uploads are not malware-scanned in the current documented scope.
6. **EVC and compliance lifecycle — medium/high priority.** Trace eligibility and state transitions through service and API layers; identify any duplicated hard-coded statuses that can drift from workflow rules.
7. **Migration and database parity — medium/high priority.** Unit/API fixtures use in-memory SQLite, while CI separately tests PostgreSQL. Preserve the PostgreSQL migration/smoke checks for schema and concurrency-sensitive changes.
8. **Deployment configuration — medium priority.** Review secret/CORS/storage/worker settings and health checks. A passing GitHub workflow does not establish that Render is running the same commit or has all required environment variables and persistent storage.

## Phase 1 change discipline

- Keep all Phase 1 chunks on `phase-1/core-reliability-security`.
- Add a regression test before or with each behavior fix whenever practical.
- Prefer deterministic clocks and isolated test data; do not use live institutional data.
- Preserve synthetic/demo labels and human decision authority. Do not encode unverified AICTE rules as official requirements.
- No production deployment until all Phase 1 chunks pass their checks and the phase is reviewed.
