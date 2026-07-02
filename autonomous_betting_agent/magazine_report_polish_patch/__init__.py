from __future__ import annotations

import importlib

_PATCH_VERSION = 'magazine_report_polish_package_active_guard_v2'


def install() -> None:
    try:
        importlib.import_module('autonomous_betting_agent.' + 'report_studio_bootstrap').install()
    except Exception:
        pass


def install_sale_ready_polish() -> None:
    install()


def install_live_odds_api_match() -> None:
    return None


install()
