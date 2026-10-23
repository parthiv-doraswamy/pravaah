"""Central role allowlists for application and operational endpoints.

These sets preserve the prototype's existing authorization policy while making
role grants reviewable in one place. They are application permissions, not a
substitute for per-resource institution/region scoping.
"""

# Roles allowed to browse the full application registry. Regional officers are
# deliberately handled separately by scoped_applications_statement().
GLOBAL_APPLICATION_REVIEW_ROLES = frozenset({
    "scrutiny_officer",
    "bureau_officer",
    "evc_coordinator",
    "competent_authority",
    "policy_admin",
    "auditor",
    "system_admin",
})

# Register/upload evidence roles. Auditors are read-only.
EVIDENCE_WRITE_ROLES = frozenset({
    "institution_user",
    "scrutiny_officer",
    "regional_officer",
    "bureau_officer",
    "evc_coordinator",
    "competent_authority",
    "policy_admin",
    "system_admin",
})

EVC_SCHEDULER_ROLES = (
    "evc_coordinator",
    "bureau_officer",
    "policy_admin",
    "system_admin",
)

COMPLIANCE_ESCALATION_RESOLVER_ROLES = (
    "scrutiny_officer",
    "regional_officer",
    "bureau_officer",
    "policy_admin",
    "system_admin",
    "evc_coordinator",
)

NOTIFICATION_QUEUE_ROLES = (
    "scrutiny_officer",
    "regional_officer",
    "bureau_officer",
    "policy_admin",
    "system_admin",
    "evc_coordinator",
)
