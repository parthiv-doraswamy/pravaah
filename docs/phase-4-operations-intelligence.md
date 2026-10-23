# Phase 4 — Operations Intelligence

Branch: `phase-4/operations-intelligence`

Phase 4 turns the workflow data already stored by PRAVAAH into scoped operational views. All aggregate metrics must respect the same server-side application visibility rules as the application register.

## Chunks

- [x] **Chunk 1 — Dashboard metrics and operational KPIs.** Added `GET /api/v1/operations/metrics`, returning role-scoped application status counts, active and awaiting-review totals, pending submission reviews, expired and near-expiry evidence, open escalations, failed notifications, and completed EVC visits with reports still pending. Added dashboard KPI cards backed by the API and tests for authentication, aggregate correctness, and institution scoping.
- [ ] **Chunk 2 — Pendency and workload analytics.**
- [ ] **Chunk 3 — Unified task inbox.**
- [ ] **Chunk 4 — Notification operations console.**
- [ ] **Chunk 5 — Reports and exports.**

## Metric semantics and limitations

- Metrics are computed from persisted records visible to the authenticated user's role and scope; client-side loaded-page counts are not used for the new operational KPI cards.
- “Awaiting review” is a configured set of workflow statuses, not an official regulatory service-level definition.
- “Evidence due within 7 days” includes dates from today through seven days ahead. Expired records are counted separately.
- “EVC reports pending” means the visit is marked completed while the report is not submitted.
- These metrics describe the prototype's data; they do not establish statutory compliance or replace human review.
