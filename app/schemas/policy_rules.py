"""Versioned, validated policy-rule contracts for the configurable workflow engine.

These contracts describe application configuration; they are not official AICTE policy.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ApplicationStatus = Literal[
    "draft",
    "submitted",
    "clarification_requested",
    "under_scrutiny",
    "returned",
    "recommended_for_approval",
    "pending_authority_decision",
    "approved",
    "rejected",
]

PolicyRole = Literal[
    "institution_user",
    "scrutiny_officer",
    "regional_officer",
    "bureau_officer",
    "evc_coordinator",
    "competent_authority",
    "policy_admin",
    "auditor",
    "system_admin",
]

RuleKey = Annotated[str, Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_.-]*$")]


class StrictPolicyModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class PolicyTransitionRule(StrictPolicyModel):
    from_status: ApplicationStatus
    to_status: ApplicationStatus
    allowed_roles: list[PolicyRole] = Field(min_length=1, max_length=9)
    requires_human_approval: bool = False

    @model_validator(mode="after")
    def final_decisions_require_human_approval(self):
        if self.to_status in {"approved", "rejected"}:
            if not self.requires_human_approval:
                raise ValueError("Final approval and rejection transitions must require human approval")
            if "competent_authority" not in self.allowed_roles:
                raise ValueError("Final approval and rejection transitions must allow competent_authority")
        if self.from_status in {"approved", "rejected"}:
            raise ValueError("Final application states cannot have outgoing transitions")
        if len(set(self.allowed_roles)) != len(self.allowed_roles):
            raise ValueError("allowed_roles must not contain duplicates")
        return self


class PolicyPrerequisiteRule(StrictPolicyModel):
    status: ApplicationStatus
    required_fields: list[Literal["title", "summary", "institution_id"]] = Field(
        default_factory=list, max_length=3
    )
    required_evidence_categories: list[RuleKey] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def lists_must_be_unique(self):
        if len(set(self.required_fields)) != len(self.required_fields):
            raise ValueError("required_fields must not contain duplicates")
        if len(set(self.required_evidence_categories)) != len(self.required_evidence_categories):
            raise ValueError("required_evidence_categories must not contain duplicates")
        return self


class PolicyDeadlineRule(StrictPolicyModel):
    event: Literal["submitted", "clarification_requested", "evidence_expiry", "evc_report_due"]
    deadline_days: int = Field(ge=1, le=365)
    reminder_days_before: list[int] = Field(default_factory=list, max_length=30)
    escalation_days_after: int | None = Field(default=None, ge=1, le=365)

    @model_validator(mode="after")
    def reminders_must_be_valid(self):
        if any(day < 0 or day > self.deadline_days for day in self.reminder_days_before):
            raise ValueError("Reminder offsets must be between zero and the deadline window")
        if len(set(self.reminder_days_before)) != len(self.reminder_days_before):
            raise ValueError("reminder_days_before must not contain duplicates")
        return self


class PolicyRulesV1(StrictPolicyModel):
    """Schema version 1 for transitions, prerequisites, and deadline rules."""

    transitions: list[PolicyTransitionRule] = Field(default_factory=list, max_length=100)
    prerequisites: list[PolicyPrerequisiteRule] = Field(default_factory=list, max_length=100)
    deadlines: list[PolicyDeadlineRule] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def rule_keys_must_be_unique(self):
        transition_keys = [(rule.from_status, rule.to_status) for rule in self.transitions]
        if len(set(transition_keys)) != len(transition_keys):
            raise ValueError("Duplicate transition rules are not allowed")
        prerequisite_statuses = [rule.status for rule in self.prerequisites]
        if len(set(prerequisite_statuses)) != len(prerequisite_statuses):
            raise ValueError("Only one prerequisite rule may be defined per status")
        deadline_events = [rule.event for rule in self.deadlines]
        if len(set(deadline_events)) != len(deadline_events):
            raise ValueError("Only one deadline rule may be defined per event")
        return self


def validate_policy_rules(schema_version: int, rules: dict) -> PolicyRulesV1:
    """Parse policy JSON using its declared schema version; reject unknown versions."""
    if schema_version != 1:
        raise ValueError(f"Unsupported policy rules schema version: {schema_version}")
    return PolicyRulesV1.model_validate(rules)
