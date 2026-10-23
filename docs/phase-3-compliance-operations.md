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

Run `pytest tests/test_compliance_submissions.py` and `ruff check app tests`, then run the repository's full CI workflow before marking the chunk complete.
