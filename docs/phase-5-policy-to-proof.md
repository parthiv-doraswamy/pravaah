# Phase 5 — Policy-to-Proof Traceability

## Chunk 1: Application dossier API

### Delivered

The read-only endpoint `GET /api/v1/applications/{application_id}/policy-to-proof` assembles the records that help a human reviewer trace a case from policy provenance to evidence and recorded actions:

- application identity and current workflow status;
- policy versions referenced by evidence metadata or workflow event metadata;
- evidence metadata, expiry and version lineage;
- attachment metadata and SHA-256 checksums (never the file bytes or private storage keys);
- compliance submission versions and review status;
- EVC visit and outcome-report metadata, including linked evidence IDs;
- notification delivery state and related compliance escalations;
- the ordered application event history and a fresh hash-chain verification result.

The endpoint uses the same server-side application-scope query as the application registry. A caller who cannot view an application receives `404`, without confirmation that the record exists. Results are read-only and bounded per record family to avoid unbounded responses.

### Interpretation and limits

The dossier is an evidence-navigation and explainability aid, not an automated approval recommendation or statutory decision. Policy labels and rules can be synthetic demonstration assumptions; this endpoint does not validate them against official AICTE publications. Hash-chain verification is tamper-evident integrity checking, not proof against an administrator who can rewrite the database and recompute hashes.

### Verification

Integration coverage checks policy/evidence linkage, valid audit-chain reporting, disclaimer visibility, unauthenticated access denial, and institution-scope isolation. CI remains the authoritative test result for the branch; this document alone is not a claim that the test suite passed.


## Chunk 2: Application workspace integration

### Delivered

The application detail screen now loads the dossier automatically and presents it as a dedicated Policy-to-Proof panel. Reviewers can refresh the dossier, inspect policy provenance, evidence and file checksums, compliance submission versions, EVC visits and reports, notification/escalation records, and the event hashes. Summary counts and a clear audit-chain status make the amount and integrity state of recorded data visible at a glance.

The panel has loading, request-error, retry and empty states. Related record groups use collapsible sections so the case screen stays navigable. The UI uses the authenticated API client and does not bypass server-side scope checks. A browser end-to-end test covers loading the dossier and displaying policy provenance.

The displayed audit status is limited to the server's hash-chain check. A valid hash chain is not an external trust anchor and cannot establish that an underlying policy is official. The panel repeats the human-review disclaimer to avoid implying that traceability equals certification or approval.

## Chunk 3: Integrity and regression hardening

### Delivered

- Added an integration regression test proving that the dossier exposes attachment filename and SHA-256 metadata without exposing private storage keys.
- Added a tampering test that modifies a persisted event after its hash was recorded and confirms the dossier reports an invalid audit chain and identifies the first invalid sequence.
- Fixed two Playwright assertions that became ambiguous after the new dossier panel introduced a second visible “Audit chain verified” status. The assertions now select the intended first status while retaining the existing end-to-end coverage.

### Verification notes

The prior backend test, lint, frontend build, PostgreSQL smoke, SMTP smoke, Compose configuration, and Compose reliability jobs passed. The prior frontend end-to-end job failed only on strict-mode locator ambiguity for the duplicated audit status text; the updated assertions address that observed failure. The updated branch's CI run remains the source of truth for the fixes.

## Chunk 4: Portable dossier export

### Delivered

- Added an **Export JSON** action to the Policy-to-Proof panel, alongside refresh.
- Exports the dossier currently shown on screen, including its as-of timestamp, counts, policy provenance, evidence and attachment checksums, review records, notification/escalation state, and audit verification result.
- The download filename is derived from the application number after removing unsafe filename characters. The export uses the API's existing response, so it does not make an additional request or bypass application-scope authorization.
- Added browser end-to-end coverage for the JSON download and expected filename, with responsive action styling.

The export is a point-in-time copy of the dossier response. It does not include attachment bytes or private storage keys, and it does not convert a hash-chain result into an official certification.

