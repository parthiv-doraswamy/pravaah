# PRAVAAH Supabase public-schema hardening runbook

Status: **draft for review; not executed**  
Project: dedicated PRAVAAH Supabase project `sygujugakrgofpsepgyf`  
Scope: PRAVAAH only. Do not run against VitalGuard AI or another project.

## Why this is needed

The read-only audit on 2026-10-23 found 12 application tables in `public` with RLS disabled and broad table privileges for `anon` and `authenticated`. No RLS policies were present. Default privileges also grant these roles privileges on future objects. The connection tested manually from a developer Mac used the `postgres` role; this does **not** prove the deployed Render service uses the same role.

The API currently uses SQLAlchemy's `DATABASE_URL` and automatically runs Alembic migrations at startup when `APP_ENV=production`. Do not place this operational SQL in an Alembic migration or merge/deploy it automatically without a separate deployment plan.

## Preconditions

- Confirm the project ref in the Supabase dashboard is exactly `sygujugakrgofpsepgyf`.
- Confirm a recent recoverable backup/restore point exists and the operator has permission to restore it.
- Confirm Render's actual runtime role without displaying connection secrets. Do not assume it is `postgres` based on a separate local connection.
- Inspect the current grants, default ACLs, functions, sequences, views, and Supabase Data API exposure settings immediately before applying.
- Rehearse on a disposable PostgreSQL/Supabase project first, then test login, institution scoping, application CRUD and transitions, evidence upload/download, EVC visits/reports, notification jobs, and Alembic upgrade.
- Schedule a controlled window. This script is a proposed containment step, not a substitute for application-level authorization tests.

## Proposed transactional containment SQL

Review against a fresh catalog snapshot before running. It intentionally does not add broad RLS policies and does not grant access to public client roles. It preserves existing `service_role` grants and does not use `FORCE ROW LEVEL SECURITY`.

```sql
BEGIN;

-- Remove direct Data API table access from client-facing roles.
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM anon, authenticated;

-- Defense in depth for the currently audited application tables.
ALTER TABLE public.alembic_version ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.institutions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.policy_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.application_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.application_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notification_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.compliance_escalations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notification_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evc_visits ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evidence_attachments ENABLE ROW LEVEL SECURITY;

-- Stop the audited object creators from regranting client-role access by default.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE ALL PRIVILEGES ON TABLES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE ALL PRIVILEGES ON SEQUENCES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE EXECUTE ON FUNCTIONS FROM anon, authenticated;

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public
  REVOKE ALL PRIVILEGES ON TABLES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public
  REVOKE ALL PRIVILEGES ON SEQUENCES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public
  REVOKE EXECUTE ON FUNCTIONS FROM anon, authenticated;

COMMIT;
```

### Important caveats before execution

- Run only after confirming the current project and the catalog snapshot. If a role/object is missing or an ACL differs from the audit, stop and revise the script rather than improvising.
- Default privileges are per object-creating role. This draft covers the two roles identified in the earlier audit; inspect all rows in `pg_default_acl` and add only relevant creators.
- The SQL does not revoke `PUBLIC` function execution defaults. Inventory functions and their `SECURITY DEFINER` status separately; decide any `PUBLIC` revocation per function after reviewing legitimate callers.
- RLS enabled without policies denies normal roles that have table privileges. The intent here is to remove client-role table privileges while the FastAPI backend continues using its trusted DB role. Verify the actual Render role before applying.
- The `postgres` role bypasses RLS in this project, so RLS is defense-in-depth; it is not a replacement for least-privilege credentials or API authorization.
- Do not use `FORCE ROW LEVEL SECURITY` without testing migration ownership and every backend workflow.

## Verification queries (read-only)

Run immediately after the proposed change:

```sql
-- No client-facing table privileges should remain on the audited tables.
SELECT c.relname AS table_name,
       has_table_privilege('anon', c.oid, 'SELECT') AS anon_select,
       has_table_privilege('anon', c.oid, 'INSERT') AS anon_insert,
       has_table_privilege('authenticated', c.oid, 'SELECT') AS authenticated_select,
       has_table_privilege('authenticated', c.oid, 'INSERT') AS authenticated_insert,
       c.relrowsecurity AS rls_enabled
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
ORDER BY c.relname;

-- Inspect remaining default privileges (review all rows, not only these roles).
SELECT pg_get_userbyid(d.defaclrole) AS creator_role,
       n.nspname AS schema_name,
       d.defaclobjtype AS object_type,
       d.defaclacl AS default_acl
FROM pg_default_acl d
LEFT JOIN pg_namespace n ON n.oid = d.defaclnamespace
WHERE n.nspname = 'public'
ORDER BY creator_role, object_type;
```

Expected for the 12 audited tables: RLS enabled and the `anon`/`authenticated` table privilege checks false. Review all remaining default ACLs for unintended client-role grants.

## Rollback

Do not improvise a blanket rollback. Before applying, export the exact table ACLs, sequence ACLs, function ACLs, default ACLs, RLS flags, and policies to a secure change record. If application checks fail, stop traffic if necessary and restore only the captured grants/flags/default ACLs in a reviewed transaction. Do not grant `ALL` back to `anon` or `authenticated` as a shortcut. Re-test all workflows before reopening traffic.

## Acceptance checklist

- [ ] Confirmed project ref and backup/restore readiness.
- [ ] Confirmed Render's runtime DB role safely.
- [ ] Captured pre-change ACL/RLS/default-ACL inventory.
- [ ] Rehearsed the exact change in a disposable environment.
- [ ] Confirmed no unintended direct Data API access.
- [ ] Passed backend tests and end-to-end workflows.
- [ ] Verified readiness and migrations after controlled application.
- [ ] Saved post-change verification output and a tested rollback procedure.

No production database change is authorized by this document.
