from dataclasses import dataclass


@dataclass
class TeamSnapshot:
    name: str
    rating: float = 1500.0


@dataclass
class EventResearchInput:
    sport: str
    event_name: str
    home: TeamSnapshot
    away: TeamSnapshot
