"""API regression tests for scoped compliance undertaking submissions."""

from app.auth.security import create_access_token, hash_password
from app.models.core import Application, Institution, User
from app.models.evidence import ApplicationEvidence


def _user(db, *, email, role, institution_id):
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


def test_submit_compliance_undertaking_with_scoped_evidence(api_client_and_sessions):
    client, session_factory = api_client_and_sessions
    with session_factory() as db:
        institution = Institution(name="Submission Institute", code="SUBMIT-OWN", region_code="R1")
        db.add(institution)
        db.flush()
        user = _user(db, email="submission@example.test", role="institution_user", institution_id=institution.id)
        application = Application(
            application_number="PVH-SUBMISSION-1", title="Submission case", status="draft",
            institution_id=institution.id,
        )
        db.add(application)
        db.flush()
        evidence = ApplicationEvidence(
            application_id=application.id, title="Governance record", category="governance",
            created_by_user_id=user.id,
        )
        db.add(evidence)
        db.commit()
        application_id, evidence_id = application.id, evidence.id
        token = create_access_token(str(user.id), user.role)

    response = client.post(
        f"/api/v1/compliance/applications/{application_id}/submissions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "submission_type": "annual_undertaking",
            "title": "Annual compliance undertaking",
            "declaration": "I confirm the submitted information is accurate and complete.",
            "evidence_ids": [str(evidence_id)],
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "submitted"
    assert body["version"] == 1
    assert body["application_id"] == str(application_id)
    assert body["evidence_ids"] == [str(evidence_id)]


def test_submission_rejects_evidence_from_another_application(api_client_and_sessions):
    client, session_factory = api_client_and_sessions
    with session_factory() as db:
        own = Institution(name="Own Institute", code="SUBMIT-OWN2", region_code="R1")
        other = Institution(name="Other Institute", code="SUBMIT-OTHER", region_code="R2")
        db.add_all([own, other])
        db.flush()
        user = _user(db, email="submission-scope@example.test", role="institution_user", institution_id=own.id)
        own_app = Application(
            application_number="PVH-SUBMISSION-OWN", title="Own case", status="draft",
            institution_id=own.id,
        )
        other_app = Application(
            application_number="PVH-SUBMISSION-OTHER", title="Other case", status="draft",
            institution_id=other.id,
        )
        db.add_all([own_app, other_app])
        db.flush()
        evidence = ApplicationEvidence(
            application_id=other_app.id, title="Other evidence", category="governance",
        )
        db.add(evidence)
        db.commit()
        own_id, evidence_id = own_app.id, evidence.id
        token = create_access_token(str(user.id), user.role)

    response = client.post(
        f"/api/v1/compliance/applications/{own_id}/submissions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "submission_type": "annual_undertaking",
            "title": "Annual compliance undertaking",
            "declaration": "I confirm the submitted information is accurate and complete.",
            "evidence_ids": [str(evidence_id)],
        },
    )
    assert response.status_code == 422


def test_submission_is_not_visible_outside_institution_scope(api_client_and_sessions):
    client, session_factory = api_client_and_sessions
    with session_factory() as db:
        own = Institution(name="Visible Institute", code="SUBMIT-VISIBLE", region_code="R1")
        other = Institution(name="Hidden Institute", code="SUBMIT-HIDDEN", region_code="R2")
        db.add_all([own, other])
        db.flush()
        user = _user(db, email="submission-list@example.test", role="institution_user", institution_id=own.id)
        own_app = Application(
            application_number="PVH-SUBMISSION-VISIBLE", title="Visible case", status="draft",
            institution_id=own.id,
        )
        other_app = Application(
            application_number="PVH-SUBMISSION-HIDDEN", title="Hidden case", status="draft",
            institution_id=other.id,
        )
        db.add_all([own_app, other_app])
        db.flush()
        db.add_all([
            ApplicationEvidence(application_id=own_app.id, title="Own evidence", category="governance"),
            ApplicationEvidence(application_id=other_app.id, title="Hidden evidence", category="governance"),
        ])
        db.commit()
        token = create_access_token(str(user.id), user.role)

    response = client.get(
        "/api/v1/compliance/submissions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json() == []
