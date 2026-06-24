from __future__ import annotations

from autonomous_betting_agent.local_access import check_local_access, open_session


def test_open_session_defaults_to_active_no_login(monkeypatch):
    monkeypatch.delenv("ABA_REQUIRE_LOGIN", raising=False)
    session = open_session()
    assert session.active is True
    assert session.role == "admin"


def test_check_local_access_accepts_secret_backed_admin():
    session = check_local_access(
        "admin",
        "local-code",
        {
            "ABA_ADMIN_NAME": "admin",
            "ABA_ADMIN_CODE": "local-code",
        },
    )
    assert session.active is True
    assert session.role == "admin"


def test_check_local_access_rejects_wrong_code():
    session = check_local_access(
        "admin",
        "bad-code",
        {
            "ABA_ADMIN_NAME": "admin",
            "ABA_ADMIN_CODE": "local-code",
        },
    )
    assert session.active is False
