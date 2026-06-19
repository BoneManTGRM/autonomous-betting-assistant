from __future__ import annotations

from typing import Any

# Target profile based on Cody's larger-list result:
# 108 picks, 60 finished, 43-17 = 71.7% while still maintaining useful volume.
# This does not guarantee 70%+, but it sets Pro Predictor's defaults to reproduce
# the same style: broad enough volume, light filters, then top-ranked export.
NUMBER_DEFAULTS = {
    'Max sports': 50,
    'Máximo de deportes': 50,
    'Max events per sport': 500,
    'Máximo de eventos por deporte': 500,
}

MULTI_DEFAULTS = {
    'Bookmaker regions': ['us', 'us2', 'eu', 'uk'],
    'Regiones de casas': ['us', 'us2', 'eu', 'uk'],
    'Markets': ['h2h'],
    'Mercados': ['h2h'],
}

PROFILE_VALUES = {
    # Main default profile: Large List 70 Mode.
    'baseline_accuracy_min_books': 1,
    'baseline_accuracy_min_model_prob': 0.58,
    'baseline_accuracy_min_edge': -0.03,
    'baseline_accuracy_strong_edge': 0.04,
    'baseline_accuracy_min_strength': 38.0,
    'baseline_accuracy_use_high_conf': True,
    'baseline_accuracy_max_high_conf': 108,
    'baseline_accuracy_min_high_prob': 0.58,
    'baseline_accuracy_min_high_edge': -0.03,
    'baseline_accuracy_min_high_strength': 38.0,
    'baseline_accuracy_min_high_agent': 35.0,
    # Keep other profiles aligned but distinct.
    'balanced_confidence_min_books': 1,
    'balanced_confidence_min_model_prob': 0.60,
    'balanced_confidence_min_edge': -0.02,
    'balanced_confidence_strong_edge': 0.03,
    'balanced_confidence_min_strength': 45.0,
    'balanced_confidence_use_high_conf': True,
    'balanced_confidence_max_high_conf': 75,
    'balanced_confidence_min_high_prob': 0.60,
    'balanced_confidence_min_high_edge': -0.015,
    'balanced_confidence_min_high_strength': 45.0,
    'balanced_confidence_min_high_agent': 45.0,
    'profit_strict_min_books': 2,
    'profit_strict_min_model_prob': 0.62,
    'profit_strict_min_edge': 0.01,
    'profit_strict_strong_edge': 0.05,
    'profit_strict_min_strength': 55.0,
    'profit_strict_use_high_conf': True,
    'profit_strict_max_high_conf': 25,
    'profit_strict_min_high_prob': 0.64,
    'profit_strict_min_high_edge': 0.00,
    'profit_strict_min_high_strength': 55.0,
    'profit_strict_min_high_agent': 55.0,
}


def apply_large_list_70_defaults(st_module: Any) -> None:
    """Set Pro Predictor widget defaults without monkey-patching Streamlit.

    Streamlit buttons/uploads were fragile when we used runtime monkey-patches.
    This function only preloads session-state values for Pro Predictor widget keys.
    It does not override st.button, st.form, st.file_uploader, number_input, or
    multiselect behavior.
    """
    for key, value in PROFILE_VALUES.items():
        try:
            st_module.session_state.setdefault(key, value)
        except Exception:
            pass


def install_pro_predictor_defaults_patch() -> None:
    try:
        import streamlit as st
    except Exception:
        return
    apply_large_list_70_defaults(st)
