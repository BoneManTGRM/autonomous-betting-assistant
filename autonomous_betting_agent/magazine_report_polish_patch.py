from __future__ import annotations

from . import report_studio_bootstrap as _bootstrap

_PATCH_VERSION = 'display_v8'

def install() -> None:
    _bootstrap.install()

def install_sale_ready_polish() -> None:
    install()

def install_live_odds_api_match() -> None:
    return None

install()
