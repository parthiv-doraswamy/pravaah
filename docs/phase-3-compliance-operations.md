# Phase 3 — End-to-end compliance operations

## Chunk 1: Undertaking and compliance submission lifecycle

This chunk introduces versioned compliance submission records tied to an application. Submissions capture a typed undertaking, declaration, linked evidence IDs, submission actor, and timestamp. A new submission is persisted as submitted, and its creation is added to the application's tamper-evident event chain.

### API

- `POST /api/v1/compliance/applications/{application_id}/submissions` creates a submission.
- `GET /api/v1/compliance/applications/{application_id}/submissions` lists submissions for a visible application.
- `GET /api/v1/compliance/submissions` lists submissions inside the authenticated user's permitted application scope; an optional `status` filter is supported.

### Validation and safety

- The authenticated user must have a submission-capable role and must be authorized to access the application.
- At least one evidence record is required; evidence identifiers must be unique and belong to the same application.
- New submissions increment the version for the same submission type and application.
- Each submission is recorded in the application audit chain.
- This is a configurable application workflow, not a statement of official AICTE requirements. Final approval/rejection remains a human action.

### Verification
- Frontend detail view now lists submission versions and reviewer decisions, supports accepting/rejecting/requesting changes, and offers a correction form to institution users.
- Frontend API client exposes list, create, review, and resubmit operations.

Run `pytest tests/test_compliance_submissions.py` and `ruff check app tests`, then run the repository's full CI workflow before marking the chunk complete.


## Chunk 3: EVC eligibility, scheduling, and report lifecycle

- Added a scoped eligibility endpoint: `GET /api/v1/evc/applications/{application_id}/eligibility`.
- Eligibility reports whether the application is in an allowed active-review status and whether an existing scheduled visit blocks another booking.
- Scheduling rechecks the same server-side rules under an application row lock; a second active scheduled visit is rejected with HTTP 409.
- The scheduling UI checks eligibility before enabling confirmation and explains blocking reasons.
- Existing report lifecycle remains: reports can be saved as drafts only after visit completion; submitted reports are locked, checklist sections are validated, linked evidence must belong to the same application, and report changes are audit-recorded.
- Eligibility rules are application workflow configuration, not official AICTE policy. EVC scheduling and reports do not themselves approve or reject an application.

### Verification
- Added integration coverage for eligibility state, active-visit conflicts, and duplicate-schedule rejection.
- Run `pytest tests/test_evc.py`, `ruff check app tests`, frontend production build, and the full CI suite.


## Chunk 4: Evidence renewal, versioning, and expiry

- Evidence records now carry a version number, a link to the prior record, and a lifecycle state (`current` or `replaced`). Expiry remains derived from the recorded expiry date; a replaced record is retained for history.
- Added `POST /api/v1/applications/{application_id}/evidence/{evidence_id}/renewals`. It is access-scoped, rejects finalized applications and already-replaced versions, requires a new future expiry date, and creates the next linked version.
- Renewal writes an `evidence_renewed` application audit event. The prior metadata remains available and its lifecycle state becomes `replaced`; attachments and prior audit references are not deleted.
- The evidence workspace now displays version/lifecycle lineage and submits the renewal form to the dedicated renewal endpoint instead of creating an unrelated record.
- Expiry alerts and overview continue to derive expired/near-expiry state from dates and existing configurable demo warning windows. These windows are illustrative, not official AICTE deadlines.

### Verification
- Added tests for renewal lineage, preserving the previous reference, event-chain history, duplicate renewal rejection, and expired renewal date rejection.
- Run `pytest tests/test_evidence.py tests/test_evidence_attachments.py tests/test_evidence_integrity.py`, `ruff check app tests`, frontend production build, and the full CI suite.
