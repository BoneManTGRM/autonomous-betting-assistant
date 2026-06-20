from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from autonomous_betting_agent.all_high_confidence_lock import build_all_reviewed_high_confidence_locks


def test_build_all_reviewed_high_confidence_locks_keeps_all_rows():
    future = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    past = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    frame = pd.DataFrame(
        [
            {
                "event": "A at B",
                "sport": "Baseball",
                "event_start_utc": future,
                "prediction": "A",
                "decimal_price": 2.1,
                "recommended_stake_units": 0.25,
                "confidence": "HIGH",
            },
            {
                "event": "C at D",
                "sport": "Basketball",
                "event_start_utc": past,
                "prediction": "D",
                "decimal_price": 1.9,
                "confidence": "HIGH",
            },
        ]
    )

    locked = build_all_reviewed_high_confidence_locks(
        frame,
        analyst="ABA",
        max_units=1.0,
        workspace_id="test_01",
    )

    assert len(locked) == 2
    assert set(locked["ledger_type"]) == {"all_reviewed_high_confidence_internal_test"}
    assert locked["all_reviewed_high_confidence_lock"].all()
    assert locked["proof_id"].astype(str).str.len().gt(0).all()
    assert locked["locked_at_utc"].astype(str).str.len().gt(0).all()
    assert locked["official_ev_pick"].eq(False).all()
