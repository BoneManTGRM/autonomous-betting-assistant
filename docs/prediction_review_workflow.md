# Prediction Review Workflow

This workflow turns a new prediction CSV into checked outputs that can be reviewed consistently.

## Command

```bash
python tools/run_prediction_review.py "weather_enhanced_predictions.csv"
```

## Default outputs

```text
data/predictions_checked.csv
data/predictions_checked_deduped.csv
data/predictions_review_report.json
```

## What the review does

The review command runs the CSV through the ARA, deep-analysis, and best-bet layers. It then adds audit fields for record key, duplicate count, duplicate status, normalized result status, and unit profit or loss.

The JSON report summarizes:

- raw performance
- deduped performance
- final status counts
- grade counts
- risk flag counts
- duplicate rows
- qualified rows
- rejected rows

## Final status rules

Only these statuses should be treated as shortlist candidates:

```text
QUALIFIED_STRONG
QUALIFIED
QUALIFIED_SMALL
```

These statuses are not ready for action:

```text
WATCH
TRACK_ONLY_NEEDS_MODEL_PROBABILITY
REJECT
```

## Weather safety

WeatherAPI results are validated against the requested query. If WeatherAPI resolves the query to the wrong city, region, or country, strict fetching raises `WeatherLocationMismatchError` and the row should not be trusted.

Strict location checking is on by default in `fetch_weather_snapshot()`.
