from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict

from autonomous_betting_agent import AutonomousBettingAgent, EventResearchInput, TeamSnapshot
from autonomous_betting_agent.output import render_text


def _team(data: Dict[str, Any]) -> TeamSnapshot:
    return TeamSnapshot(**data)


def _event(data: Dict[str, Any]) -> EventResearchInput:
    return EventResearchInput(
        sport=data["sport"],
        event_name=data["event_name"],
        home=_team(data["home"]),
        away=_team(data["away"]),
        neutral_site=bool(data.get("neutral_site", False)),
        home_market_price=data.get("home_market_price"),
        away_market_price=data.get("away_market_price"),
        metadata=dict(data.get("metadata", {})),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a sports research report.")
    parser.add_argument("event_json", type=Path)
    parser.add_argument("--json-output", type=Path, default=None)
    args = parser.parse_args()
    try:
        event = _event(json.loads(args.event_json.read_text(encoding="utf-8")))
        result = AutonomousBettingAgent().analyze(event)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
        return 2
    if args.json_output:
        args.json_output.write_text(json.dumps(asdict(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"Wrote JSON output to {args.json_output}")
    else:
        print(render_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
