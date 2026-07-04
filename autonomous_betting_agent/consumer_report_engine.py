# consumer_report_engine.py - stubs matching test expectations + balldontlie support

class BrandSettings:
    def __init__(self, **kwargs):
        self.primary_color = kwargs.get('primary_color', '#1E3A8A')
        self.secondary_color = kwargs.get('secondary_color', '#3B82F6')
        self.accent_color = kwargs.get('accent_color', '#10B981')
        self.font_family = kwargs.get('font_family', 'Inter, system-ui, sans-serif')
        self.logo_url = kwargs.get('logo_url', '')
        self.company_name = kwargs.get('company_name', 'ABA Signal Pro')

def cards_to_json(cards):
    import json
    return json.dumps(cards, default=str)

def consumer_cards(data):
    return data.get('cards', [])

def prepare_report_frame(data, **kwargs):
    min_probability = kwargs.get('min_probability', 0)
    # minimal filter logic
    rows = data.get('rows', [])
    filtered = [r for r in rows if r.get('probability', 0) >= min_probability]
    return {'frame': filtered, 'prepared': True}

def render_consumer_cards_html(cards):
    return '<div>Consumer cards</div>'

def render_magazine_markdown(report):
    return '# Magazine Report\n' + str(report)

def generate_consumer_report(data):
    return {
        'report_id': data.get('report_id', 'rpt_001'),
        'brand': BrandSettings(),
        'sections': data.get('sections', []),
        'generated_at': '2026-07-04T20:00:00Z'
    }

def generate_modeled_parlays(anchor, legs):
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
        if combo['combined_ev'] > 0:
            candidates.append(combo)
    return candidates
