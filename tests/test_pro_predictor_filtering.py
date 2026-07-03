import pandas as pd

from autonomous_betting_agent.pro_predictor_filtering import (
    FILTER_DIAGNOSTIC_TIER,
    apply_filter_audit,
    diagnostic_mode_allowed,
    make_research_diagnostic_candidates,
)


def test_filter_audit_shows_first_blocking_gate():
    frame = pd.DataFrame(
        [
            {
                "model_probability_clean": 0.54,
                "model_market_edge": -0.02,
                "scanner_strength_score": 10,
                "agent_score": 30,
            }
        ]
    )

    filtered, audit = apply_filter_audit(frame, min_prob=0.58, min_edge=-0.05, min_signal=1, min_agent=1)

    assert filtered.empty
    assert audit.iloc[0]["gate"] == "Minimum model probability"
    assert audit.iloc[0]["before_rows"] == 1
    assert audit.iloc[0]["after_rows"] == 0


def test_diagnostic_candidates_are_review_only():
    frame = pd.DataFrame(
        [
            {
                "event": "Away at Home",
                "model_probability_clean": 0.54,
                "model_market_edge": -0.02,
                "scanner_strength_score": 10,
                "agent_score": 30,
                "decision_signals": "large_list_volume_candidate",
            }
        ]
    )
    _, audit = apply_filter_audit(frame, min_prob=0.58, min_edge=-0.05, min_signal=1, min_agent=1)

    diagnostic = make_research_diagnostic_candidates(frame, audit, max_rows=10)

    assert len(diagnostic) == 1
    assert diagnostic.iloc[0]["recommendation_tier"] == FILTER_DIAGNOSTIC_TIER
    assert bool(diagnostic.iloc[0]["client_report_ready"]) is False


def test_diagnostic_mode_requires_late_gates_to_be_intentionally_loosened():
    assert diagnostic_mode_allowed(min_signal=1, min_agent=1)
    assert not diagnostic_mode_allowed(min_signal=38, min_agent=1)
    assert not diagnostic_mode_allowed(min_signal=1, min_agent=35)
