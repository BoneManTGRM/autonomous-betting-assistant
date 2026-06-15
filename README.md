# Autonomous Betting Agent

[![tests](https://github.com/BoneManTGRM/autonomous-betting-agent/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/BoneManTGRM/autonomous-betting-agent/actions/workflows/tests.yml)

Autonomous Betting Agent is a proprietary, source-available sports research and prediction-analysis platform built from the ARA/TGRM workflow: test the available evidence, detect weak signals, repair the analysis, verify uncertainty, and produce auditable probability reports.

It is designed for serious sports analysts, betting researchers, prediction-market reviewers, private handicapping groups, and commercial operators who need a repeatable decision layer instead of manual guesswork.

**Important:** this software does not place bets, does not guarantee winners, and does not guarantee profit. It is an analytics and research system. Any betting, financial, legal, or commercial decision remains the responsibility of the user.

## Commercial positioning

This project is intended to become a sellable product, not a free open-source betting bot. It can be licensed for:

- private sports-analysis dashboards
- paid research tools
- white-label prediction-review systems
- client-facing sports analytics reports
- internal betting-group research workflows
- custom integrations with odds, weather, injury, lineup, statistics, and player-prop providers
- private deployment, support, and model-tuning packages

The repository is public for limited review and evaluation, but the code is governed by a proprietary evaluation license. Commercial use, resale, sublicensing, hosting, paid access, SaaS deployment, API access, white-label use, competing-product use, AI/model training use, or monetized derivative use requires written permission from Reparodynamics.

## What it does

- estimates win probabilities for two-outcome sports events
- lets each app user paste their own provider access token
- scans live market feeds when a provider token is supplied
- fetches SportsDataIO league data when a SportsDataIO key is supplied
- supports WeatherAPI context checks for weather-relevant events
- ranks the most likely outcome for upcoming games
- estimates likely scorelines such as 1-1 and 2-1
- scores player props such as touchdown, home run, goal, shot on goal, assist, hit, strikeout, reception, rushing yards, receiving yards, and passing yards
- compares model probabilities with no-vig market probabilities
- calculates expected-value diagnostics for later testing
- tracks confidence, evidence strength, uncertainty, and risk flags
- logs a TGRM-style TEST, DETECT, REPAIR, VERIFY cycle
- supports backtesting metrics such as Brier score, accuracy, log loss, ROI, and closing-line value
- learns probability calibration from graded results and applies it to future predictions
- reviews calibration by classification, probability bucket, and sport
- checks a strict 70 percent win-rate goal using win rate, average odds, ROI, CLV, duplicates, and minimum sample-size controls
- filters weak, low-edge, bad-weather, bad-location, low-data, favorite-heavy, or unverified picks before they are counted as recommendations
- includes a CLI, sample event file, Streamlit UI, unit tests, and GitHub Actions test workflow

## ARA/TGRM lineage

This project is separated from the original ARA repository so the original research agent remains clean. The betting agent keeps the useful architecture pattern:

1. **TEST** the available event data.
2. **DETECT** weak sources, incomplete inputs, and unstable signals.
3. **REPAIR** the analysis by converting evidence into auditable factors.
4. **VERIFY** with confidence, efficiency, calibration, and stability metrics.

The domain target is sports analytics rather than longevity or scientific literature review.

## Main components

| Component | Purpose |
| --- | --- |
| Streamlit app | Interactive user interface for predictions, market scans, keys, and review workflows. |
| Market scanner | Reads live market feeds when a provider key is supplied. |
| SportsDataIO layer | Fetches schedule, score, and statistics endpoints available to the user's SportsDataIO account. |
| Weather layer | Adds strict location-aware weather context for weather-relevant games. |
| ARA decision layer | Blocks or watches common failure modes before they become recommendations. |
| Deep-analysis layer | Blends data quality, market movement, independent edge, and ARA flags into a stricter diagnostic score. |
| Best-bet shortlist layer | Separates qualified candidates from WATCH, TRACK_ONLY, and REJECT rows. |
| Player-props layer | Scores player props against independent probability and market-implied probability. |
| Calibration trainer | Learns from graded results and applies probability calibration to future predictions. |
| Review/reporting tools | Produces checked CSV files, deduped files, calibration reports, profit-goal reports, and prediction ledgers. |

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

## Run the Streamlit app

```bash
streamlit run streamlit_app.py
```

If your deployment uses the older entrypoint, run:

```bash
streamlit run app_streamlit.py
```

The app asks each user for their own provider access token on the app screen. This means the app owner does not need to store a shared token in Streamlit secrets.

Optional owner fallback: the app can still read keys such as `THE_ODDS_API_KEY`, `SPORTSDATAIO_API_KEY`, and `WEATHERAPI_KEY` from Streamlit secrets or environment variables when configured.

## Run the sample CLI workflow

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

## Learning and calibration workflow

The learning loop is:

```text
prediction -> final result -> graded CSV -> train calibration -> learned_state.json -> future predictions
```

Train from a graded CSV:

```bash
python learn_from_results.py pro_predictor_updated_win_loss.csv --output learned_state.json
```

The CSV parser accepts common columns such as:

- `probability`, `predicted_probability`, `favorite_probability`, `model_probability`, or `market_probability`
- `result`, `outcome`, `win_loss`, or `graded_result` with values like `won`, `lost`, `1`, or `0`
- optional `prediction` / `pick` and `winner` / `actual_winner` columns

The learned state stores calibration parameters, events trained, Brier score before/after, log loss before/after, and accuracy before/after. If `learned_state.json` exists in the project root, the live market scanner applies it automatically.

This is probability calibration, not proof of edge. It learns whether raw market/model probabilities have been too confident, too cautious, or biased based on past graded predictions. Retrain it whenever more finished games are added.

Review calibration quality by classification, probability bucket, and sport:

```bash
python tools/run_calibration_review.py pro_predictor_updated_win_loss.csv
```

Default output:

```text
data/calibration_review_report.json
```

## Prediction tracking, edge, profit/loss, and CLV

Use the tracker after predictions have been graded:

```bash
python track_predictions.py pro_predictor_updated_win_loss.csv --ledger-output prediction_ledger_enriched.csv --report-output prediction_report.json
```

The tracker accepts flexible CSV columns and enriches each row with:

- predicted winner
- model probability
- calibrated probability
- sportsbook odds
- implied probability
- edge
- expected value
- actual winner
- result
- profit/loss
- closing odds
- closing implied probability
- closing-line value
- confidence bucket
- decision and decision reason
- sport
- bookmaker count

The report summarizes resolved picks, wins/losses/pushes, hit rate, average probabilities, Brier score, log loss, unit profit/loss, ROI, average edge, average closing-line value, and performance by decision, confidence bucket, and sport.

## Profit-goal review

Check whether a tracked CSV meets a stricter high-hit-rate target:

```bash
python tools/run_profit_goal_review.py pro_predictor_updated_win_loss.csv
```

Default output:

```text
data/profit_goal_report.json
```

The goal review checks:

- win-rate target with tolerance
- average odds at or above 1.43
- positive ROI
- positive closing-line value when closing odds are supplied
- no duplicate event/start/pick padding
- minimum finished-pick sample size

A high win rate is not the same thing as profitability. ROI, closing-line value, odds quality, sample size, and prospective performance are more important than a headline percentage.

## SportsDataIO integration

Set your SportsDataIO API key:

```bash
export SPORTSDATAIO_API_KEY="your_key_here"
```

Fetch any SportsDataIO endpoint your account can access:

```bash
python tools/fetch_sportsdataio.py ScoresByDate/2026-JAN-15 --sport nfl --subfeed scores --output data/sportsdataio_nfl_scores.json
```

The SportsDataIO client defaults to header authentication using `Ocp-Apim-Subscription-Key` and also supports query-string auth with `--auth-mode query`.

The full workflow is documented in `docs/sportsdataio.md`.

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

The deep-analysis layer lives in `autonomous_betting_agent/deep_analysis.py`. It blends ARA flags, market movement, data quality, book coverage, and independent edge into:

- `ara_deep_score`
- `ara_deep_grade`
- `ara_deep_recommendation`
- `ara_deep_primary_risk`
- `ara_deep_factors`

Deep analysis is diagnostic. It should not be treated as a final betting signal by itself.

## Best-bet shortlist layer

The final shortlist layer lives in `autonomous_betting_agent/best_bets.py`. It turns enriched rows into stricter final statuses:

- `QUALIFIED_STRONG`
- `QUALIFIED`
- `QUALIFIED_SMALL`
- `WATCH`
- `TRACK_ONLY_NEEDS_MODEL_PROBABILITY`
- `REJECT`

Only `QUALIFIED_STRONG`, `QUALIFIED`, and `QUALIFIED_SMALL` should be treated as shortlist candidates. `WATCH`, `TRACK_ONLY_NEEDS_MODEL_PROBABILITY`, and `REJECT` are not bet-ready.

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

Use review mode when you also want WATCH and track-only rows in the shortlist output:

```bash
python generate_best_bets.py "weather_enhanced_predictions.csv" --include-watch
```

## Player props layer

The player props layer lives in `autonomous_betting_agent/player_props.py`. It uses market odds as a baseline, then compares the market probability against an independent player probability.

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

Use the review CLI when you want checked rows, deduped checked rows, and a JSON report from one CSV:

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

The code rejects placeholder keys such as `your_weatherapi_key_here`, `weatherapi_key`, `your_key_here`, `paste_key_here`, and `replace_me`.

Weather output rows include the original query and returned location so location mismatches can be audited. Wrong returned location means the row should be watched or rejected, not trusted.

Weather fetching defaults to strict location validation. `fetch_weather_snapshot(..., strict_location=True)` raises `WeatherLocationMismatchError` when WeatherAPI resolves the requested query to the wrong city, region, or country. Use `strict_location=False` only for debugging.

## Run tests

```bash
python -m unittest discover -s tests -v
```

GitHub Actions is configured to run the unit test suite on pushes and pull requests to `main` for Python 3.11 and 3.12.

## Validation standard

No claim of accuracy or profitability should be made until the system is tested on a large untouched historical dataset and then evaluated prospectively. Sports outcomes are uncertain, market prices include margins, and backtests can be misleading if they contain leakage, overfitting, survivorship bias, cherry-picked samples, duplicate padding, or unrealistic execution assumptions.

The safest commercial claim is that the system provides repeatable sports research, structured decision review, probability tracking, and audit-ready reporting. Performance claims should be made only after independent testing.

## License

This repository is governed by the **Reparodynamics Proprietary Evaluation License v1.1** in `LICENSE`.

Summary:

- this is proprietary, source-available software, not open-source software
- source visibility is allowed only for limited private evaluation
- commercial use requires a signed written agreement from Reparodynamics
- resale, sublicensing, redistribution, hosting, paid access, SaaS use, API access, white-label use, managed-service use, and monetized derivatives are prohibited without written permission
- competing-product use is prohibited without written permission
- AI/model training, scraping, dataset creation, benchmarking, fine-tuning, distillation, or automated extraction using this software is prohibited without written permission
- users must bring their own third-party API keys and comply with third-party provider terms
- the software is provided as-is with no guarantee of accuracy, legality, availability, winners, or profit

Earlier public versions may have been distributed under different terms, including MIT. The current license governs versions distributed with the current `LICENSE` file and future updates unless a signed written agreement states otherwise.

For commercial licensing, private deployment, custom integrations, resale rights, or white-label discussions, contact Reparodynamics / BoneManTGRM through the repository owner account.
