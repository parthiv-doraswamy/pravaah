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
