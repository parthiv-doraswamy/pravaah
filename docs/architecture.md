# PRAVAAH — Initial Architecture

## Status

This document describes the planned architecture, not a claim that all modules already exist. The initial repository foundation contains the FastAPI entry point, environment-backed settings, and health smoke tests. Database-backed readiness, authentication, workflow rules, and UI pages are future implementation work.

## System boundaries

- **Web client:** React + TypeScript + Vite; renders role-specific workspaces and calls the API.
- **API:** FastAPI; validates requests, authenticates callers, checks permissions, and coordinates domain services.
- **Relational storage:** PostgreSQL with SQLAlchemy and Alembic; persists applications, policies, tasks, deadlines, events, and notification records.
- **Workflow and policy:** deterministic, versioned policy configuration plus explicit transition guards.
- **Background processing:** database-backed notification outbox and worker with idempotency and retry records.
- **Private document storage:** private local storage for development, replaceable with private object storage in hosted environments.

## Transactional case changes

An accepted workflow transition should update the application state, append the case event, and create any notification intent within one database transaction. Rejected transitions should not partially mutate the case. Concurrency checks should prevent a stale request from silently overwriting a newer state.

## Policy provenance

Each policy version should be validated and immutable after publication. Case events and deadline records should refer to the exact policy version used. Until checked against the applicable official AICTE handbook and amendments, workflow and deadline configurations must be marked as demo assumptions.

## Security boundaries

- Deny access by default and authorize on the server for every protected operation.
- Scope institution and regional data access at the data-access/service layer, not only in UI filters.
- Keep credentials in environment configuration or a secret manager.
- Store uploaded documents privately and validate content, size, and file signatures.
- Use synthetic records in public demos; do not connect to live AICTE systems without formal authorization.
- Audit hash chains are tamper-evident, not absolute proof of immutability.

## Current API contract

- `GET /health/live`: process liveness only.
- `GET /health/ready`: placeholder readiness response until dependency checks are implemented.

The readiness endpoint must be upgraded to check actual dependencies before being used as a deployment health gate.

## Planned delivery order

1. Requirements and demo policy assumptions.
2. Backend package, settings, health endpoints, and smoke tests.
3. Database models, migrations, seed data, and scoped identity foundation.
4. Application registry and guarded workflow engine.
5. Deadline, compliance, and document services.
6. Outbox, worker, notifications, and audit verification.
7. EVC operations, dashboards, and reports.
8. Security, browser end-to-end tests, and deployment hardening.
