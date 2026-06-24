# Optional External Context APIs

ABA Signal Pro can optionally use three external context APIs to enrich reports and review risk. These keys are optional. The app still works in local CSV-only mode without them.

```toml
# Optional external context APIs
API_FOOTBALL_KEY = ""
PERPLEXITY_API_KEY = ""
NEWSAPI_KEY = ""
```

## What they do

- `API_FOOTBALL_KEY`: soccer fixtures, team context, statistics, lineups, injuries, standings, and odds when available on the active plan.
- `PERPLEXITY_API_KEY`: concise research summaries for match context, injury notes, lineup news, travel, weather, motivation, public narrative, and game-script support.
- `NEWSAPI_KEY`: recent news search for injury, lineup, suspension, travel, coaching, motivation, and weather risk flags.

## Recommended placement

Keep the core predictor keys visible in the main API Sources block:

- Odds API
- SportsDataIO
- WeatherAPI

Place the three optional context keys in a collapsed sidebar/expander called `Optional context sources`:

- API-Football
- Perplexity
- NewsAPI

This keeps the predictor screen compact while making the optional context layer available for reports, cards, magazine output, and chain review.

A reusable Streamlit helper is available in:

```text
autonomous_betting_agent/source_key_panel.py
```

Use:

```python
from autonomous_betting_agent.source_key_panel import render_optional_context_source_panel
render_optional_context_source_panel(st, expanded=False)
```

## Safety rules

These APIs do not guarantee better results, higher win rate, ROI, profit, or winning picks. They are supporting signals only.

The primary decision system remains:

1. Core model probability
2. Odds value
3. Expected value
4. Risk score
5. Gate system
6. Subscriber/client fit

External context can weaken a pick, raise risk, add a warning, or move a pick to `WATCH ONLY`. It cannot create a `BET` by itself and cannot override bad EV.

## Missing keys

If a key is missing, the app continues normally in local CSV-only mode and shows a missing-key status in the report page.
