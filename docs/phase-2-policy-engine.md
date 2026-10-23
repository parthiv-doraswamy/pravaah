# Phase 2 — Configurable policy engine

## Policy rule schema v1

`PolicyVersion.rules_schema_version` identifies the JSON contract used by a policy record. Existing records are migrated with version `1`; an empty rules object remains valid and represents no additional configured rules. Unknown schema versions are rejected rather than guessed.

The v1 contract is defined in `app/schemas/policy_rules.py`:

- **Transitions** describe source status, target status, allowed application roles, and whether a human decision is required.
- **Prerequisites** describe required application fields and evidence categories at a status.
- **Deadlines** describe an event, a bounded number of days, reminder offsets, and an optional escalation offset.

Validation rejects unknown fields, unsupported roles/statuses/events, duplicate rule keys, invalid bounds, and final approval/rejection rules that do not explicitly require human approval.

## Safety and compatibility

- These are configurable application rules and synthetic demo examples, not official AICTE policy.
- Final approval/rejection remains a human action; configuration cannot authorize automatic final decisions.
- This chunk defines and validates the schema only. Workflow execution will be wired to policies in later chunks, with compatibility tests and fail-closed behavior.
- Do not activate a policy in production merely because it validates. Activation needs a reviewed policy source, effective date, and human approval process.
