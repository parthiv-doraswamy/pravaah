"""Integration tests for scoped Policy-to-Proof traceability dossiers."""

from datetime import UTC, datetime, timedelta

from app.auth.security import hash_password
from app.models.core import Application, Institution, User
from app.models.evidence import ApplicationEvidence
from app.models.evidence_attachment import EvidenceAttachment
from app.models.workflow import ApplicationEvent, PolicyVersion
from app.services.workflow import append_event


def _case(client, session_factory, suffix: str):
    with session_factory() as db:
        institution = Institution(
            name=f"Traceability College {suffix}",
            code=f"TRACE-{suffix}",
            region_code="TRACE-REGION",
        )
        db.add(institution)
        db.flush()
        user = User(
            email=f"trace-{suffix}@example.test",
            full_name="Traceability Test User",
            role="institution_user",
            password_hash=hash_password("Trace-Test-123!"),
            institution_id=institution.id,
        )
        application = Application(
            application_number=f"PVH-TRACE-{suffix}",
            title="Traceability test application",
            status="draft",
            institution_id=institution.id,
        )
        db.add_all([user, application])
        db.flush()
        application_id = application.id
        institution_id = institution.id
        db.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": f"trace-{suffix}@example.test", "password": "Trace-Test-123!"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}, application_id, institution_id


def test_policy_to_proof_dossier_links_policy_evidence_and_valid_audit_chain(api_client_and_sessions):
    client, session_factory = api_client_and_sessions
    headers, application_id, _ = _case(client, session_factory, "001")

    with session_factory() as db:
        application = db.get(Application, application_id)
        evidence = ApplicationEvidence(
            application_id=application.id,
            title="Fire safety certificate",
            category="fire_safety",
            reference_number="FSC-TRACE-001",
            policy_key="EVIDENCE_EXPIRY",
        )
        policy = PolicyVersion(
            policy_key="EVIDENCE_EXPIRY",
            version=1,
            title="Evidence expiry demo policy",
            description="Synthetic policy for traceability tests.",
            effective_from=datetime.now(UTC) - timedelta(days=1),
            rules={"warning_windows_days": [30, 7, 1]},
            source_label="Synthetic test policy",
            is_active=True,
        )
        db.add_all([evidence, policy])
        db.flush()
        append_event(
            db,
            application_id=application.id,
            event_type="evidence_registered",
            from_status=None,
            to_status="draft",
            actor_user_id=None,
            metadata={"policy_key": "EVIDENCE_EXPIRY", "evidence_title": evidence.title},
        )
        db.commit()

    response = client.get(
        f"/api/v1/applications/{application_id}/policy-to-proof",
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["application"]["application_number"] == "PVH-TRACE-001"
    assert payload["policy_versions"][0]["policy_key"] == "EVIDENCE_EXPIRY"
    assert payload["evidence"][0]["title"] == "Fire safety certificate"
    assert payload["audit"]["valid"] is True
    assert payload["audit"]["event_count"] == 1
    assert payload["counts"]["evidence"] == 1
    assert "not official AICTE rules" in payload["disclaimer"]


def test_policy_to_proof_dossier_hides_applications_outside_institution_scope(api_client_and_sessions):
    client, session_factory = api_client_and_sessions
    headers, _, _ = _case(client, session_factory, "002")
    _, other_application_id, _ = _case(client, session_factory, "003")

    response = client.get(
        f"/api/v1/applications/{other_application_id}/policy-to-proof",
        headers=headers,
    )
    assert response.status_code == 404



def test_policy_to_proof_exposes_file_integrity_without_private_storage_keys_and_flags_tampering(api_client_and_sessions):
    client, session_factory = api_client_and_sessions
    headers, application_id, _ = _case(client, session_factory, "005")

    with session_factory() as db:
        application = db.get(Application, application_id)
        evidence = ApplicationEvidence(
            application_id=application.id,
            title="Signed inspection report",
            category="inspection_report",
            policy_key=None,
        )
        db.add(evidence)
        db.flush()
        attachment = EvidenceAttachment(
            application_id=application.id,
            evidence_id=evidence.id,
            original_filename="inspection.pdf",
            storage_key="private-object-key-005",
            content_type="application/pdf",
            size_bytes=128,
            sha256_hex="a" * 64,
        )
        db.add(attachment)
        event = append_event(
            db,
            application_id=application.id,
            event_type="evidence_registered",
            from_status=None,
            to_status="draft",
            actor_user_id=None,
            metadata={"evidence_title": evidence.title},
        )
        db.commit()
        event_id = event.id

    response = client.get(
        f"/api/v1/applications/{application_id}/policy-to-proof",
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["attachments"][0]["filename"] == "inspection.pdf"
    assert payload["attachments"][0]["sha256"] == "a" * 64
    assert "storage_key" not in payload["attachments"][0]
    assert "private-object-key-005" not in response.text

    with session_factory() as db:
        event = db.get(ApplicationEvent, event_id)
        event.reason = "Altered after event hash was written"
        db.commit()

    tampered = client.get(
        f"/api/v1/applications/{application_id}/policy-to-proof",
        headers=headers,
    )
    assert tampered.status_code == 200
    assert tampered.json()["audit"]["valid"] is False
    assert tampered.json()["audit"]["first_invalid_sequence"] == 1

def test_policy_to_proof_requires_authentication(api_client_and_sessions):
    client, session_factory = api_client_and_sessions
    _, application_id, _ = _case(client, session_factory, "004")

    response = client.get(f"/api/v1/applications/{application_id}/policy-to-proof")
    assert response.status_code == 401
