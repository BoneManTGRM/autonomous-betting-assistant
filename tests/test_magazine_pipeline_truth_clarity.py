from autonomous_betting_agent.magazine_pipeline_runtime import build_final_enriched_picks_df, beginner_explanation, prepare_report_rows


def _base_row(**extra):
    row = {
        "sport": "WNBA",
        "event": "Las Vegas Aces vs Phoenix Mercury",
        "home_team": "Phoenix Mercury",
        "away_team": "Las Vegas Aces",
        "decimal_odds": 1.65,
        "model_probability": 0.62,
        "market_type": "spread",
        "prediction": "Phoenix Mercury -1.5",
        "line": -1.5,
    }
    row.update(extra)
    return row


def test_beginner_explains_negative_spread():
    text = beginner_explanation(_base_row(), "Phoenix Mercury", "Las Vegas Aces")
    assert "Phoenix Mercury -1.5" in text
    assert "must win by 2 or more" in text


def test_beginner_explains_positive_spread():
    text = beginner_explanation(_base_row(prediction="Las Vegas Aces +1.5", line=1.5), "Phoenix Mercury", "Las Vegas Aces")
    assert "Las Vegas Aces +1.5" in text
    assert "can win outright or lose by 1 or fewer" in text


def test_total_requires_numeric_line():
    frame = build_final_enriched_picks_df([
        _base_row(market_type="total", prediction="Game Total: Over", line="")
    ])
    row = frame.iloc[0].to_dict()
    assert row["data_issue_reason"] == "missing total line"
    assert row["final_decision"] == "BLOCKED"
    assert row["risk_label"] == "TOTAL LINE MISSING"


def test_total_explains_over_threshold():
    text = beginner_explanation(_base_row(market_type="total", prediction="Game Total: Over 171.5", line=171.5))
    assert "Over 171.5" in text
    assert "172 or more" in text


def test_structured_line_mismatch_blocks_publish():
    frame = build_final_enriched_picks_df([
        _base_row(line=-1.5, provider_line=-5.5)
    ])
    row = frame.iloc[0].to_dict()
    assert "line mismatch" in row["data_issue_reason"]
    assert row["final_decision"] == "BLOCKED"
    assert row["risk_label"] == "LINE MISMATCH"


def test_uploaded_row_stays_verify_price_and_shadow_observing():
    frame = build_final_enriched_picks_df([_base_row()])
    row = frame.iloc[0].to_dict()
    assert row["odds_status"] == "UPLOADED_ROW"
    assert row["report_truth_severity"] == "VERIFY PRICE"
    assert row["ev_display_label"] == "Unverified EV"
    assert row["shadow_mode"] == "OBSERVING_ONLY"
    assert row["shadow_recommendation"] == "BLOCK STALE PRICE"
    assert row["live_verified_stake_units"] == "0.0"


def test_demonstration_fixture_bypasses_live_enrichment_without_becoming_saved_handoff():
    row = _base_row(
        demonstration_mode=True,
        source_mode="synthetic_test_fixture",
        report_source_label="Synthetic validation fixture",
        report_data_scope="Demonstration only - not current betting advice",
        report_truth_warning="SYNTHETIC TEST DATA - NOT LIVE SPORTS INFORMATION",
    )

    prepared = prepare_report_rows([row])[0]

    assert prepared["report_source"] == "demonstration_fixture"
    assert prepared["report_source_mode"] == "synthetic_test_fixture"
    assert prepared["report_source_label"] == "Synthetic validation fixture"
    assert prepared["report_truth_severity"] == "DEMONSTRATION ONLY"
    assert prepared["risk"] == "DEMONSTRATION DATA"
    assert prepared["target_stake_units"] == "0.0"
    assert prepared["model_probability"] == 0.62
    assert "saved handoff" not in str(prepared).lower()
