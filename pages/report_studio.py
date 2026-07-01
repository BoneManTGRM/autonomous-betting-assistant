from __future__ import annotations

from dataclasses import asdict
import hashlib
import importlib

import pandas as pd
import streamlit as st

from autonomous_betting_agent.app_feed_delivery import save_app_feed
from autonomous_betting_agent.commercial_platform_tools import load_persistent_ledger, normalize_workspace_id
import autonomous_betting_agent.magazine_book_export as magazine_book_export
from autonomous_betting_agent.magazine_api_sources import api_provenance
from autonomous_betting_agent.magazine_live_api_enrichment import ENRICHMENT_VERSION, enrich_rows_with_live_api_data, install as install_magazine_live_api_enrichment
from autonomous_betting_agent.magazine_report_polish_patch import install as install_magazine_report_polish
from autonomous_betting_agent.magazine_sale_ready_patch import apply_magazine_sale_ready_patch
from autonomous_betting_agent.pick_hold_store import load_first_available
from autonomous_betting_agent.report_feed_service import save_report_feed
from autonomous_betting_agent.report_product_layer import MagazineBrand, event_text, safe_text, value_text
from autonomous_betting_agent.report_publisher_service import build_report_publisher_payload
from autonomous_betting_agent.report_studio_service import ReportStudioFilters, build_report_studio_state, report_studio_summary
from autonomous_betting_agent.report_studio_spanish_ui import render_sport_league_filter
from autonomous_betting_agent.report_studio_ui import render_premium_card_deck, render_status_dashboard
from autonomous_betting_agent.row_normalizer import normalize_frame
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.ui_i18n import localize_dataframe as global_localize_dataframe, localize_options, localize_value
from autonomous_betting_agent.white_label_profiles import WhiteLabelProfile, list_profiles, load_profile, save_profile

magazine_book_export = apply_magazine_sale_ready_patch(install_magazine_live_api_enrichment(importlib.reload(magazine_book_export)))
install_magazine_report_polish()

st.set_page_config(page_title="Report Studio", layout="wide")
LANG = render_app_sidebar("report_studio", language_key="report_studio_language", selector="radio")
NO_MARKET_EXPORT_VERSION = "no_market_metric_v10"
DISPLAY_POLISH_VERSION = "display_polish_v1"
ACTIVE_EXPORT_VERSION = f"{magazine_book_export.MAGAZINE_STYLE_VERSION}:{NO_MARKET_EXPORT_VERSION}:{ENRICHMENT_VERSION}:{DISPLAY_POLISH_VERSION}"
REPORT_STUDIO_PUBLISHER_PACKAGE_TYPE_OPTIONS = ("public", "client")
REPORT_STUDIO_PUBLISHER_PREVIEW_KEY = "report_studio_publisher_preview"
REPORT_STUDIO_PUBLISHER_FINGERPRINT_KEY = "report_studio_publisher_input_fingerprint"
REPORT_STUDIO_PUBLISHER_META_KEY = "report_studio_publisher_preview_meta"
if st.session_state.get("report_studio_active_export_version") != ACTIVE_EXPORT_VERSION:
    st.cache_data.clear()
    for key in list(st.session_state.keys()):
        if key.startswith("report_studio_full_book_export_cache_"):
            del st.session_state[key]
    st.session_state["report_studio_active_export_version"] = ACTIVE_EXPORT_VERSION

TEXT = {
    "en": {
        "title": "Report Studio",
        "caption": "Premium reports, proof, exports, profiles, and app feed.",
        "input": "Input rows",
        "workspace": "Client / Workspace ID",
        "use_saved": "Use saved workspace rows",
        "upload": "Upload CSV rows",
        "source": "Source",
        "empty": "No rows found. Use Pro Predictor / Odds Lock Pro first or upload a CSV.",
        "profile": "White-label profile",
        "profile_id": "Profile ID",
        "profile_key": "Profile key",
        "load_profile": "Load profile",
        "save_profile": "Save profile",
        "brand_name": "Brand / tipster name",
        "tagline": "Tagline",
        "report_title": "Report title",
        "full_book_name": "Full magazine book file name",
        "logo_url": "Logo URL",
        "disclaimer": "Disclaimer",
        "mode": "Report mode",
        "risk": "Risk preference",
        "sports": "Sport / League Filter",
        "max_rows": "Max rows",
        "visibility": "Feed visibility",
        "cards": "Premium Cards",
        "magazine": "Magazine Report",
        "copy": "WhatsApp / Telegram",
        "audit": "Learning Audit",
        "proof": "Analyst Proof",
        "exports": "Exports",
        "images": "Images",
        "profile_json": "Profile JSON",
        "feed_json": "App Feed",
        "diagnostics": "Diagnostics",
    }
}
