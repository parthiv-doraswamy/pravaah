# Backend Development

## Prerequisites

- Docker with the Compose plugin, or Python 3.12+ and PostgreSQL 16 for a manual setup.
- Git for version control.

## Start the backend with Docker Compose

```bash
docker compose up --build
```

Compose starts PostgreSQL, waits for its health check, applies Alembic migrations, and starts the API. The local demo database credentials in `docker-compose.yml` are for local development only; never reuse them in a public or production deployment.

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

The initial health tests stub the database readiness function, so they do not require a running PostgreSQL instance. A real readiness request requires the configured database to be reachable.

## Apply migrations manually

After setting `DATABASE_URL` to a reachable PostgreSQL database:

```bash
alembic upgrade head
alembic current
```

Do not use `Base.metadata.create_all()` as a substitute for migrations in application environments.

## Initial schema

- `institutions`: institution identity and regional scope.
- `users`: user profile, active flag, role label, optional institution association.
- `applications`: application registry and current workflow status label.

Authentication, server-enforced authorization, audited workflow transitions, and tenant-scope enforcement are not implemented by these tables alone; those are separate follow-up chunks.
