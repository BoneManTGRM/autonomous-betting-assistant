from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

PATCH_VERSION = "magazine_provider_usage_v1_guard_bridge"


def _team(value: Any) -> tuple[str, str]:
    import autonomous_betting_agent.magazine_live_api_enrichment as live
    row = live._row(value)
    return live._split_teams(row)


def _date_hint(row: Mapping[str, Any]) -> str:
    import autonomous_betting_agent.magazine_live_api_enrichment as live
    for key in ("event_date", "start_time", "commence_time", "event_start_utc", "game_time"):
        value = live._get(row, key)
        if len(value) >= 10:
            return value[:10]
    return ""


def _norm(value: Any) -> str:
    import autonomous_betting_agent.magazine_live_api_enrichment as live
    return live._normalize_text(value)


def _install_display_guard() -> None:
    try:
        from autonomous_betting_agent.magazine_display_guard import install as install_display_guard
        install_display_guard()
    except Exception:
        pass


def _patch_report_polish_install() -> None:
    try:
        import autonomous_betting_agent.magazine_report_polish_patch as polish
    except Exception:
        return
    original = getattr(polish, "install", None)
    if not callable(original) or getattr(original, "_ABA_DISPLAY_GUARD_BRIDGE", False):
        return

    def install_and_guard(*args: Any, **kwargs: Any):
        result = original(*args, **kwargs)
        _install_display_guard()
        return result

    install_and_guard._ABA_DISPLAY_GUARD_BRIDGE = True
    polish.install = install_and_guard  # type: ignore[assignment]


def _api_football_team(team: str, key: str) -> dict[str, Any]:
    import autonomous_betting_agent.magazine_live_api_enrichment as live
    if not team:
        return {}
    data = live._request_json(
        "https://v3.football.api-sports.io/teams?search=" + live.quote_plus(team),
        headers={"x-apisports-key": key},
        cache_key=("api-football-team-v2", team.lower()),
    )
    response = data.get("response") if isinstance(data, Mapping) else None
    if not isinstance(response, list) or not response:
        return {}
    item = response[0] if isinstance(response[0], Mapping) else {}
    team_data = item.get("team") if isinstance(item, Mapping) else None
    return dict(team_data) if isinstance(team_data, Mapping) else {}


def _api_football_fixture(row: Mapping[str, Any], key: str) -> dict[str, Any]:
    import autonomous_betting_agent.magazine_live_api_enrichment as live
    away, home = _team(row)
    teams = [_api_football_team(name, key) for name in (away, home)]
    team_ids = [str(team.get("id")) for team in teams if team.get("id")]
    date = _date_hint(row)
    candidates: list[dict[str, Any]] = []
    for team_id in team_ids[:2]:
        params: dict[str, str] = {"team": team_id}
        if date:
            params["date"] = date
        else:
            params["last"] = "3"
        url = "https://v3.football.api-sports.io/fixtures?" + live.urlencode(params)
        data = live._request_json(
            url,
            headers={"x-apisports-key": key},
            cache_key=("api-football-fixture-v2", team_id + "|" + date),
        )
        response = data.get("response") if isinstance(data, Mapping) else None
        if isinstance(response, list):
            candidates.extend([item for item in response if isinstance(item, Mapping)])
    away_n = _norm(away)
    home_n = _norm(home)
    for fixture in candidates:
        teams_obj = fixture.get("teams") if isinstance(fixture, Mapping) else None
        if not isinstance(teams_obj, Mapping):
            continue
        names = []
        for side in ("home", "away"):
            side_obj = teams_obj.get(side)
            if isinstance(side_obj, Mapping):
                names.append(_norm(side_obj.get("name")))
        joined = " ".join(names)
        if (away_n and away_n in joined) or (home_n and home_n in joined):
            return dict(fixture)
    return candidates[0] if candidates else {}


def _patched_api_football(row: dict[str, Any]) -> None:
    import autonomous_betting_agent.magazine_live_api_enrichment as live
    if live._sport_kind(row) != "soccer":
        row.setdefault("api_football_match_status", "SPORT_UNSUPPORTED")
        row.setdefault("api_football_failure_reason", "Not a soccer/FIFA row")
        return
    key = live._secret(*live.API_SECRET_DEFS["API-Football"])
    if not key:
        row.setdefault("api_football_match_status", "API_KEY_MISSING")
        row.setdefault("api_football_failure_reason", "API-Football key missing")
        return
    try:
        fixture = _api_football_fixture(row, key)
    except Exception as exc:
        row["api_football_match_status"] = "API_ERROR"
        row["api_football_failure_reason"] = exc.__class__.__name__
        return
    if not fixture:
        away, home = _team(row)
        row["api_football_match_status"] = "NO_FIXTURE_MATCH"
        row["api_football_failure_reason"] = "API-Football returned no fixture match for teams/date"
        row["api_football_summary"] = f"API-Football checked {away or 'away'} / {home or 'home'}; fixture not matched."
        return
    fixture_obj = fixture.get("fixture") if isinstance(fixture.get("fixture"), Mapping) else {}
    teams_obj = fixture.get("teams") if isinstance(fixture.get("teams"), Mapping) else {}
    goals_obj = fixture.get("goals") if isinstance(fixture.get("goals"), Mapping) else {}
    venue = fixture_obj.get("venue") if isinstance(fixture_obj.get("venue"), Mapping) else {}
    status = fixture_obj.get("status") if isinstance(fixture_obj.get("status"), Mapping) else {}
    home = teams_obj.get("home") if isinstance(teams_obj.get("home"), Mapping) else {}
    away = teams_obj.get("away") if isinstance(teams_obj.get("away"), Mapping) else {}
    fixture_id = fixture_obj.get("id") or fixture.get("fixture_id")
    row["api_football_fixture_id"] = str(fixture_id or "")
    row["api_football_match_status"] = "MATCHED"
    score = ""
    if goals_obj:
        score = f" {goals_obj.get('home', '')}-{goals_obj.get('away', '')}".strip()
    fixture_date = str(fixture_obj.get("date") or "")[:16]
    venue_bits = [str(venue.get(k)) for k in ("name", "city") if venue.get(k)]
    venue_text = ", ".join(venue_bits)
    status_text = str(status.get("short") or status.get("long") or "fixture matched")
    summary = f"API-Football matched {home.get('name', 'home')} vs {away.get('name', 'away')}"
    if score:
        summary += f"; score {score}"
    summary += f"; status {status_text}"
    if fixture_date:
        summary += f"; date {fixture_date}"
    if venue_text:
        summary += f"; venue {venue_text}"
    summary += "."
    row["api_football_summary"] = summary
    row["api_football_team_summary"] = summary
    if venue.get("city"):
        country = str(venue.get("country") or "")
        row.setdefault("weather_location", ", ".join(part for part in (str(venue.get("city")), country) if part))


def _patched_weather(row: dict[str, Any]) -> None:
    import autonomous_betting_agent.magazine_live_api_enrichment as live
    if row.get("weather_status") == "LIVE":
        return
    live._enrich_weather_original_provider_usage(row)  # type: ignore[attr-defined]
    if row.get("weather_status") == "NO_LOCATION" and live._sport_kind(row) == "soccer":
        row["weather_status"] = "NOT_NEEDED_NO_VENUE"
        row["weather_failure_reason"] = "No verified venue/city available from row or API-Football fixture"
        row["weather_summary"] = "Weather not used because no verified venue/city was attached to this match."


def install() -> None:
    import autonomous_betting_agent.magazine_live_api_enrichment as live
    _patch_report_polish_install()
    if getattr(live, "_PROVIDER_USAGE_PATCH", "") == PATCH_VERSION:
        _install_display_guard()
        return
    if not hasattr(live, "_enrich_weather_original_provider_usage"):
        live._enrich_weather_original_provider_usage = live._enrich_weather  # type: ignore[attr-defined]
    live._enrich_api_football = _patched_api_football  # type: ignore[assignment]
    live._enrich_weather = _patched_weather  # type: ignore[assignment]

    original_enrich = live.enrich_row_with_live_api_data

    def enrich_row(row_like: Any, *, report_run_id: str | None = None, last_api_refresh_time: str | None = None) -> dict[str, Any]:
        row = live._row(row_like)
        if row.get("_live_api_enriched") == live.ENRICHMENT_VERSION and row.get("report_source") == "final_enriched_picks_df":
            return original_enrich(row, report_run_id=report_run_id, last_api_refresh_time=last_api_refresh_time)
        report_run_id = report_run_id or f"aba_mag_{int(live.time.time())}_{live._hash_payload(row)}"
        last_api_refresh_time = last_api_refresh_time or datetime.now(timezone.utc).isoformat(timespec="seconds")
        live._enrich_sportsdataio(row)
        live._enrich_api_football(row)
        live._enrich_weather(row)
        live._enrich_news(row)
        live._enrich_perplexity(row)
        live._apply_truth_fields(row, report_run_id, last_api_refresh_time)
        row["_live_api_enriched"] = live.ENRICHMENT_VERSION
        live._install_spanish_renderer_patch()
        return live._apply_spanish(live._render_cleanup(row))

    live.enrich_row_with_live_api_data = enrich_row  # type: ignore[assignment]
    live._PROVIDER_USAGE_PATCH = PATCH_VERSION
    _install_display_guard()
