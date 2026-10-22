# Backend Development

## Prerequisites

- Docker with the Compose plugin, or Python 3.12+ and PostgreSQL 16 for a manual setup.
- Git for version control.

## Start the backend with Docker Compose

```bash
docker compose up --build
```

Compose starts PostgreSQL, waits for its health check, applies Alembic migrations, seeds clearly synthetic local demo accounts and cases, starts the API, and launches the Vite frontend. The seeded institution and reviewer accounts use the local-only password `ChangeMe-LocalOnly-123!`; these credentials must never be reused outside this local Compose setup. The local demo database credentials in `docker-compose.yml` are for local development only; never reuse them in a public or production deployment.

- Frontend: `http://localhost:5173`
- API: `http://localhost:8000`
- OpenAPI docs: `http://localhost:8000/docs`
- Liveness: `http://localhost:8000/health/live`
- Readiness: `http://localhost:8000/health/ready`

Stop the services with `docker compose down`. To remove the local database volume too, run `docker compose down -v`; this permanently deletes local database data.

## Run tests without Docker

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest
ruff check app tests migrations
```

The initial health tests stub the database readiness function, so they do not require a running PostgreSQL instance. A real readiness request requires the configured database to be reachable. Authentication uses Argon2 password hashes and signed, short-lived bearer tokens. Set a unique `JWT_SECRET_KEY` (at least 32 characters) for any environment other than development or test; never commit real secrets.

## Apply migrations manually

After setting `DATABASE_URL` to a reachable PostgreSQL database:

```bash
alembic upgrade head
alembic current
```

Do not use `Base.metadata.create_all()` as a substitute for migrations in application environments.

## Domain schema and workflow endpoints

- `institutions`: institution identity and regional scope.
- `users`: user profile, active flag, role label, optional institution association, and password hash.
- `applications`: application registry and current workflow status label.
- `policy_versions`: versioned synthetic demo policy records with explicit source labels.
- `application_events`: ordered application events with previous-hash links and SHA-256 event hashes.

The current API includes:

- `POST /api/v1/auth/login` and `GET /api/v1/auth/me`
- `GET/POST /api/v1/applications` and `GET /api/v1/applications/{id}`
- `POST /api/v1/applications/{id}/transitions` for role-guarded state changes with an expected-current-status check
- `GET /api/v1/applications/{id}/events` and `GET /api/v1/applications/{id}/events/verify`
- `GET /api/v1/applications/policies/registry`

Demo policy values and target durations are illustrative, not official AICTE rules or legal deadlines. Final approval and rejection remain explicit human actions. The event chain is tamper-evident and verifiable; it is not a substitute for access-controlled storage, backups, or an externally anchored audit log.


## Evidence metadata and expiry tracking

The `application_evidence` table stores evidence title, category, reference number, optional issue/expiry dates, optional policy key, notes, creator, and timestamps. The `evidence_attachments` table stores metadata for private files persisted outside the database under `EVIDENCE_STORAGE_DIR` (default `./var/uploads`; Docker Compose mounts a named volume at `/data/uploads`). The default upload cap is 10 MiB and can be changed with `EVIDENCE_MAX_UPLOAD_BYTES`.

- `GET /api/v1/applications/{id}/evidence` lists evidence metadata for an application visible to the current user.
- `POST /api/v1/applications/{id}/evidence` registers metadata for a visible application. Writer roles are checked server-side, and expiry cannot precede issue date.
- Each registration appends an `evidence_registered` event to the application's hash chain so the record is included in audit verification.
- `GET /api/v1/applications/{id}/evidence/{evidence_id}/attachments` lists file metadata for a registered evidence item.
- `POST /api/v1/applications/{id}/evidence/{evidence_id}/attachments` accepts a multipart field named `file`; writer roles are checked server-side. Only PDF, PNG, and JPEG extensions with matching file signatures are accepted. The server generates a random storage key, computes SHA-256, enforces the configured byte limit, and records an `evidence_file_uploaded` audit event.
- `GET /api/v1/applications/{id}/evidence/{evidence_id}/attachments/{attachment_id}/download` streams a private attachment only after application-scope and evidence-link checks. Download responses include `X-Content-Type-Options: nosniff` and private no-store caching.

This prototype does not yet perform malware scanning, PDF/image content sanitization, virus quarantine, external object storage, or file-retention cleanup. File-signature checks are not a guarantee that a file is safe. Expiry badges are display-level warnings, not legal determinations or a substitute for a verified policy engine.


## Compliance overview and expiry warnings

`GET /api/v1/compliance/overview` returns a summary for evidence attached to applications visible to the authenticated user. It counts expired records, records due within one day, within seven days, within thirty days, and records without an expiry date. The response includes alert rows for expired and near-expiry records and the date on which the summary was computed.

The warning windows `[30, 7, 1]` are synthetic demo defaults, not official AICTE rules. This endpoint computes the overview when requested. A separate Compose worker also scans expiry dates periodically and records escalations using a synthetic threshold documented below. Institution and regional scoping are applied server-side.


## In-app notification queue

The `notification_records` table stores recipient-scoped in-app notifications, a unique deduplication key, severity, read timestamp, and delivery bookkeeping (`delivery_status`, attempt count, retry ceiling, next-attempt timestamp, and last error). The notification API provides:

- `GET /api/v1/notifications?unread_only=true` — list notifications belonging to the authenticated user.
- `POST /api/v1/notifications/{notification_id}/read` — mark only the recipient's notification as read.
- `POST /api/v1/notifications/queue-expiry` — reviewer/admin roles can queue idempotent expiry reminders for institution users associated with visible cases.

Newly queued expiry reminders add an event to the application's tamper-evident timeline. The dedupe key is based on the evidence record, expiry date, severity window, and recipient; repeated queue runs skip existing reminders. Records are immediately available in the in-app notification center. The scheduled worker, optional SMTP email transport, retry attempt logging, and escalation records are described in the scheduled worker section below. SMS delivery is not implemented. Warning windows remain synthetic demo defaults, not official AICTE deadlines.


## Scheduled notification worker and escalation handling

Docker Compose starts a separate notification-worker process. It runs an expiry scan every NOTIFICATION_WORKER_INTERVAL_SECONDS (default 300 seconds), creates deduplicated in-app expiry notifications, and opens a compliance escalation when evidence has been expired for more than the synthetic seven-day threshold. Both operations append events to the application audit timeline. The threshold is a prototype assumption, not an official AICTE requirement.

The worker also processes due email notifications if SMTP is configured. Set SMTP_HOST, SMTP_PORT, SMTP_FROM, and optional SMTP_USERNAME, SMTP_PASSWORD, and SMTP_USE_TLS in the local environment. Keep credentials out of source control. Without SMTP_HOST and SMTP_FROM, the worker deliberately leaves email delivery pending while in-app notifications remain available; it does not claim that email was sent.

Each actual email attempt is recorded in notification_attempts. Transient failures schedule retries with exponential backoff starting at five minutes and capped at sixty minutes. Once the notification reaches its configured attempt limit, its delivery status becomes failed. The transport is SMTP email only; SMS, provider webhooks, and delivery guarantees beyond the SMTP response are not implemented.

- GET /api/v1/compliance/escalations lists escalations in the authenticated user's application scope.
- POST /api/v1/compliance/escalations/{id}/resolve lets authorized review roles resolve an escalation; the action is written to the application timeline.
- python -m scripts.notification_worker --once runs one scan and delivery pass for local diagnostics.

The worker and migrations have been committed but must still be executed in CI or a local environment before treating the workflow as runtime-verified.
