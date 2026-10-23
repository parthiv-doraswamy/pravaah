"""Security checks for notification worker logging."""


def test_worker_logs_error_type_without_raw_exception_secrets(monkeypatch, caplog):
    import sys

    import pytest

    import scripts.notification_worker as worker

    sentinel = "SMTP_PASSWORD_DO_NOT_LEAK_8f13"

    def fail_with_sensitive_message():
        raise OSError(f"SMTP connection failed using password={sentinel}")

    monkeypatch.setattr(worker, "run_once", fail_with_sensitive_message)
    monkeypatch.setattr(sys, "argv", ["notification_worker.py", "--once"])

    with caplog.at_level("ERROR", logger="pravaah.notification_worker"):
        with pytest.raises(OSError, match="DO_NOT_LEAK"):
            worker.main()

    assert "error_type=OSError" in caplog.text
    assert sentinel not in caplog.text
    assert "password=" not in caplog.text
