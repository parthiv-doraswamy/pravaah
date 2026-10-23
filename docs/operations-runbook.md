# PRAVAAH Operations Runbook

This runbook describes the repository's **local Docker Compose prototype**. It is not a production deployment guide. The current Compose file uses development credentials, sets `APP_ENV=development`, publishes PostgreSQL on the host, and uses a Vite development server. Do not expose this configuration to the public internet or use real institution records with it.

## 1. Start and verify the stack

From the repository root:

```bash
docker compose config --quiet
docker compose up --build -d
docker compose ps
```

Wait for the API health check to become healthy. The API startup command applies Alembic migrations, runs the idempotent synthetic demo seed, and then starts Uvicorn.

Check health endpoints:

```bash
curl --fail http://localhost:8000/health/live
curl --fail http://localhost:8000/health/ready
```

- **Liveness** indicates the API process is responding.
- **Readiness** additionally depends on the configured database being reachable.
- Frontend: `http://localhost:5173`
- API documentation: `http://localhost:8000/docs`

Inspect status and recent logs:

```bash
docker compose ps
docker compose logs --tail=150 api
docker compose logs --tail=150 db
docker compose logs --tail=150 notification-worker
docker compose logs --tail=150 web
```

Avoid copying logs into public issues without checking them for sensitive operational details. Do not print environment variables or credentials into logs.

## 2. Restart and seed behavior

Restart services without deleting their volumes:

```bash
docker compose restart api notification-worker
docker compose ps
curl --fail http://localhost:8000/health/ready
```

The Compose services use `restart: unless-stopped`. This helps recover from a process exit but does not guarantee recovery from data corruption, host loss, bad migrations, or exhausted storage.

The API runs `python -m scripts.seed_demo` at startup. The seed routine is designed to be idempotent and uses clearly synthetic demo accounts and records. Never use a demo seed password in a deployed environment. A restart should not be treated as a database reset.

**Data-loss warning:** `docker compose down -v` removes the Compose project's named volumes, including the local PostgreSQL data and uploaded evidence files. Do not run it if you need to retain local data.

## 3. Back up PostgreSQL and evidence files

Back up the database and private upload volume together so attachment metadata and file bytes can be recovered as a consistent pair. Create a restricted backup directory first:

```bash
mkdir -p backups
chmod 700 backups
docker compose exec -T db pg_dump -U pravaah -d pravaah > backups/pravaah-postgres.sql
```

Find the actual Compose-created upload volume name (Compose prefixes it with the project name):

```bash
docker volume ls
```

Then replace `<actual_upload_volume_name>` with the exact volume shown by that command:

```bash
docker run --rm \
  -v <actual_upload_volume_name>:/data:ro \
  -v "$PWD/backups:/backup" \
  alpine sh -c 'tar -czf /backup/pravaah-uploads.tar.gz -C /data .'
```

Keep database and upload backups in access-controlled storage. Do not commit backups to Git. For any non-disposable environment, encrypt backups, restrict access, define retention, and periodically test restores.

### Restore precautions

A restore can overwrite or duplicate application data. Restore only after confirming the target environment and obtaining an explicit backup/restore plan. Prefer restoring into a **separate, fresh database and fresh upload volume** first, then verify application IDs, attachment IDs, file hashes, and audit-chain verification before switching traffic.

For a disposable local database, the SQL dump can be loaded with:

```bash
cat backups/pravaah-postgres.sql | docker compose exec -T db psql -U pravaah -d pravaah
```

That command is **not** a safe in-place recovery recipe for a populated database: it may fail on existing objects or cause conflicts. Do not use it against important data without a tested, target-specific restore plan. The upload archive must be extracted into the corresponding upload volume; ensure file ownership and permissions match the API container's runtime user. After restoring, check that every database attachment row points to an available file and that the downloaded bytes match the stored SHA-256 value.

## 4. Notification worker and SMTP

Inspect the worker:

```bash
docker compose logs --tail=150 notification-worker
```

Without `SMTP_HOST` and `SMTP_FROM`, email delivery is deliberately deferred; in-app notifications can still be queued. This is not evidence that an email was sent. To test real email delivery, configure a dedicated test SMTP account using uncommitted environment settings, send only to an authorized test mailbox, and verify receipt and retry behavior. Never put SMTP credentials in source control or paste them into logs/issues.

The expiry thresholds and escalation timing in this prototype are synthetic demo defaults, not official AICTE deadlines.

## 5. Common checks

| Symptom | Checks |
| --- | --- |
| API is unhealthy | Inspect `docker compose ps`, API logs, DB health, and `/health/ready`. |
| Frontend cannot reach API | Confirm both services are running and the browser can reach `http://localhost:8000`; check `VITE_API_BASE_URL` and CORS configuration. |
| Login fails after a reset/reseed | Use the local-only synthetic demo credentials documented in the development guide; do not change credentials on a deployed environment without a controlled plan. |
| Attachment metadata exists but download returns 404 | Confirm the named upload volume is mounted at `/data/uploads`, the file exists, and the database and upload volume came from the same backup set. |
| Email stays pending | Confirm whether SMTP is configured; inspect worker logs and notification attempt records without exposing credentials. |
| Migrations fail at startup | Preserve the database volume, capture sanitized logs, and inspect the current Alembic revision before attempting any rollback or destructive reset. |

## 6. Production-readiness gaps

Before any real deployment, replace the development Compose defaults with deployment-specific configuration and secret management; remove public database exposure; configure HTTPS and trusted CORS origins; use a strong unique JWT secret; create managed database backups and recovery drills; add monitoring and alerting; decide attachment malware scanning, retention, and external/private object storage; and verify the real deployment after restart/redeploy. The SHA-256 audit chain is tamper-evident within the application's data store but is not an independently anchored immutable log.
