"""Run the PRAVAAH expiry monitor as a standalone worker process."""

import argparse
import logging
import os
import time

from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_session_factory
from app.services.notification_jobs import run_expiry_monitoring

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("pravaah.notification_worker")


def run_once() -> dict[str, int | str]:
    session_factory = get_session_factory()
    with session_factory() as db:
        return run_expiry_monitoring(db)


def main() -> None:
    parser = argparse.ArgumentParser(description="PRAVAAH expiry notification and escalation worker")
    parser.add_argument("--once", action="store_true", help="Run a single scan and exit")
    args = parser.parse_args()
    interval = max(30, int(os.getenv("NOTIFICATION_WORKER_INTERVAL_SECONDS", "300")))

    while True:
        try:
            logger.info("Expiry monitoring result: %s", run_once())
        except (SQLAlchemyError, OSError, RuntimeError):
            logger.exception("Expiry monitoring failed")
            if args.once:
                raise
            time.sleep(min(interval, 15))
            continue
        if args.once:
            return
        time.sleep(interval)


if __name__ == "__main__":
    main()
