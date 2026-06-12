from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AgentConfig:
    default_sport: str = "basketball"
    log_dir: Path = Path("logs")
    data_dir: Path = Path("data")
    reports_dir: Path = Path("reports")
    min_data_completeness: float = 0.70
    min_source_count: int = 6
    allow_live_market_data: bool = False


def load_config() -> AgentConfig:
    return AgentConfig(
        default_sport=os.getenv("ABA_DEFAULT_SPORT", "basketball"),
        log_dir=Path(os.getenv("ABA_LOG_DIR", "logs")),
        data_dir=Path(os.getenv("ABA_DATA_DIR", "data")),
        reports_dir=Path(os.getenv("ABA_REPORTS_DIR", "reports")),
        min_data_completeness=float(os.getenv("ABA_MIN_DATA_COMPLETENESS", "0.70")),
        min_source_count=int(os.getenv("ABA_MIN_SOURCE_COUNT", "6")),
        allow_live_market_data=os.getenv("ABA_ALLOW_LIVE_MARKET_DATA", "false").lower() in {"1", "true", "yes", "on"},
    )
