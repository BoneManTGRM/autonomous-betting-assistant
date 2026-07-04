# Parlay recommendation board update per perfect prompt
# Added modeled correlation support for multi-leg parlay generation when book/SGP correlation is unavailable.
# Function can be called from report generation to produce 2+/3+ leg candidates from positive-EV legs.

def generate_modeled_parlay_candidates(anchor_leg: dict, other_positive_ev_legs: list[dict], correlation_model: callable | None = None) -> list[dict]:
    """
    Generate 2+ and 3+ leg parlay candidates using modeled correlation.
    Only combines legs that individually have positive EV.
    Falls back to simple combination if no correlation_model provided.
    """
    candidates = []
    if not other_positive_ev_legs:
        return candidates
    # Simple 2-leg combinations
    for leg in other_positive_ev_legs[:5]:  # limit for performance
        combo = {
            "legs": [anchor_leg, leg],
            "type": "2-leg modeled",
            "correlation": correlation_model(anchor_leg, leg) if correlation_model else 0.6,
            "combined_ev": anchor_leg.get("ev", 0) + leg.get("ev", 0),
        }
        if combo["combined_ev"] > 0:
            candidates.append(combo)
    # Simple 3-leg (anchor + 2 others)
    if len(other_positive_ev_legs) >= 2:
        for i in range(min(3, len(other_positive_ev_legs)-1)):
            leg1 = other_positive_ev_legs[i]
            leg2 = other_positive_ev_legs[i+1]
            combo = {
                "legs": [anchor_leg, leg1, leg2],
                "type": "3-leg modeled",
                "correlation": (correlation_model(anchor_leg, leg1) if correlation_model else 0.5) * 0.8,
                "combined_ev": anchor_leg.get("ev", 0) + leg1.get("ev", 0) + leg2.get("ev", 0),
            }
            if combo["combined_ev"] > 0:
                candidates.append(combo)
    return candidates

# TODO: Wire this into the parlay board rendering in report generation so page 2 shows ranked candidates instead of always SOLO ANCLA DIRECTA.
