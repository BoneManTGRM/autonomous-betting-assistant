from __future__ import annotations

from pathlib import Path


def test_pro_predictor_volume_required_anchors_exist():
    root = Path(__file__).resolve().parents[1]
    base = (root / 'pages' / 'pro_predictor.py').read_text(encoding='utf-8')
    anchors = [
        "min_agent = h3.number_input(t('min_agent'), min_value=0.0, max_value=100.0, value=DEFAULTS['min_agent'], step=1.0)",
        "decisions = decisions[pd.to_numeric(decisions.get('agent_score'), errors='coerce').fillna(0) >= float(min_agent)]",
        "['learned_agent_score', 'agent_score', 'learning_adjustment_score', 'scanner_strength_score', 'model_probability_clean', 'model_market_edge']",
        "'event', 'sport', 'market_type', 'line_point', 'prediction',",
    ]
    missing = [anchor for anchor in anchors if anchor not in base]
    assert not missing


def test_pro_predictor_volume_has_automation_panel_and_guarded_injection():
    root = Path(__file__).resolve().parents[1]
    wrapper = (root / 'pages' / 'pro_predictor_volume.py').read_text(encoding='utf-8')
    assert 'def render_predictor_automation_panel()' in wrapper
    assert 'Find & update wins/losses' in wrapper
    assert 'Full auto update' in wrapper
    assert 'def _replace_required(' in wrapper
    assert 'pattern_mode' in wrapper
