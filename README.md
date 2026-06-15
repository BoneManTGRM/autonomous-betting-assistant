# Autonomous Sports Analytics Agent

[![tests](https://github.com/BoneManTGRM/autonomous-betting-agent/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/BoneManTGRM/autonomous-betting-agent/actions/workflows/tests.yml)

Autonomous Sports Analytics Agent is a proprietary, source-available sports research and prediction-analysis platform built from the ARA/TGRM workflow: test available evidence, detect weak signals, repair the analysis, verify uncertainty, and produce auditable probability reports.

It is designed for sports analysts, market researchers, prediction reviewers, private research groups, and commercial operators that need a repeatable decision layer instead of manual guesswork.

**Important:** this software does not execute transactions, does not guarantee winners, and does not guarantee returns. It is an analytics and research system. Any real-world decision remains the responsibility of the user.

## Current product structure

The app is organized around one clean four-tool workflow:

```text
Scanner Pro -> Pro Predictor -> What Are the Odds -> Learning Memory
```

| Tool | Main job |
| --- | --- |
| **Scanner Pro** | Scans live odds feeds, normalizes markets, ranks market quality, and sends clean rows forward. |
| **Pro Predictor** | Builds model probabilities, applies learned memory, scores agent decisions, and produces prediction-ready rows. |
| **What Are the Odds** | Runs the market/value command board: edge, agent decision, scanner strength, CLV, loss review, sport routing, and lock-ready review. |
| **Learning Memory** | Trains durable calibration and pattern memory from finished, graded results. |

The sidebar intentionally shows only these four core tools. Older duplicate scanner, market-finder, league-specific, and legacy self-learning pages were removed or consolidated.

## Four-tool handoff health

A shared orchestration layer in `autonomous_betting_agent/four_tool_orchestrator.py` checks whether rows are ready to move from one tool to the next.

It reports:

- `status`
- `next_action`
- `handoff_score`
- scanner handoff coverage
- predictor handoff coverage
- value-review handoff coverage
- learning handoff coverage
- playable rows
- lock-ready rows
- resolved rows
- resolved rows with usable probabilities
- missing blockers

The readiness checks understand common aliases. For example, Learning Memory accepts `result_status`, `result`, `outcome`, `win_loss`, or `graded_result` for final results, and accepts `model_probability`, `model_probability_clean`, `probability`, `predicted_probability`, or `confidence_probability` for probability fields.

This prevents result-only rows from being treated as strong training data unless they also contain a usable probability or price-derived probability.

## Core decision layers

The current system includes:

- live odds scanning through The Odds API
- SportsDataIO context where the user key supports it
- WeatherAPI context for weather-relevant events
- scanner strength scoring
- agent decision scoring
- lock-ready candidate detection
- no-vig and implied-probability review
- model-vs-market edge review
- bankroll and drawdown analysis
- closing-line value diagnostics
- loss review and future-rule generation
- sport-specific model routing
- walk-forward validation
- cumulative learning memory
- probability calibration from graded results
- Spanish/English UI support

## Scanner Pro

Scanner Pro is the consolidated market scanner.

It ranks each scanned market using:

- bookmaker depth
- best price availability
- best price vs average price
- price range
- market overround / hold
- market type quality

It outputs fields such as:

- `scanner_strength_score`
- `scanner_strength_tier`
- `scanner_recommendation`
- `scanner_reasons`
- `scanner_book_count_clean`

Scanner Pro saves its latest rows into the app session so Pro Predictor and What Are the Odds can use them without another upload.

## Pro Predictor

Pro Predictor is the main all-sports prediction engine.

It:

- scans selected sports or manual sport keys
- supports team/player filtering
- uses Odds API prices
- adds optional SportsDataIO and WeatherAPI context
- applies built-in learning-memory signals
- builds fused model probabilities
- computes agent decisions
- ranks prediction candidates
- exports a CSV
- saves prediction rows for What Are the Odds

It does not mark a prediction as strong proof unless the proper timestamp and proof fields are present.

## What Are the Odds

What Are the Odds is the market/value command board.

It combines:

- Scanner Pro strength
- Pro Predictor probabilities
- Agent Decision Engine output
- CLV intelligence
- loss review
- walk-forward validation
- sport-specific model routing
- API snapshots
- lock-ready review

The **Best Board** prioritizes rows by:

1. lock-ready status
2. agent score
3. scanner strength
4. model-vs-market edge
5. model probability

## Learning Memory

Learning Memory is the durable training page.

It reviews and trains from graded CSVs with finished results. It separates:

- direct probability rows
- price-implied probability rows
- fallback probability rows
- rows missing results
- rows missing usable probabilities

It writes or updates:

```text
learned_state.json
data/learning_memory_bank.json
data/ara_learning_memory.csv
```

Learning Memory now shows both learning-health and training-handoff readiness. Rows with results but no usable probabilities are flagged as needing probability or price data before serious training.

## Data proof rules

The system distinguishes between:

- historical backfill
- learning-only rows
- result-only rows
- future lock-ready rows
- official forward-proof rows

A future prediction is strongest when it has:

- event name
- sport
- market type
- prediction
- model probability
- decimal price
- bookmaker / odds source
- event start time
- prediction timestamp or lock timestamp before event start
- final result added later

A high hit rate alone is not enough. ROI, average price, CLV, book coverage, sample size, duplicate control, and prospective timestamped proof matter more than headline accuracy.

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

## API keys

The app can read keys from Streamlit secrets, environment variables, or user input fields depending on the page.

Common secret names:

```text
THE_ODDS_API_KEY
ODDS_API_KEY
SPORTSDATAIO_API_KEY
WEATHERAPI_KEY
WEATHER_API_KEY
GITHUB_TOKEN
GH_TOKEN
GITHUB_REPOSITORY
GITHUB_BRANCH
```

`GITHUB_TOKEN` is only needed if Learning Memory should save trained memory files back to GitHub from the deployed app.

## Run tests

```bash
python -m unittest discover -s tests
```

The repository also includes a GitHub Actions workflow for tests, but a green badge or workflow run should be checked directly in GitHub before claiming that a deployment passed.

## CLI examples

Run the sample agent workflow:

```bash
python run_agent.py examples/sample_event.json
```

Write JSON output:

```bash
python run_agent.py examples/sample_event.json --json-output result.json
```

Run with a learned calibration state:

```bash
python run_agent.py examples/sample_event.json --learned-state learned_state.json
```

Train from a graded CSV:

```bash
python learn_from_results.py pro_predictor_updated_win_loss.csv --output learned_state.json
```

Track graded predictions:

```bash
python track_predictions.py pro_predictor_updated_win_loss.csv --ledger-output prediction_ledger_enriched.csv --report-output prediction_report.json
```

## Commercial positioning

This project is intended to become a licensable product, not a free open-source prediction bot. It can support:

- private sports-analysis dashboards
- paid research tools
- white-label prediction-review systems
- client-facing sports analytics reports
- internal research workflows
- custom integrations with odds, weather, injury, lineup, statistics, and player-prop providers
- private deployment, support, and model-tuning packages

The repository is public for limited review and evaluation, but the code is governed by a proprietary evaluation license. Commercial use, resale, sublicensing, hosting, paid access, SaaS deployment, API access, white-label use, competing-product use, model-training use, or monetized derivative use requires written permission from Reparodynamics.

## Limitations

- The system is only as strong as the data supplied to it.
- Short samples can look excellent by luck and should not be sold as proof.
- Fallback probability rows are useful for rough learning, not serious validation.
- Result-only rows are not enough for calibration.
- A model can have a high hit rate and still perform poorly if the prices are too short.
- API outages, missing keys, low quota, unsupported sports, or bad market coverage can reduce output quality.
- This software does not execute transactions or provide guarantees.

## ARA/TGRM lineage

This project is separated from the original ARA repository so the original research agent remains clean. The sports analytics agent keeps the useful architecture pattern:

1. **TEST** the available event data.
2. **DETECT** weak sources, incomplete inputs, and unstable signals.
3. **REPAIR** the analysis by converting evidence into auditable factors.
4. **VERIFY** with confidence, efficiency, calibration, and stability metrics.

The domain target is sports analytics rather than longevity or scientific literature review.
