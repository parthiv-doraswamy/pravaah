"""Run the PRAVAAH expiry monitor as a standalone worker process."""

import argparse
import logging
import os
import time

from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_session_factory
from app.services.notification_jobs import run_expiry_monitoring
from app.services.notification_delivery import process_due_notifications

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("pravaah.notification_worker")


def run_once() -> dict[str, object]:
    session_factory = get_session_factory()
    with session_factory() as db:
        scan = run_expiry_monitoring(db)
    with session_factory() as db:
        delivery = process_due_notifications(db)
    return {"expiry_scan": scan, "delivery": delivery}


def main() -> None:
    parser = argparse.ArgumentParser(description="PRAVAAH expiry notification and escalation worker")
    parser.add_argument("--once", action="store_true", help="Run a single scan and exit")
    args = parser.parse_args()
    interval = max(30, int(os.getenv("NOTIFICATION_WORKER_INTERVAL_SECONDS", "300")))

    while True:
        try:
            logger.info("Expiry monitoring result: %s", run_once())
        except (SQLAlchemyError, OSError, RuntimeError) as error:
            # Exception messages can contain DSNs or provider details. Log the
            # category without echoing the raw message or traceback.
            logger.error(
                "Expiry monitoring failed (error_type=%s)",
                type(error).__name__,
            )
            if args.once:
                raise
            time.sleep(min(interval, 15))
            continue
        if args.once:
            return
        time.sleep(interval)


if __name__ == "__main__":
    main()
