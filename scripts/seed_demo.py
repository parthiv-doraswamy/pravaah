"""Idempotently seed synthetic local demo records.

This script is intended only for APP_ENV=development and requires an explicit
DEMO_USER_PASSWORD environment variable. Never use the bundled Compose credentials
outside the local development environment.
"""

import os

from sqlalchemy import select

from app.auth.security import hash_password
from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models.core import Application, Institution, User


def main() -> None:
    settings = get_settings()
    if settings.app_env.lower() != "development":
        raise RuntimeError("Demo seed script is only allowed when APP_ENV=development")

    password = os.environ.get("DEMO_USER_PASSWORD", "")
    if len(password) < 12:
        raise RuntimeError("Set DEMO_USER_PASSWORD to a local-only password of at least 12 characters")

    session_factory = get_session_factory()
    with session_factory() as db:
        demo_institution = db.scalar(
            select(Institution).where(Institution.code == "DEMO-001")
        )
        if demo_institution is None:
            demo_institution = Institution(
                name="Demo Technical Institute",
                code="DEMO-001",
                region_code="REGION-DEMO",
            )
            db.add(demo_institution)
            db.flush()

        second_institution = db.scalar(
            select(Institution).where(Institution.code == "DEMO-002")
        )
        if second_institution is None:
            second_institution = Institution(
                name="Example Engineering College",
                code="DEMO-002",
                region_code="REGION-DEMO",
            )
            db.add(second_institution)
            db.flush()

        institution_user = db.scalar(
            select(User).where(User.email == "demo.institution@example.test")
        )
        if institution_user is None:
            db.add(
                User(
                    email="demo.institution@example.test",
                    full_name="Demo Institution User",
                    role="institution_user",
                    institution_id=demo_institution.id,
                    password_hash=hash_password(password),
                    is_active=True,
                )
            )

        reviewer = db.scalar(select(User).where(User.email == "demo.reviewer@example.test"))
        if reviewer is None:
            db.add(
                User(
                    email="demo.reviewer@example.test",
                    full_name="Demo Scrutiny Officer",
                    role="scrutiny_officer",
                    password_hash=hash_password(password),
                    is_active=True,
                )
            )

        demo_cases = [
            ("PVH-DEMO-1001", "New programme approval", "draft", demo_institution.id),
            ("PVH-DEMO-1002", "Infrastructure compliance review", "submitted", demo_institution.id),
            ("PVH-DEMO-2001", "Institution renewal application", "scrutiny", second_institution.id),
        ]
        for number, title, case_status, institution_id in demo_cases:
            existing = db.scalar(
                select(Application).where(Application.application_number == number)
            )
            if existing is None:
                db.add(
                    Application(
                        application_number=number,
                        title=title,
                        status=case_status,
                        institution_id=institution_id,
                        summary="Synthetic sample record for local demonstration only.",
                    )
                )

        db.commit()
    print("Synthetic PRAVAAH demo records are ready (local development only).")


if __name__ == "__main__":
    main()
