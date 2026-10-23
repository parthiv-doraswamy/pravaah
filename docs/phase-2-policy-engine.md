# Phase 2 — Configurable policy engine

## Policy rule schema v1

`PolicyVersion.rules_schema_version` identifies the JSON contract used by a policy record. Existing records are migrated with version `1`; an empty rules object remains valid and represents no additional configured rules. Unknown schema versions are rejected rather than guessed.

The v1 contract is defined in `app/schemas/policy_rules.py`:

- **Transitions** describe source status, target status, allowed application roles, and whether a human decision is required.
- **Prerequisites** describe required application fields and evidence categories at a status.
- **Deadlines** describe an event, a bounded number of days, reminder offsets, and an optional escalation offset.

Validation rejects unknown fields, unsupported roles/statuses/events, duplicate rule keys, invalid bounds, and final approval/rejection rules that do not explicitly require human approval and include the competent-authority role.

## Policy registry and runtime behavior

- Policy versions are created only by `policy_admin` or `system_admin`; creation validates the schema and keeps each new version inactive.
- Runtime transition enforcement uses the dedicated `application_workflow` policy key. A policy administrator explicitly activates an effective, validated version. Activating a version deactivates the other versions for that key.
- When an active workflow policy exists, its transition list is authoritative: transitions absent from it are denied. Prerequisites are checked against application fields and registered evidence categories before status mutation.
- Final `approved`/`rejected` decisions always require an authenticated `competent_authority` user, regardless of policy configuration. A policy cannot automate final decisions.
- Transition events record the policy key/version/schema version used for the decision, preserving a verifiable audit trail.
- If no effective `application_workflow` policy is active, the existing guarded transition map remains as a backward-compatible fallback.

## Safety and compatibility

- These are configurable application rules and synthetic demo examples, not official AICTE policy.
- Policy versions are immutable configuration records after creation; activation state is the only mutable lifecycle field.
- Activation is an explicit administrative action. Review policy source, effective date, and intended routes before activating a production policy.

## Policy-controlled deadlines and reminders

The scheduled notification worker runs both the existing evidence-expiry scan and the policy deadline scan.

- For `evidence_expiry`, an active policy's `reminder_days_before` list controls which future expiry offsets produce reminders. Expired evidence still produces an expiry notice, and `escalation_days_after` controls when an idempotent compliance escalation is opened. If no evidence-expiry rule is configured, the existing synthetic 30/7/1-day reminder windows and 7-day escalation default remain for compatibility.
- For `submitted` and `clarification_requested`, the worker derives the deadline from the corresponding chained status-transition event. It only sends notices while the application remains in that status, so it does not keep reminding about a stage that has already advanced.
- For `evc_report_due`, the deadline begins when an EVC visit is completed and remains active only while its report is not submitted.
- Reminder and escalation notices are persistent, in-app notification records with deterministic deduplication keys. The worker writes an audit event when a reminder or escalation notice is first queued. The existing delivery processor handles queued records and retries according to its configured delivery adapter.
- Deadline notifications go to role-based recipients appropriate to the event; institution users are restricted to their own institution, and regional officers are restricted to matching region codes. Escalation notices are sent to the configured oversight roles.
- Invalid active policy JSON causes the worker to fail closed rather than silently inventing policy deadlines.

These deadline values are synthetic application configuration. They do not assert official AICTE deadlines, and the worker only queues notices; it never automatically approves, rejects, or otherwise decides an application.
