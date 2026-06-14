# Profitable 70 Percent Goal Tracker

This layer checks whether a finished-picks CSV is actually meeting the practical Marco-style target:

```text
70% win rate +/- 1%
average odds above 1.43
positive ROI
positive closing-line value
no duplicate padding
tracked over hundreds of finished picks
```

## Why this exists

A high win rate can still lose money if the average odds are too low. This tracker checks win rate, payout quality, ROI, CLV and duplicates together.

## Command

```bash
python tools/run_profit_goal_review.py predictions.csv
```

Default output:

```text
data/profit_goal_report.json
```

## Useful CSV columns

Minimum useful columns:

```text
event
start
prediction
result
best_price
```

Better columns:

```text
closing_odds
closing_line_value
sport
classification
bookmaker_count
```

## Goal checks

The report checks:

- enough finished non-push picks
- win rate inside or above the 70% +/- 1% band
- average odds at or above 1.43
- positive ROI
- positive average CLV
- no duplicate event/start/pick rows

## No-API mode

This works without external APIs if the CSV contains results, entry odds and closing odds. Without closing odds or a direct CLV column, the report can still calculate win rate, average odds, ROI and duplicates, but it cannot prove positive CLV.

Use `--allow-missing-clv` only for temporary tracking. The stricter version should require closing-line data.

## Example

```bash
python tools/run_profit_goal_review.py pro_predictor_updated_win_loss.csv --min-finished 200
```

Temporary no-CLV review:

```bash
python tools/run_profit_goal_review.py pro_predictor_updated_win_loss.csv --allow-missing-clv
```

## Important limitation

This does not prove future profitability. It verifies whether the historical or tracked sample currently meets the goal after deduping and after accounting for odds quality. The goal should be trusted only after hundreds of prospectively tracked picks.
