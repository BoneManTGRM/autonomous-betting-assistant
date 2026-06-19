from autonomous_betting_agent import pick_hold_store
from autonomous_betting_agent import live_odds


def test_store_helpers_import():
    assert callable(pick_hold_store.save_held_rows)
    assert callable(pick_hold_store.load_held_rows)
    assert callable(pick_hold_store.verify_held_rows)
    assert callable(pick_hold_store.store_snapshot)


def test_live_odds_models_import():
    assert hasattr(live_odds, "OutcomePrice")
    assert hasattr(live_odds, "MarketLine")
    assert hasattr(live_odds, "scan_market")
