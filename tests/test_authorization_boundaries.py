"""Regression tests for centralized RBAC and resource-scope boundaries."""

from datetime import UTC, datetime, timedelta

from app.auth.security import create_access_token, hash_password
from app.models.core import Application, Institution, User
from app.models.evc_visit import EVCVisit


def _institution(db, *, code: str, region: str):
    institution = Institution(name=f"Institution {code}", code=code, region_code=region)
    db.add(institution)
    db.flush()
    return institution


def _user(db, *, email: str, role: str, institution_id=None):
    user = User(
        email=email,
        full_name=email.split("@")[0],
        role=role,
        password_hash=hash_password("Test-password-123!"),
        institution_id=institution_id,
    )
    db.add(user)
    db.flush()
    return user


def test_token_role_claim_cannot_elevate_database_role(api_client_and_sessions):
    client, session_factory = api_client_and_sessions
    with session_factory() as db:
        own = _institution(db, code="TOKEN-OWN", region="REGION-A")
        other = _institution(db, code="TOKEN-OTHER", region="REGION-B")
        user = _user(db, email="token-role@example.test", role="institution_user", institution_id=own.id)
        db.add_all([
            Application(
                application_number="PVH-TOKEN-OWN", title="Own case", status="draft",
                institution_id=own.id,
            ),
            Application(
                application_number="PVH-TOKEN-OTHER", title="Other case", status="draft",
                institution_id=other.id,
            ),
        ])
        db.commit()
        token = create_access_token(str(user.id), "system_admin")

    response = client.get(
        "/api/v1/applications",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert [item["application_number"] for item in response.json()["items"]] == ["PVH-TOKEN-OWN"]


def test_unknown_database_role_fails_closed_for_application_registry(api_client_and_sessions):
    client, session_factory = api_client_and_sessions
    with session_factory() as db:
        institution = _institution(db, code="UNKNOWN-ROLE", region="REGION-A")
        user = _user(
            db, email="unknown-role@example.test", role="unrecognized_role",
            institution_id=institution.id,
        )
        db.commit()
        token = create_access_token(str(user.id), user.role)

    response = client.get(
        "/api/v1/applications",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_auditor_is_read_only_for_evidence_registration(api_client_and_sessions):
    client, session_factory = api_client_and_sessions
    with session_factory() as db:
        institution = _institution(db, code="AUDITOR-READONLY", region="REGION-A")
        auditor = _user(
            db, email="auditor-readonly@example.test", role="auditor",
            institution_id=institution.id,
        )
        application = Application(
            application_number="PVH-AUDITOR-READONLY",
            title="Auditor-visible case",
            status="submitted",
            institution_id=institution.id,
        )
        db.add(application)
        db.commit()
        application_id = application.id
        token = create_access_token(str(auditor.id), auditor.role)

    headers = {"Authorization": f"Bearer {token}"}
    assert client.get(f"/api/v1/applications/{application_id}", headers=headers).status_code == 200
    response = client.post(
        f"/api/v1/applications/{application_id}/evidence",
        headers=headers,
        json={"title": "Attempted evidence write", "category": "other"},
    )
    assert response.status_code == 403


def test_regional_officer_evc_listing_is_scoped_to_assigned_region(api_client_and_sessions):
    client, session_factory = api_client_and_sessions
    with session_factory() as db:
        own = _institution(db, code="EVC-REGION-OWN", region="REGION-A")
        other = _institution(db, code="EVC-REGION-OTHER", region="REGION-B")
        regional_user = _user(
            db, email="evc-regional-scope@example.test", role="regional_officer",
            institution_id=own.id,
        )
        own_case = Application(
            application_number="PVH-EVC-REGION-OWN", title="Own regional case",
            status="under_scrutiny", institution_id=own.id,
        )
        other_case = Application(
            application_number="PVH-EVC-REGION-OTHER", title="Other regional case",
            status="under_scrutiny", institution_id=other.id,
        )
        db.add_all([own_case, other_case])
        db.flush()
        db.add_all([
            EVCVisit(
                application_id=own_case.id,
                scheduled_for=datetime.now(UTC) + timedelta(days=3),
                mode="virtual", status="scheduled", created_by_user_id=regional_user.id,
            ),
            EVCVisit(
                application_id=other_case.id,
                scheduled_for=datetime.now(UTC) + timedelta(days=4),
                mode="virtual", status="scheduled", created_by_user_id=regional_user.id,
            ),
        ])
        db.commit()
        own_case_id = own_case.id
        token = create_access_token(str(regional_user.id), regional_user.role)

    response = client.get(
        "/api/v1/evc/visits",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    assert len(response.json()) == 1
    assert response.json()[0]["application_id"] == str(own_case_id)


def test_transition_rejects_roles_not_assigned_to_the_stage(api_client_and_sessions):
    from fastapi import HTTPException
    import pytest
    from sqlalchemy import select

    from app.models.workflow import ApplicationEvent
    from app.services.workflow import transition_application

    rejected_roles = (
        "scrutiny_officer",
        "regional_officer",
        "bureau_officer",
        "evc_coordinator",
        "competent_authority",
        "policy_admin",
        "auditor",
        "system_admin",
        "unrecognized_role",
    )
    _, session_factory = api_client_and_sessions

    for index, role in enumerate(rejected_roles):
        with session_factory() as db:
            institution = _institution(db, code=f"WF-ROLE-{index}", region="REGION-A")
            actor = _user(
                db,
                email=f"wf-role-{index}@example.test",
                role=role,
                institution_id=institution.id,
            )
            application = Application(
                application_number=f"PVH-WF-ROLE-{index}",
                title="Workflow role guard test",
                status="draft",
                institution_id=institution.id,
            )
            db.add(application)
            db.commit()

            with pytest.raises(HTTPException) as error:
                transition_application(
                    db,
                    application=application,
                    actor=actor,
                    target_status="submitted",
                    expected_status="draft",
                )

            assert error.value.status_code == 409
            db.refresh(application)
            assert application.status == "draft"
            events = db.scalars(
                select(ApplicationEvent).where(ApplicationEvent.application_id == application.id)
            ).all()
            assert events == []
