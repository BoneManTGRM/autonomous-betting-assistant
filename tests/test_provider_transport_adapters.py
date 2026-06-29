from autonomous_betting_agent import provider_transport_adapters as adapters


def _request():
    return {
        "sport": "tennis",
        "event": "A vs B",
        "event_start_utc": "2026-06-29T20:00:00Z",
        "market_type": "moneyline",
        "selection": "A",
    }


def test_sportsdataio_request_redacts_key():
    plan = adapters.build_sportsdataio_confirmation_request(_request(), "secret-key")
    redacted = adapters.redact_request_plan(plan)

    assert plan["headers"]["Ocp-Apim-Subscription-Key"] == "secret-key"
    assert redacted["headers"]["Ocp-Apim-Subscription-Key"] == "***"
    assert "secret-key" not in str(redacted)


def test_the_odds_request_redacts_key_param():
    plan = adapters.build_the_odds_value_request(_request(), "secret-key")
    redacted = adapters.redact_request_plan(plan)

    assert plan["params"]["apiKey"] == "secret-key"
    assert redacted["params"]["apiKey"] == "***"
    assert "secret-key" not in str(redacted)


def test_sportsdataio_transport_uses_injected_http_get():
    calls = []

    def http_get(url, params, headers):
        calls.append((url, params, headers))
        return {"provider": "sportsdataio", "home_score": 2, "away_score": 0, "confidence": 0.95}

    transport = adapters.make_sportsdataio_confirmation_transport("secret-key", http_get)
    payload = transport(_request())

    assert calls
    assert payload["provider"] == "sportsdataio"
    assert payload["primary_value"] == 2
    assert payload["secondary_value"] == 0
    assert payload["confidence"] == 0.95


def test_the_odds_transport_uses_injected_http_get():
    calls = []

    def http_get(url, params, headers):
        calls.append((url, params, headers))
        return {"provider": "the_odds_api", "locked_value": 2.0, "closing_value": 1.9}

    transport = adapters.make_the_odds_value_transport("secret-key", http_get)
    payload = transport(_request())

    assert calls
    assert payload["provider"] == "the_odds_api"
    assert payload["original_value"] == 2.0
    assert payload["latest_value"] == 1.9


def test_provider_transport_adapters_do_not_import_network_clients_or_write_paths():
    source = open("autonomous_betting_agent/provider_transport_adapters.py", encoding="utf-8").read()
    for token in ("requests" + ".", "httpx" + ".", "urllib" + ".", "write_" + "text", "write_" + "bytes"):
        assert token not in source
