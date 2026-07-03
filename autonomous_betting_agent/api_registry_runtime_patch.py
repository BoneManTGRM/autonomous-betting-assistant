from __future__ import annotations

from typing import Any

BALLDONTLIE_PROVIDER_DEF = (
    "Ball Don't Lie",
    ("balldontlie_source_used", "balldontlie_live", "balldontlie_enabled", "balldontlie_status"),
    ("balldontlie_team_summary", "balldontlie_injury_summary", "balldontlie_game_summary", "balldontlie_props_summary"),
    ("player_prop_markets", "balldontlie_odds_summary"),
    False,
)
BALLDONTLIE_SECRET_NAMES = ("BALLDONTLIE_API_KEY", "BDL_API_KEY", "BALLDONTLIE_KEY")


def _append_provider(module: Any) -> None:
    defs = tuple(getattr(module, "API_SOURCE_DEFS", ()))
    if not any(item and item[0] == "Ball Don't Lie" for item in defs):
        module.API_SOURCE_DEFS = defs + (BALLDONTLIE_PROVIDER_DEF,)
    secrets = dict(getattr(module, "API_SECRET_DEFS", {}))
    secrets.setdefault("Ball Don't Lie", BALLDONTLIE_SECRET_NAMES)
    module.API_SECRET_DEFS = secrets
    labels = dict(getattr(module, "API_SHORT_LABELS", {}))
    labels.setdefault("Ball Don't Lie", "BDL")
    module.API_SHORT_LABELS = labels
    fragments = tuple(getattr(module, "API_SUMMARY_KEY_FRAGMENTS", ()))
    if "balldontlie" not in fragments:
        module.API_SUMMARY_KEY_FRAGMENTS = fragments + ("balldontlie",)


def _install_report_studio_guard() -> None:
    try:
        from autonomous_betting_agent.report_studio_fresh_ledger_guard import install as install_guard
        install_guard()
    except Exception:
        pass


def install() -> None:
    for name in (
        "autonomous_betting_agent.magazine_api_sources",
        "autonomous_betting_agent.magazine_book_export",
    ):
        try:
            module = __import__(name, fromlist=["*"])
            _append_provider(module)
        except Exception:
            pass
    _install_report_studio_guard()
