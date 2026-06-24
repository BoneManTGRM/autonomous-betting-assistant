"""Optional local access helper for Streamlit pages.

Default behavior stays open/no-login. When enabled by environment or Streamlit
secrets, the helper supports simple local roles without OAuth or a server.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class LocalAccessSession:
    name: str = "local"
    role: str = "admin"
    active: bool = True


def local_access_required() -> bool:
    return os.getenv("ABA_REQUIRE_LOGIN", "false").strip().lower() in {"1", "true", "yes", "on"}


def open_session() -> LocalAccessSession:
    if local_access_required():
        return LocalAccessSession(name="", role="demo", active=False)
    return LocalAccessSession()


def check_local_access(name: str, passcode: str, secrets: Mapping[str, Any] | None = None) -> LocalAccessSession:
    source = dict(secrets or {})

    def get(key: str, default: str = "") -> str:
        return str(source.get(key) or os.getenv(key, default)).strip()

    users = [
        (get("ABA_ADMIN_NAME", "admin"), get("ABA_ADMIN_CODE"), "admin"),
        (get("ABA_CLIENT_NAME", "client"), get("ABA_CLIENT_CODE"), "client"),
        (get("ABA_DEMO_NAME", "demo"), get("ABA_DEMO_CODE", "demo"), "demo"),
    ]
    for expected_name, expected_code, role in users:
        if name == expected_name and expected_code and passcode == expected_code:
            return LocalAccessSession(name=name, role=role, active=True)
    return LocalAccessSession(name=name, role="demo", active=False)


def can_view_private(role: str) -> bool:
    return role == "admin"


def can_view_client_reports(role: str) -> bool:
    return role in {"admin", "client"}
