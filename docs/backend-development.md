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
