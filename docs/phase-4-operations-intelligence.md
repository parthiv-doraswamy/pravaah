# Phase 4 — Operations Intelligence

Branch: `phase-4/operations-intelligence`

Phase 4 turns the workflow data already stored by PRAVAAH into scoped operational views. All aggregate metrics must respect the same server-side application visibility rules as the application register.

## Chunks

- [x] **Chunk 1 — Dashboard metrics and operational KPIs.** Added `GET /api/v1/operations/metrics`, returning role-scoped application status counts, active and awaiting-review totals, pending submission reviews, expired and near-expiry evidence, open escalations, failed notifications, and completed EVC visits with reports still pending. Added dashboard KPI cards backed by the API and tests for authentication, aggregate correctness, and institution scoping.
- [x] **Chunk 2 — Pendency and workload analytics.** Added `GET /api/v1/operations/pendency` with scope-aware age buckets, workload by status (count, average age, oldest age), and the ten oldest pending cases. The dashboard now shows age distribution and institution-labelled oldest cases. Integration tests verify age bucketing and institution isolation.
- [ ] **Chunk 3 — Unified task inbox.**
- [ ] **Chunk 4 — Notification operations console.**
- [ ] **Chunk 5 — Reports and exports.**

## Pendency semantics and limitations

- Pending workload includes configured review stages from submitted through authority decision; drafts and terminal states are excluded.
- Waiting age uses `submitted_at` when present, otherwise the record's last-updated timestamp, then creation timestamp as a fallback. Age buckets are 0–2, 3–7, 8–14, and 15+ days.
- Oldest-case detail is capped at ten records, while bucket and per-status aggregates cover all visible pending applications.
- Aging is an operational indicator only; it does not encode official statutory service-level deadlines.

## Metric semantics and limitations

- Metrics are computed from persisted records visible to the authenticated user's role and scope; client-side loaded-page counts are not used for the new operational KPI cards.
- “Active” excludes completed, withdrawn, approved, and rejected applications. “Awaiting review” is a configured set of workflow statuses, not an official regulatory service-level definition.
- “Evidence due within 7 days” includes dates from today through seven days ahead. Expired records are counted separately.
- “EVC reports pending” means the visit is marked completed while the report is not submitted.
- These metrics describe the prototype's data; they do not establish statutory compliance or replace human review.
