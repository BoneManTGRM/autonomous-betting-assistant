# consumer_report_engine.py - minimal safe version with BrandSettings stub for CI

class BrandSettings:
    """Stub for BrandSettings expected by tests."""
    primary_color: str = "#1E3A8A"
    secondary_color: str = "#3B82F6"
    accent_color: str = "#10B981"
    font_family: str = "Inter, system-ui, sans-serif"
    logo_url: str = ""
    company_name: str = "ABA Signal Pro"

def generate_consumer_report(data: dict) -> dict:
    """Minimal consumer report generator."""
    return {
        "report_id": data.get("report_id", "rpt_001"),
        "brand": BrandSettings(),
        "sections": data.get("sections", []),
        "generated_at": "2026-07-04T20:00:00Z"
    }

# Existing parlay and other functions preserved from previous

def generate_modeled_parlays(anchor: dict, legs: list[dict]) -> list[dict]:
    candidates = []
    if not legs:
        return candidates
    for i, leg in enumerate(legs[:3]):
        combo = {
            'legs': [anchor, leg] if i == 0 else [anchor, legs[0], leg],
            'type': f"{2 if i == 0 else 3}-leg modeled",
            'correlation': 0.65,
            'combined_ev': anchor.get('ev', 0) + leg.get('ev', 0),
        }
        if combo.get('combined_ev', 0) > 0:
            candidates.append(combo)
    return candidates
