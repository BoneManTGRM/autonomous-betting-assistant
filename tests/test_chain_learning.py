from autonomous_betting_agent.chain_learning import (
    LOSS,
    PUSH,
    UNKNOWN,
    VOID,
    build_chain_learning_signal,
    grade_chain_leg,
    grade_chain_result,
    identify_failed_chain_leg,
)
from autonomous_betting_agent.chain_learning_store import (
    append_chain_learning_result,
    load_chain_learning_memory,
    summarize_chain_learning_memory,
)


def leg(name, market, status, **extra):
    row = {
        "leg_name": name,
        "market": market,
        "selection": name,
        "result_status": status,
    }
    row.update(extra)
    return row


def test_detects_add_on_leg_failure_when_main_read_wins():
    chain = {
        "chain_id": "c1",
        "game": "Portugal vs Uzbekistan",
        "legs": [
            leg("Portugal moneyline", "moneyline", "win", was_main_read=True, game_script_supported=True),
            leg("Uzbekistan corners over 1.5", "corners", "loss", game_script_supported=True),
        ],
    }
    result = grade_chain_result(chain)
    failed = identify_failed_chain_leg(result)
    assert result.main_read_correct is True
    assert failed is not None
    assert failed.was_add_on_leg is True
    assert "add-on" in result.learning_summary.lower()


def test_detects_game_script_wrong():
    chain = {
        "chain_id": "c2",
        "game": "A vs B",
        "legs": [leg("Main read", "moneyline", "loss", was_main_read=True, game_script_supported=True)],
    }
    result = grade_chain_result(chain)
    assert result.game_script_correct is False


def test_detects_straight_bet_would_have_won_but_chain_lost():
    chain = {
        "chain_id": "c3",
        "game": "A vs B",
        "straight_pick_status": "win",
        "legs": [leg("Add on", "corners", "loss")],
    }
    result = grade_chain_result(chain)
    assert result.straight_bet_would_have_won is True
    assert "Straight bet would have won" in result.learning_summary


def test_detects_target_payout_filler_leg():
    chain = {
        "chain_id": "c4",
        "game": "A vs B",
        "target_payout_fit": "Good target fit",
        "legs": [leg("Random filler", "prop", "loss", was_filler_leg=True)],
    }
    result = grade_chain_result(chain)
    assert result.target_payout_chase_detected is True
    signal = build_chain_learning_signal(result)
    assert signal.signal_type in {"target_payout_chase", "straight_bet_better", "failed_leg_pattern"}
    assert "filler" in signal.reason.lower() or signal.leg_type == "filler"


def test_failed_underdog_corner_leg_signal():
    chain = {
        "chain_id": "c5",
        "game": "A vs B",
        "legs": [
            leg("Favorite moneyline", "moneyline", "win", was_main_read=True),
            leg("Underdog corners", "corners", "loss"),
        ],
    }
    result = grade_chain_result(chain)
    signal = build_chain_learning_signal(result)
    assert "corner" in signal.reason.lower() or signal.market_type == "corners"
    assert signal.adjustment_direction in {"decrease", "watch_only"}


def test_unknown_legs_do_not_create_strong_learning():
    result = grade_chain_result({"chain_id": "c6", "legs": [leg("Unknown", "cards", "")]})
    signal = build_chain_learning_signal(result)
    assert signal.adjustment_direction == "neutral"
    assert signal.confidence == 0.0


def test_push_void_legs_are_neutral():
    push = grade_chain_leg(leg("Push leg", "total", "push"))
    void = grade_chain_leg(leg("Void leg", "total", "void"))
    assert push.status == PUSH
    assert void.status == VOID
    assert "Neutral" in push.failed_reason
    assert "Neutral" in void.failed_reason


def test_saves_and_loads_memory_safely(tmp_path):
    path = tmp_path / "chain_learning_memory.json"
    result = grade_chain_result({"chain_id": "c7", "game": "A vs B", "legs": [leg("Bad add", "corners", "loss")]})
    memory = append_chain_learning_result(result, path=path)
    loaded = load_chain_learning_memory(path)
    summary = summarize_chain_learning_memory(loaded)
    assert path.exists()
    assert summary["graded_result_count"] == 1
    assert "corners" in loaded["leg_failure_patterns"]


def test_does_not_modify_existing_adaptive_learning_unexpectedly():
    import autonomous_betting_agent.adaptive_learning as adaptive_learning

    assert hasattr(adaptive_learning, "apply_adaptive_learning")
