from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class Cycle:
    number: int
    phase: str
    notes: List[str] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)


class CycleLog:
    def __init__(self) -> None:
        self.cycles: List[Cycle] = []

    def add(self, phase: str, notes: List[str], data: Dict[str, Any] | None = None) -> None:
        self.cycles.append(Cycle(len(self.cycles) + 1, phase, list(notes), dict(data or {})))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_count": len(self.cycles),
            "cycles": [
                {"number": c.number, "phase": c.phase, "notes": c.notes, "data": c.data}
                for c in self.cycles
            ],
        }
