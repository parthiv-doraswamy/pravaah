"""Integration tests for the in-app expiry notification queue."""

from datetime import date, timedelta

from app.auth.security import hash_password
from app.models.core import Application, Institution, User
from app.models.evidence import ApplicationEvidence
from app.models.notification import NotificationRecord
from app.models.workflow import ApplicationEvent


def make_case(client, db_factory, suffix):
    with db_factory() as db:
        institution = Institution(name=f"College {suffix}", code=f"NT-{suffix}", region_code="REGION-N")
        db.add(institution)
        db.flush()
        owner = User(email=f"owner-{suffix}@example.test", full_name="Institution User",
                     role="institution_user", password_hash=hash_password("Test-password-123!"),
                     institution_id=institution.id)
        reviewer = User(email=f"reviewer-{suffix}@example.test", full_name="Reviewer",
                        role="scrutiny_officer", password_hash=hash_password("Test-password-123!"))
        case = Application(application_number=f"PVH-NT-{suffix}", title="Expiry test case",
                           status="under_scrutiny", institution_id=institution.id)
        db.add_all([owner, reviewer, case])
        db.flush()
        db.add(ApplicationEvidence(application_id=case.id, title="Accreditation certificate",
                                   category="accreditation", expires_on=date.today() + timedelta(days=5),
                                   created_by_user_id=owner.id))
        db.commit()
        owner_email, reviewer_email, case_id = owner.email, reviewer.email, case.id

    def login(email):
        response = client.post("/api/v1/auth/login",
                               json={"email": email, "password": "Test-password-123!"})
        assert response.status_code == 200
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return login(owner_email), login(reviewer_email), case_id


def test_expiry_queue_is_idempotent_and_audited(api_client_and_sessions):
    client, db_factory = api_client_and_sessions
    owner_headers, reviewer_headers, case_id = make_case(client, db_factory, "001")
    first = client.post("/api/v1/notifications/queue-expiry", headers=reviewer_headers)
    assert first.status_code == 200
    assert first.json()["created"] == 1
    second = client.post("/api/v1/notifications/queue-expiry", headers=reviewer_headers)
    assert second.status_code == 200
    assert second.json()["created"] == 0
    assert second.json()["skipped_existing"] == 1

    listing = client.get("/api/v1/notifications?unread_only=true", headers=owner_headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 1
    item = listing.json()[0]
    assert item["delivery_status"] == "pending"
    assert item["severity"] == "warning"
    marked = client.post(f"/api/v1/notifications/{item['id']}/read", headers=owner_headers)
    assert marked.status_code == 200
    assert marked.json()["read_at"] is not None
    assert client.get("/api/v1/notifications?unread_only=true", headers=owner_headers).json() == []

    with db_factory() as db:
        event = db.query(ApplicationEvent).filter_by(
            application_id=case_id, event_type="expiry_notification_queued"
        ).one()
        assert event.event_metadata["severity"] == "warning"
        assert db.query(NotificationRecord).filter_by(application_id=case_id).count() == 1


def test_notification_read_is_recipient_scoped(api_client_and_sessions):
    client, db_factory = api_client_and_sessions
    owner_headers, reviewer_headers, _ = make_case(client, db_factory, "002")
    assert client.post("/api/v1/notifications/queue-expiry", headers=reviewer_headers).status_code == 200
    item = client.get("/api/v1/notifications", headers=owner_headers).json()[0]
    response = client.post(f"/api/v1/notifications/{item['id']}/read", headers=reviewer_headers)
    assert response.status_code == 404


def test_institution_user_cannot_queue_notifications(api_client_and_sessions):
    client, db_factory = api_client_and_sessions
    owner_headers, _, _ = make_case(client, db_factory, "003")
    response = client.post("/api/v1/notifications/queue-expiry", headers=owner_headers)
    assert response.status_code == 403



def test_notification_list_is_private_and_limit_is_bounded(api_client_and_sessions):
    client, db_factory = api_client_and_sessions
    owner_headers, reviewer_headers, case_id = make_case(client, db_factory, "004")
    assert client.post("/api/v1/notifications/queue-expiry", headers=reviewer_headers).status_code == 200
    owner_items = client.get("/api/v1/notifications?limit=999", headers=owner_headers)
    assert owner_items.status_code == 200
    assert len(owner_items.json()) == 1

    reviewer_items = client.get("/api/v1/notifications", headers=reviewer_headers)
    assert reviewer_items.status_code == 200
    assert reviewer_items.json() == []

    with db_factory() as db:
        item = db.query(NotificationRecord).filter_by(application_id=case_id).one()
        assert item.recipient_user_id is not None


def test_notification_read_requires_authentication(api_client_and_sessions):
    client, db_factory = api_client_and_sessions
    owner_headers, reviewer_headers, _ = make_case(client, db_factory, "005")
    assert client.post("/api/v1/notifications/queue-expiry", headers=reviewer_headers).status_code == 200
    item = client.get("/api/v1/notifications", headers=owner_headers).json()[0]
    response = client.post(f"/api/v1/notifications/{item['id']}/read")
    assert response.status_code == 401
