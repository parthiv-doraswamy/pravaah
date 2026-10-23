"""Tests for versioned policy rule validation; fixtures are synthetic demo rules."""

import pytest
from pydantic import ValidationError

from app.schemas.policy_rules import PolicyRulesV1, validate_policy_rules


def test_empty_existing_rules_remain_valid_for_schema_v1():
    assert validate_policy_rules(1, {}).model_dump() == {
        "transitions": [], "prerequisites": [], "deadlines": []
    }


def test_schema_rejects_unknown_version():
    with pytest.raises(ValueError, match="Unsupported policy rules schema version"):
        validate_policy_rules(2, {})


def test_policy_rejects_unknown_fields_and_invalid_roles():
    with pytest.raises(ValidationError):
        PolicyRulesV1.model_validate({"unreviewed_setting": True})
    with pytest.raises(ValidationError):
        PolicyRulesV1.model_validate({
            "transitions": [{
                "from_status": "draft",
                "to_status": "submitted",
                "allowed_roles": ["super_admin"],
            }]
        })


def test_final_decisions_must_remain_human_approved():
    with pytest.raises(ValidationError, match="must require human approval"):
        PolicyRulesV1.model_validate({
            "transitions": [{
                "from_status": "pending_authority_decision",
                "to_status": "approved",
                "allowed_roles": ["competent_authority"],
            }]
        })
    valid = PolicyRulesV1.model_validate({
        "transitions": [{
            "from_status": "pending_authority_decision",
            "to_status": "approved",
            "allowed_roles": ["competent_authority"],
            "requires_human_approval": True,
        }]
    })
    assert valid.transitions[0].requires_human_approval is True


def test_policy_rejects_duplicate_transitions_and_deadline_reminders_outside_window():
    transition = {
        "from_status": "draft", "to_status": "submitted", "allowed_roles": ["institution_user"]
    }
    with pytest.raises(ValidationError, match="Duplicate transition rules"):
        PolicyRulesV1.model_validate({"transitions": [transition, transition]})
    with pytest.raises(ValidationError, match="Reminder offsets"):
        PolicyRulesV1.model_validate({
            "deadlines": [{
                "event": "submitted", "deadline_days": 5, "reminder_days_before": [7]
            }]
        })


def test_policy_deadline_bounds_are_enforced():
    with pytest.raises(ValidationError):
        PolicyRulesV1.model_validate({
            "deadlines": [{"event": "submitted", "deadline_days": 0}]
        })
