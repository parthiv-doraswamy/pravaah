"""API regression tests for submission review and correction."""
from app.auth.security import create_access_token, hash_password
from app.models.core import Application, Institution, User
from app.models.evidence import ApplicationEvidence
from app.models.undertaking import ComplianceSubmission


def _make(db, suffix):
    inst = Institution(name=suffix, code=f"SUB-{suffix}", region_code="R1")
    db.add(inst)
    db.flush()
    applicant = User(email=f"app-{suffix}@example.test", full_name="Applicant", role="institution_user", password_hash=hash_password("Test-password-123!"), institution_id=inst.id)
    reviewer = User(email=f"review-{suffix}@example.test", full_name="Reviewer", role="scrutiny_officer", password_hash=hash_password("Test-password-123!"), institution_id=inst.id)
    db.add_all([applicant, reviewer])
    db.flush()
    app = Application(application_number=f"PVH-{suffix}", title="Test case", status="submitted", institution_id=inst.id)
    db.add(app)
    db.flush()
    evidence = ApplicationEvidence(application_id=app.id, title="Governance record", category="governance")
    db.add(evidence)
    db.flush()
    sub = ComplianceSubmission(application_id=app.id, submission_type="annual_undertaking", title="Annual undertaking", declaration="I confirm the submitted information is accurate and complete.", evidence_ids=[str(evidence.id)], status="submitted", version=1, submitted_by_user_id=applicant.id)
    db.add(sub)
    db.commit()
    return app, evidence, applicant, reviewer, sub


def test_review_role_and_notes_are_enforced(api_client_and_sessions):
    client, sessions = api_client_and_sessions
    with sessions() as db:
        _, _, applicant, reviewer, sub = _make(db, "REV")
        sid = sub.id
        a = create_access_token(str(applicant.id), applicant.role)
        r = create_access_token(str(reviewer.id), reviewer.role)
    url = f"/api/v1/compliance/submissions/{sid}/review"
    assert client.post(url, headers={"Authorization": f"Bearer {a}"}, json={"decision": "accepted"}).status_code == 403
    assert client.post(url, headers={"Authorization": f"Bearer {r}"}, json={"decision": "changes_requested"}).status_code == 422
    response = client.post(url, headers={"Authorization": f"Bearer {r}"}, json={"decision": "changes_requested", "notes": "Attach the current approved record."})
    assert response.status_code == 200, response.text
    assert response.json()["reviewed_by_user_id"] is not None


def test_resubmission_keeps_review_history_and_increments_version(api_client_and_sessions):
    client, sessions = api_client_and_sessions
    with sessions() as db:
        app, evidence, applicant, reviewer, sub = _make(db, "COR")
        sid, aid, eid = sub.id, app.id, evidence.id
        a = create_access_token(str(applicant.id), applicant.role)
        r = create_access_token(str(reviewer.id), reviewer.role)
    url = f"/api/v1/compliance/submissions/{sid}/review"
    review = client.post(url, headers={"Authorization": f"Bearer {r}"}, json={"decision": "changes_requested", "notes": "Please attach the updated record."})
    assert review.status_code == 200, review.text
    corrected = client.post(f"/api/v1/compliance/submissions/{sid}/resubmit", headers={"Authorization": f"Bearer {a}"}, json={"submission_type": "annual_undertaking", "title": "Corrected undertaking", "declaration": "I confirm the submitted information is accurate and complete.", "evidence_ids": [str(eid)]})
    assert corrected.status_code == 201, corrected.text
    assert corrected.json()["version"] == 2
    assert corrected.json()["supersedes_submission_id"] == str(sid)
    history = client.get(f"/api/v1/compliance/applications/{aid}/submissions", headers={"Authorization": f"Bearer {a}"})
    old = next(item for item in history.json() if item["id"] == str(sid))
    assert old["status"] == "changes_requested"
    assert old["review_notes"] == "Please attach the updated record."


def test_review_is_one_way_for_each_submission(api_client_and_sessions):
    client, sessions = api_client_and_sessions
    with sessions() as db:
        _, _, _, reviewer, sub = _make(db, "ONE")
        sid = sub.id
        token = create_access_token(str(reviewer.id), reviewer.role)
    url = f"/api/v1/compliance/submissions/{sid}/review"
    first = client.post(url, headers={"Authorization": f"Bearer {token}"}, json={"decision": "accepted"})
    assert first.status_code == 200
    second = client.post(url, headers={"Authorization": f"Bearer {token}"}, json={"decision": "rejected", "notes": "Changed decision"})
    assert second.status_code == 409
