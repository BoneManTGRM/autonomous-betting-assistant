from __future__ import annotations

import sys

from autonomous_betting_agent.license_status import make_license_record, normalize_client_status, upsert_license_record
from autonomous_betting_agent.local_alerts import bad_price_alert, grading_conflict_alert, sqlite_fallback_alert


def test_local_alerts_are_structured_messages():
    alert = bad_price_alert("Outlier price")
    assert alert["kind"] == "bad_price"
    assert alert["severity"] == "warning"
    assert "Outlier price" in alert["message"]
    assert sqlite_fallback_alert()["kind"] == "sqlite_fallback"
    assert grading_conflict_alert("P1")["kind"] == "grading_conflict"


def test_license_status_normalizes_values():
    assert normalize_client_status("ACTIVE") == "active"
    assert normalize_client_status("unknown") == "inactive"


def test_license_record_can_be_upserted(tmp_path):
    path = tmp_path / "licenses.csv"
    record = make_license_record("Client A", client_status="active")
    records = upsert_license_record(record, path=path)
    assert len(records) == 1
    assert records[0].client_status == "active"
    assert path.exists()


def test_license_module_does_not_import_stripe():
    assert "stripe" not in sys.modules
