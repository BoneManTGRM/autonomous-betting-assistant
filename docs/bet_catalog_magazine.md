# Bet Catalog and Betting Magazine

`autonomous_betting_agent.bet_catalog` implements the issue #52 catalog and subscriber-ready magazine output layer.

## What it does

The helper accepts rows that already contain sports analysis and odds fields, then produces:

- Best 65%+ Singles
- Best Good-Odds Bets
- Closest Double-Money Bets
- Conservative Baseball Chains
- Balanced Baseball Chains
- Aggressive Baseball Chains
- Player Prop Catalog
- Home Run Watchlist
- Good Read / Bad Price
- No-Bet List

## Required final pick fields

Each rendered pick card includes:

- Game
- Exact bet
- Sportsbook/casino
- Current odds
- Implied probability
- Model probability
- 65%+ filter PASS/FAIL
- Edge
- EV
- Risk score
- Recommended stake
- Why we are picking the bet
- Why it could lose
- Final recommendation

## 65% rule

The 65% gate is a projected model-probability filter only. It does not claim a guaranteed actual win rate. Actual win rate still has to come from the graded ledger.

Core singles enter `Best 65%+ Singles` only when:

1. Model probability is at least 65%.
2. The bet is not a chain or player prop.
3. The final decision is playable.
4. The odds/EV gate is acceptable.

## Chain rule

Chain bets use supplied `combined_adjusted_probability`, `adjusted_combined_probability`, or `chain_probability` when present. If those are absent, the helper multiplies leg probabilities and applies a small correlation penalty.

A chain is not labeled as 65%+ unless the combined adjusted chain probability is actually at least 65%.

## Safety labels

The helper can output these final decisions:

- BET
- SMALL BET
- CHAIN ONLY
- WAIT FOR BETTER ODDS
- WATCH ONLY
- NO BET
- GOOD READ, BAD PRICE
- BAD VALUE
- AGGRESSIVE ONLY

## Example

```python
from autonomous_betting_agent.bet_catalog import render_betting_magazine

rows = [
    {
        "game": "Dodgers vs Padres",
        "sport": "MLB Baseball",
        "bet_type": "Moneyline",
        "exact_bet": "Dodgers Moneyline",
        "sportsbook": "Caliente",
        "decimal_odds": 1.75,
        "model_probability": 0.68,
        "why_pick": "Starting pitcher edge, bullpen rest, and lineup form support the Dodgers.",
        "why_lose": "Late lineup changes or bullpen variance could flip the edge.",
    }
]

print(render_betting_magazine(rows, subscriber_name="Subscriber A"))
```

## Important limitation

This module is a formatting, gating, and catalog-building layer. It does not fetch live sportsbook odds, execute bets, or guarantee outcomes.
