# Daily Chain Report

The Daily Chain Report generates a morning-style chain betting summary from already-supplied candidate rows. It is analytics and decision support only. It does not place bets, fetch live data, expose API keys, or guarantee wins/profit.

## What it does

The report ranks same-game and uploaded chain opportunities by:

- main-read strength
- add-on leg quality
- correlation strength
- market value
- injury confirmation
- lineup confirmation
- weather safety
- filler-leg risk
- straight-bet comparison
- risk penalty

It then renders:

1. A daily summary
2. Compact chain cards
3. An optional single-game deep-dive magazine
4. CSV export rows

## Editable report names

The Streamlit magazine page supports editable names for:

- Magazine Report Name
- Daily Chain Report Name
- Single-Game Report Name

The editable names are used as Markdown H1 titles and sanitized download filenames.

Example:

```text
Marco Daily Chain Report -> marco_daily_chain_report.md
Yankees vs Red Sox Deep Dive -> yankees_vs_red_sox_deep_dive.md
```

## Required input fields

At minimum, rows should include:

```text
game
exact_bet or pick or selection
model_probability
```

A single uploaded chain row can also include:

```text
chain
legs
combined_adjusted_probability
chain_probability
main_read
add_on_legs
```

## Optional professional input fields

The report can use these fields when available:

```text
sport
league
start_time
sportsbook
best_bookmaker
decimal_odds
american_odds
edge
expected_value
ev
risk_score
filler_leg_risk
correlation_score
correlation_label
straight_bet_alternative
straight_bet_comparison
better_straight_or_chain
lineup_status
starting_lineups
injury_report
weather_impact
market_movement
line_movement
sharp_money_signal
news_signal
pro_notes
why_bullets
why_we_picked_it
```

## Example compact chain card

```text
1. Yankees vs Red Sox

MAIN READ:
Yankees ML

CHAIN:
Yankees ML + Judge 1+ Hit + Over 7.5

Confidence: 61%
Edge: +5.4%
Risk: Medium
Filler Risk: Low
Correlation: Positive
Units: 0.25-0.50
Deep Dive Available: Yes
Better As Straight: No

Why It Works:
- Main read has model edge
- Prop supports same script
- Bullpen fatigue supports late runs
- Weather helps offense
- Market still playable

Risk:
- Avoid if lineup or injury news changes
```

## Example single-game magazine

```text
# Yankees vs Red Sox Deep Dive

Game: Yankees vs Red Sox
League: MLB
Start Time: 7:05 PM
Sportsbook: Caliente
Risk Profile: balanced

## Executive Summary

• Best Play: Yankees ML
• Best Chain: Yankees ML + Judge 1+ Hit + Over 7.5
• Best Straight Alternative: Yankees ML
• Confidence: 61%
• Risk: Medium
• Pass/No Pass: PASS
```

## Chain learning warnings

When existing chain learning memory is available, the daily report shows warnings such as:

- Similar filler or target-payout legs failed before.
- Straight bet has beaten similar chains before.
- Review historical failed-leg patterns before chaining.

If no learning memory exists, the report says:

```text
No chain learning memory yet. Grade completed chains to improve future reports.
```

## Safety limitations

This feature does not:

- execute bets
- guarantee wins
- guarantee profit
- expose API keys
- require live API calls for tests
- add legs only to chase payout

All output is for analytics and decision support only.
