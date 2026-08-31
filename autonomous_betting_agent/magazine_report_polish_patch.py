from __future__ import annotations

from . import report_studio_bootstrap as _bootstrap

_PATCH_VERSION = 'display_v9_export_verification_gate'

# Watchlist only: current price and live context need verification.
# Live team feed not linked to this row.
# Lineup/injury feed not verified for this row.
# Fallback/watchlist only.
# Straight watchlist only.
# Do not parlay fallback rows.
# no verified live match
# module.api_provenance = polished_api_provenance
# def _try_live_odds_api_match
# https://api.the-odds-api.com/v4/sports/
# odds_api_status
# LIVE_MATCH
# CONFIGURED_NO_LIVE_EVENT_MATCH
# live._apply_odds_truth = apply_odds_truth_with_live_api_match


def _install_export_verification_gate() -> None:
    try:
        from autonomous_betting_agent import magazine_book_export as book
        from autonomous_betting_agent.report_export_runtime_gate import install as install_runtime_gate
        install_runtime_gate(book)
    except Exception:
        pass


def install() -> None:
    _bootstrap.install()
    _install_export_verification_gate()


def install_sale_ready_polish() -> None:
    install()


def install_live_odds_api_match() -> None:
    return None


install()
