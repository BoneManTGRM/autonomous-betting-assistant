# Autonomous Betting Agent

[![tests](https://github.com/BoneManTGRM/autonomous-betting-agent/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/BoneManTGRM/autonomous-betting-agent/actions/workflows/tests.yml)

Autonomous Betting Agent is a standalone sports research agent built from the ARA/TGRM idea: run repeatable research cycles, detect weak evidence, repair the analysis, verify uncertainty, and produce transparent probability reports.

This is **research-only software**. It does not place bets, does not guarantee winners, and should not be treated as proof of profitability without rigorous backtesting and prospective testing.

## What it does

- estimates win probabilities for two-outcome sports events
- lets each app user paste their own provider access token
- scans live market feeds when a provider token is supplied
- ranks the most likely outcome for upcoming games
- estimates likely scorelines such as 1-1 and 2-1
- scores individual player props such as touchdown, home run, goal, shot on goal, assist, hit, strikeout, reception, rushing yards, receiving yards and passing yards
- explains which factors moved the manual ARA model
- tracks confidence, evidence strength and uncertainty
- compares model probabilities with no-vig market probabilities
- calculates expected-value diagnostics for later testing
- logs a TGRM-style TEST, DETECT, REPAIR, VERIFY cycle
- supports backtesting metrics such as Brier score, accuracy and closing-line delta
- learns probability calibration from graded results and applies it to future predictions
- tracks predicted winner, model probability, calibrated probability, sportsbook odds, implied probability, edge, result, profit/loss, closing-line value, confidence buckets and sport-level performance
- adds strict ARA, deep-analysis and best-bet layers so weak, low-edge, bad-weather, bad-location or favorite-heavy picks can be filtered instead of counted as real recommendations
- includes a CLI, sample event file, Streamlit UI, unit tests and GitHub Actions test workflow

## ARA/TGRM lineage

This project is separated from the original ARA repository so the original research agent remains clean. The new repo keeps the useful architecture pattern:

1. **TEST** the available event data.
2. **DETECT** weak sources, incomplete inputs and unstable signals.
3. **REPAIR** the analysis by converting evidence into auditable factors.
4. **VERIFY** with confidence, RYE-style efficiency and stability metrics.

The domain target is sports analytics rather than longevity or scientific literature review.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run the sample

```bash
python run_agent.py examples/sample_event.json
```

Write JSON output to a file:

```bash
python run_agent.py examples/sample_event.json --json-output result.json
```

Run with a learned calibration state:

```bash
python run_agent.py examples/sample_event.json --learned-state learned_state.json
```

## Make it learn from graded results

The learning loop is now:

```text
prediction -> final result -> graded CSV -> train calibration -> learned_state.json -> future predictions
```

Train from a graded CSV:

```bash
python learn_from_results.py pro_predictor_updated_win_loss.csv --output learned_state.json
```

The CSV parser accepts common columns such as:

- `probability`, `predicted_probability`, `favorite_probability`, `model_probability` or `market_probability`
- `result`, `outcome`, `win_loss`, or `graded_result` with values like `won`, `lost`, `1`, or `0`
- optional `prediction` / `pick` and `winner` / `actual_winner` columns

The learned state stores calibration parameters, events trained, Brier score before/after, log loss before/after, and accuracy before/after. If `learned_state.json` exists in the project root, the live market scanner applies it automatically.

This is probability calibration, not proof of edge. It learns whether the raw market/model probabilities have been too confident, too cautious, or biased based on past graded predictions. Retrain it whenever more finished games are added.

## Track picks, edge, profit/loss and CLV

Use the tracker after predictions have been graded:

```bash
python track_predictions.py pro_predictor_updated_win_loss.csv --ledger-output prediction_ledger_enriched.csv --report-output prediction_report.json
```

The tracker accepts flexible CSV columns and enriches each row with:

- `predicted_winner`
- `model_probability`
- `calibrated_probability`
- `sportsbook_odds`
- `implied_probability`
- `edge`
- `expected_value`
- `actual_winner`
- `result`
- `profit_loss`
- `closing_odds`
- `closing_implied_probability`
- `closing_line_value`
- `confidence_bucket`
- `decision`
- `decision_reason`
- `sport`
- `bookmaker_count`

The report summarizes resolved picks, wins/losses/pushes, hit rate, average probabilities, Brier score, log loss, unit profit/loss, ROI, average edge, average closing-line value and performance by decision, confidence bucket and sport.

## ARA decision layer

The ARA decision layer lives in `autonomous_betting_agent/ara_filters.py`. It adds auditable columns such as:

- `ara_risk_flags`
- `ara_weather_flags`
- `ara_live_decision`
- `ara_live_stake_units`
- `ara_proxy_filter_decision`
- `ara_requires_independent_probability`

It blocks or watches common failure modes, including:

- heavy favorites under `1.30`
- longshots over `3.00`
- low book coverage
- low data quality
- soccer draw-risk moneylines
- missing independent model probability
- WeatherAPI errors
- missing weather for weather-relevant games
- non-exact weather forecast dates
- returned WeatherAPI location mismatches

Weather location validation compares the original query against the returned city/region/country. A successful WeatherAPI call is not automatically trusted if the returned place does not match the intended event location.

## Deep analysis layer

The deep-analysis layer lives in `autonomous_betting_agent/deep_analysis.py`. It blends ARA flags, market movement, data quality, book coverage and independent edge into:

- `ara_deep_score`
- `ara_deep_grade`
- `ara_deep_recommendation`
- `ara_deep_primary_risk`
- `ara_deep_factors`

Deep analysis is still diagnostic. It should not be treated as a final betting signal by itself.

## Best-bet shortlist layer

The final shortlist layer lives in `autonomous_betting_agent/best_bets.py`. It turns enriched rows into stricter final statuses:

- `QUALIFIED_STRONG`
- `QUALIFIED`
- `QUALIFIED_SMALL`
- `WATCH`
- `TRACK_ONLY_NEEDS_MODEL_PROBABILITY`
- `REJECT`

Only `QUALIFIED_STRONG`, `QUALIFIED` and `QUALIFIED_SMALL` should be treated as shortlist candidates. `WATCH`, `TRACK_ONLY_NEEDS_MODEL_PROBABILITY` and `REJECT` are not bet-ready.

Generate a full best-bet ranking and a qualified-only shortlist:

```bash
python generate_best_bets.py "weather_enhanced_predictions.csv"
```

Optional with market movement:

```bash
python generate_best_bets.py "weather_enhanced_predictions.csv" --movement-csv data/latest_market_movement.csv
```

Default outputs:

```text
data/best_bet_ranked.csv
data/best_bet_shortlist.csv
```

Use review mode when you also want `WATCH` and track-only rows in the shortlist output:

```bash
python generate_best_bets.py "weather_enhanced_predictions.csv" --include-watch
```

## Player props layer

The player props layer lives in `autonomous_betting_agent/player_props.py`. It uses market odds as a baseline, then compares the market probability against an independent player probability.

Supported examples include touchdown, home run, goal, shot on goal, assist, hit, strikeout, reception, rushing yards, receiving yards and passing yards.

Score and rank player props from a CSV:

```bash
python tools/run_player_props.py player_props.csv
```

Default outputs:

```text
data/player_props_checked.csv
data/player_props_ranked.csv
```

Use review mode when you also want watch/reject rows:

```bash
python tools/run_player_props.py player_props.csv --include-watch
```

The full workflow is documented in `docs/player_props.md`.

## Prediction review workflow

Use the review CLI when you want checked rows, deduped checked rows and a JSON report from one CSV:

```bash
python tools/run_prediction_review.py "weather_enhanced_predictions.csv"
```

Default outputs:

```text
data/predictions_checked.csv
data/predictions_checked_deduped.csv
data/predictions_review_report.json
```

The full workflow is documented in `docs/prediction_review_workflow.md`.

## WeatherAPI safety

Set a real WeatherAPI key with:

```bash
export WEATHERAPI_KEY="your_real_key"
```

The code rejects placeholder keys such as `your_weatherapi_key_here`, `weatherapi_key`, `your_key_here`, `paste_key_here` and `replace_me`.

Weather output rows include the original query and returned location so location mismatches can be audited. Wrong returned location means the row should be watched or rejected, not trusted.

Weather fetching now defaults to strict location validation. `fetch_weather_snapshot(..., strict_location=True)` raises `WeatherLocationMismatchError` when WeatherAPI resolves the requested query to the wrong city, region or country. Use `strict_location=False` only for debugging.

## Selection policy for higher-quality picks

The selection policy is intentionally stricter than simply taking every favorite. A candidate must survive data-quality, odds, weather, location, book-coverage, draw-risk and independent-edge checks before it can reach the final shortlist.

A higher hit rate is not the same thing as guaranteed profit. Main performance metrics should be ROI, closing-line value, Brier score, log loss and performance by odds bucket.

## Run the Streamlit app

```bash
streamlit run app_streamlit.py
```

The Streamlit app asks each user for a provider access token on the app screen. This means the app owner does not have to store a shared token in Streamlit secrets.

Optional owner fallback: the app can still read `THE_ODDS_API_KEY` from Streamlit secrets or environment variables, but this is not required when each user provides their own token.

If `learned_state.json` exists in the app root, live market probabilities are calibrated from the graded-result learning loop before the favorite is displayed.

## Run tests

```bash
python -m unittest discover -s tests -v
```

GitHub Actions is configured to run the unit test suite on pushes and pull requests to `main` for Python 3.11 and 3.12.

## Current model signals

The baseline supports:

- live market feed scanning
- fuzzy team-name matching
- market-implied no-vig probabilities
- learned probability calibration from graded historical predictions
- likely outcome ranking
- expected-goals scoreline estimation
- scoreline and spread table generation
- ARA/TGRM cycle notes
- Brier score, accuracy and closing-line delta backtesting helpers
- prediction ledger enrichment
- expected-value and edge calculation
- confidence-bucket performance analysis
- sport-specific performance analysis
- individual player prop scoring
- STRONG/WATCH/AVOID filtering to avoid weak picks
- ARA/deep/best-bet shortlist filtering for stricter final review

All inputs are normalized so results remain interpretable. Future sport-specific modules should replace generic signals with validated features for each sport.

## Recommended development path

1. Pick the first sport.
2. Add official schedule and statistics providers.
3. Add injury, lineup and weather providers.
4. Add player-level statistics and depth-chart providers.
5. Add market-provider interfaces with timestamped snapshots.
6. Build historical event storage.
7. Add strict time-aware backtesting that prevents future-data leakage.
8. Tune weights only on training data.
9. Evaluate on untouched historical data.
10. Run prospective tests before making any performance claims.

## Validation standard

No claim of accuracy or profitability should be made until the system is tested on a large untouched historical dataset and then evaluated prospectively. Sports outcomes are uncertain, market prices include margins, and backtests can be misleading if they contain leakage, overfitting or unrealistic execution assumptions.

## License

MIT License
