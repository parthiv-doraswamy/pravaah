# PRAVAAH

**Policy-Driven Approval Workflow, Compliance and Deadline Intelligence for AICTE**

PRAVAAH is a prototype for transparent, policy-driven approval workflow coordination, compliance tracking, deadline monitoring, notification reliability, and auditable case history. It is designed for synthetic demonstration data; it is not an official AICTE system and does not replace decisions by authorised human officials.

## Project status

**Status: Backend foundation, workflow timeline, policy registry, and evidence metadata slice committed.** Login, institution-scoped application records, guarded transitions, synthetic policy versions, event-chain verification, and evidence metadata/expiry tracking are implemented. Build and test execution still need confirmation by CI or a local run.

## Planned stack

- **Frontend:** React, TypeScript, Vite, Tailwind CSS
- **Backend:** Python, FastAPI, Pydantic
- **Database:** PostgreSQL, SQLAlchemy, Alembic
- **Testing:** pytest, Hypothesis, Playwright
- **Local orchestration:** Docker Compose

Exact versions will be pinned and verified as the project is bootstrapped.

## Core capabilities

- Signed bearer-token login with Argon2 password hashing and server-side role checks
- Institution-scoped application registry with search, status filtering, and pagination
- Versioned synthetic policy registry with explicit provenance labels (not represented as official AICTE rules)
- Role-guarded state transitions with stale-state conflict protection
- Append-only application event timeline with SHA-256 hash-chain verification
- Evidence metadata registry with optional policy linkage and expiry-date visibility (file uploads are not implemented yet)
- Application intake, scrutiny, returns, and resubmissions
- Policy-to-Proof case timeline
- Deadline provenance, undertakings, and compliance evidence
- Secure document validity and renewal tracking
- Reliable notifications, retries, and escalations
- EVC queue and scheduling history
- Stage-wise pendency and operational reporting
- Tamper-evident audit history and verification

## Safety and accuracy principles

- Demonstration records and simulated integrations must be clearly labelled.
- Regulatory workflow and deadline rules remain demo assumptions until verified against authoritative, applicable AICTE sources.
- Statutory decisions remain with authorised human authorities.
- Secrets and credentials must never be committed to source control.
- Backend authorization is mandatory; hiding a UI control is not an access-control mechanism.
- A feature is only described as working after its relevant tests and workflows have been verified.

## Development roadmap

1. Requirements and policy assumptions
2. Application shell, design system, API, and database foundation
3. Identity, scoped authorization, and application registry
4. Versioned policy registry and workflow engine
5. Deadline, compliance, and document modules
6. Notification outbox, retries, and audit integrity
7. EVC, dashboards, and reporting
8. Security testing, end-to-end verification, and deployment

## Repository layout (target)

```text
app/        FastAPI backend and domain modules
web/        React frontend
policies/   Versioned policy schemas and demo configurations
migrations/ Database migrations
tests/      Unit, integration, property, security, and E2E tests
docs/       Requirements, architecture, and decisions
scripts/    Local development and demo utilities
```

The layout will be established incrementally so every commit remains understandable and verifiable.

## Getting started

Start the frontend, API, and PostgreSQL database with Docker Compose:

```bash
docker compose up --build
```

Open the PRAVAAH frontend at `http://localhost:5173` and the API documentation at `http://localhost:8000/docs`. Local synthetic demo accounts are seeded on startup: `demo.institution@example.test` and `demo.reviewer@example.test`, both using the local-only password `ChangeMe-LocalOnly-123!`. These credentials are for the Compose development environment only and must never be reused in a deployed environment. For test and migration details, see [`docs/backend-development.md`](docs/backend-development.md). This command has been configured in the repository but has not yet been executed in this session.

## Disclaimer

PRAVAAH is an independent prototype for a software competition. It is not affiliated with or endorsed by AICTE. Use synthetic data only unless formal authorization for any real integration is obtained.
