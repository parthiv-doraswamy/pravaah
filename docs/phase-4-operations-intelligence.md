# Phase 4 — Operations Intelligence

Branch: `phase-4/operations-intelligence`

Phase 4 turns the workflow data already stored by PRAVAAH into scoped operational views. All aggregate metrics must respect the same server-side application visibility rules as the application register.

## Chunks

- [x] **Chunk 1 — Dashboard metrics and operational KPIs.** Added `GET /api/v1/operations/metrics`, returning role-scoped application status counts, active and awaiting-review totals, pending submission reviews, expired and near-expiry evidence, open escalations, failed notifications, and completed EVC visits with reports still pending. Added dashboard KPI cards backed by the API and tests for authentication, aggregate correctness, and institution scoping.
- [x] **Chunk 2 — Pendency and workload analytics.** Added `GET /api/v1/operations/pendency` with scope-aware age buckets, workload by status (count, average age, oldest age), and the ten oldest pending cases. The dashboard now shows age distribution and institution-labelled oldest cases. Integration tests verify age bucketing and institution isolation.
- [x] **Chunk 3 — Unified task inbox.** Added `GET /api/v1/operations/inbox` and a role-aware task inbox for application workflow actions, compliance submission reviews/corrections, expiring current evidence, open escalations, pending EVC reports, and failed notification deliveries for the signed-in user. The UI groups counts by priority, filters by priority, and links tasks to their relevant workspace. Tests cover authentication, institution isolation, and the browser inbox flow.
- [x] **Chunk 4 — Notification operations console.** Added role-gated `GET /api/v1/notifications/operations` with status counts, retry-eligible/exhausted counts, and the latest 100 notification records within the user's server-authorized application scope. Added an operations-only retry endpoint that enforces scope and retry limits, preserves attempt history, and appends an audit event. The new UI has delivery health cards, status filtering, failure context, retry actions, and idempotent expiry-alert queueing. Integration and browser tests cover role restrictions and recovery.
- [x] **Chunk 5 — Reports and exports.** Added authenticated CSV exports for application register, compliance submissions, evidence register, EVC visits/reports, and notification delivery records. Optional date filters are validated server-side; every export uses the same application visibility scope as the register. CSV cells are protected against spreadsheet-formula injection, downloads are marked no-store, and the workspace includes report descriptions, date controls, export actions, and limitations. Integration and browser tests cover access scoping, authentication, date validation, and a CSV download.

## Notification operations semantics and limitations

- The operations console is restricted to notification-queue roles. Both listing and manual retry enforce the application's server-side visibility scope; an operations role does not grant access to notifications attached to unrelated applications.
- Status counts cover all visible notification records, while the console returns the latest 100 records ordered by creation time. Failed records at ten attempts are marked exhausted and cannot be manually retried.
- Retry changes a failed record to pending, schedules an immediate next attempt, clears the current error field, preserves the attempt count, adjusts the attempt ceiling only when necessary, and writes an application audit event. It does not itself send email or guarantee delivery.
- The queue-expiry action is idempotent. The current prototype's delivery worker/provider configuration remains a separate concern; UI status must not be interpreted as provider-confirmed delivery unless a worker records that result.

## Task inbox semantics and limitations

- Task candidates are built from persisted records in the authenticated user's server-authorized application scope. Application workflow tasks are role/status-based; compliance review tasks are limited to review-capable roles, correction tasks to institution users, and EVC report tasks to configured EVC/operations roles.
- Evidence tasks include only current evidence with an expiry date within the next 30 days or already expired. Replaced evidence is excluded. Failed notification tasks are limited to failed deliveries addressed to the signed-in user.
- Tasks are ordered by priority (high, medium, low), then oldest record date, and the response returns at most 100 items. Counts describe the returned task set before the display cap; this is a task queue, not a statutory deadline or assignment engine.
- Opening a task navigates to the relevant workspace. Each write action remains subject to its existing server-side authorization checks.

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


## Reports and exports semantics and limitations

- Export routes are `GET /api/v1/operations/reports/{report_type}/export`; supported report types are `applications`, `compliance`, `evidence`, `evc`, and `notifications`. Unknown report types return 404.
- Optional `from_date` and `to_date` filters are ISO dates and reject a start date later than the end date. The relevant timestamp is application creation, submission creation, evidence creation, EVC scheduled date, or notification creation, depending on report type.
- Each query derives visible application IDs from the same server-side application-scope helper used by the application register. The exports do not depend on client-side filtering or the current page of loaded applications.
- CSV exports contain persisted record data and use UTF-8 with a byte-order mark for spreadsheet compatibility. Text cells beginning with spreadsheet formula markers are escaped. Responses include an attachment filename and `Cache-Control: no-store`.
- The compliance export is the submission lifecycle report; evidence metadata is exported separately. Exports do not include binary evidence attachments or secrets. Notification rows show the recorded delivery state and error field, not independent provider confirmation. Data is a point-in-time operational extract and does not certify statutory compliance.
