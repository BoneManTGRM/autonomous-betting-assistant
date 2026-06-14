from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class APICallRecord:
    cache_key: str
    provider: str
    endpoint: str
    used_cache: bool
    cost_units: int


@dataclass(frozen=True)
class APIBudgetReport:
    max_api_calls_per_run: int
    calls_made: int
    cache_hits: int
    cache_misses: int
    blocked_calls: int
    records: list[APICallRecord]


class APIBudgetManager:
    def __init__(self, *, cache_dir: str | Path = "data/api_cache", max_api_calls_per_run: int = 25, ttl_seconds: int = 900) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_api_calls_per_run = max_api_calls_per_run
        self.ttl_seconds = ttl_seconds
        self.calls_made = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.blocked_calls = 0
        self.records: list[APICallRecord] = []

    def _key(self, provider: str, endpoint: str, params: Mapping[str, Any] | None = None) -> str:
        payload = json.dumps({"provider": provider, "endpoint": endpoint, "params": dict(params or {})}, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _path(self, cache_key: str) -> Path:
        return self.cache_dir / f"{cache_key}.json"

    def _fresh(self, path: Path) -> bool:
        if not path.exists():
            return False
        age = time.time() - path.stat().st_mtime
        return age <= self.ttl_seconds

    def call(self, *, provider: str, endpoint: str, params: Mapping[str, Any] | None = None, fetcher: Callable[[], Any], force_refresh: bool = False) -> Any:
        cache_key = self._key(provider, endpoint, params)
        path = self._path(cache_key)
        if not force_refresh and self._fresh(path):
            self.cache_hits += 1
            self.records.append(APICallRecord(cache_key, provider, endpoint, True, 0))
            return json.loads(path.read_text(encoding="utf-8"))
        if self.calls_made >= self.max_api_calls_per_run:
            self.blocked_calls += 1
            raise RuntimeError(f"API budget exceeded: max_api_calls_per_run={self.max_api_calls_per_run}")
        self.cache_misses += 1
        self.calls_made += 1
        payload = fetcher()
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.records.append(APICallRecord(cache_key, provider, endpoint, False, 1))
        return payload

    def report(self) -> APIBudgetReport:
        return APIBudgetReport(
            max_api_calls_per_run=self.max_api_calls_per_run,
            calls_made=self.calls_made,
            cache_hits=self.cache_hits,
            cache_misses=self.cache_misses,
            blocked_calls=self.blocked_calls,
            records=self.records,
        )

    def write_report(self, path: str | Path) -> None:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(asdict(self.report()), indent=2, sort_keys=True) + "\n", encoding="utf-8")
