# Autonomous Sports Analytics Agent

[![tests](https://github.com/BoneManTGRM/autonomous-betting-agent/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/BoneManTGRM/autonomous-betting-agent/actions/workflows/tests.yml)

Autonomous Sports Analytics Agent is a proprietary, source-available sports research and prediction-analysis platform built from the ARA/TGRM workflow: test available evidence, detect weak signals, repair the analysis, verify uncertainty, and produce auditable probability reports.

It is designed for sports analysts, market researchers, prediction reviewers, private research groups, influencers, and commercial operators that need a repeatable decision layer instead of manual guesswork.

**Important:** this software does not execute transactions, does not guarantee winners, and does not guarantee returns. It is an analytics and research system. Any real-world decision remains the responsibility of the user.

## Current product structure

The app is organized around a commercial no-password workflow:

```text
Scanner Pro -> Pro Predictor -> What Are the Odds -> Odds Lock Pro -> Public Proof Dashboard -> Learning Memory
```

| Tool | Main job |
| --- | --- |
| **Scanner Pro** | Scans live odds feeds, normalizes markets, ranks market quality, and sends clean rows forward. |
| **Pro Predictor** | Builds model probabilities, applies learned memory, scores agent decisions, and produces prediction-ready rows. |
| **What Are the Odds** | Runs the market/value command board: edge, agent decision, scanner strength, CLV, loss review, sport routing, and lock-ready review. |
| **Odds Lock Pro** | Creates timestamped proof ledgers, client-safe reports, bankroll controls, persistent-ledger saves, and audit-ready proof IDs. |
| **Public Proof Dashboard** | Displays no-login proof metrics, demo mode, proof audit, CLV, result uploads, persistent ledger storage, and report cards. |
| **Learning Memory** | Trains durable calibration and pattern memory from finished, graded results. |

Older duplicate scanner, market-finder, league-specific, and legacy self-learning pages were removed or consolidated.

## No-password commercial mode

The app now includes the most valuable platform upgrades without requiring users to log in every time:

1. **Persistent ledger storage** through a local CSV ledger at `data/odds_lock_pro_ledger.csv`.
2. **Auto-grading from finished-result uploads** by `proof_id` or event/pick matching.
3. **Public proof dashboard** for record, ROI, units, pending picks, sport breakdowns, market breakdowns, and client-safe ledgers.
4. **Report-card generator** for Markdown, HTML, and daily copy/paste reports.
5. **Proof audit layer** that checks proof hashes and pre-start lock status.
6. **Proof quality score** for buyer/demo review.
7. **CLV tracking** from locked price vs closing price when closing odds are supplied.
8. **Demo ledger mode** so a buyer can see the dashboard without an API key or real locked picks.
9. **Direct save from Odds Lock Pro** into the persistent proof ledger.
10. **Public-safe exports** and private audit exports.

This is not a full password-protected client portal yet. Login, paid accounts, Stripe, and client roles can be added later.

## Influencer and private-group workflow

For a serious sports creator, research group, or private analyst, the valuable workflow is not only prediction. It is proof, repeatability, and reporting.

The recommended operating path is:

1. **Scanner Pro** finds and ranks markets.
2. **Pro Predictor** builds probability and decision rows.
3. **What Are the Odds** reviews value, edge, CLV, risk, and lock readiness.
4. **Odds Lock Pro** locks qualified future picks into a timestamped proof ledger.
5. **Odds Lock Pro** saves locked rows into the persistent proof ledger.
6. **Public Proof Dashboard** publishes client-safe performance, proof audit, report cards, and exports.
7. Finished results are graded manually or through result-upload matching.
8. **Learning Memory** retrains calibration from finished results with usable probabilities or prices.

This structure helps separate live research, official locked picks, public-facing reports, audit proof, and learning data.

## Odds Lock Pro

Odds Lock Pro is the trust/proof layer.

It adds:

- timestamped locked pick ledger
- unique `proof_id`
- SHA-256 `proof_hash`
- pre-start lock-status check
- model probability vs implied probability edge
- recommended stake units
- fractional Kelly-style risk sizing with caps
- proof quality visibility
- direct persistent-ledger saving
- public/client-safe view
- private audit view
- daily copy/paste report generator
- Spanish/English reports
- sport and market performance dashboard
- bankroll exposure dashboard
- daily exposure limit checks
- per-sport exposure limit checks

The public/client view hides internal fields such as full model probability, proof hash, private scoring, and internal diagnostics while keeping useful proof fields such as event, pick, price, confidence, result, units, and proof ID.

## Public Proof Dashboard

The Public Proof Dashboard does **not** call sports APIs. It uses locked rows from session, uploaded ledgers, the persistent CSV ledger, or demo rows.

It supports:

- loading the persistent ledger
- loading Odds Lock Pro session rows
- uploading locked ledger CSVs
- demo ledger mode
- uploading finished-result CSVs
- applying result updates by `proof_id`
- applying result updates by event/pick fallback matching
- saving the merged ledger back to `data/odds_lock_pro_ledger.csv`
- requiring `proof_id` and `locked_at_utc` before any row counts as proof
- ignoring raw/non-proof prediction rows
- proof hash audit
- pre-start lock audit
- proof quality score
- CLV and beat-close tracking when closing odds are supplied
- sport/market/result filters
- exporting public proof CSVs
- exporting private audit CSVs
- exporting proof audit CSVs
- generating Markdown report cards
- generating HTML report cards
- generating daily copy/paste reports

## Four-tool handoff health

A shared orchestration layer in `autonomous_betting_agent/four_tool_orchestrator.py` checks whether rows are ready to move from one tool to the next.

It reports status, next action, handoff score, scanner coverage, predictor coverage, value-review coverage, learning coverage, playable rows, lock-ready rows, resolved rows, resolved rows with usable probabilities, and missing blockers.

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
- timestamped proof ledger generation
- persistent no-password ledger storage
- finished-result upload grading
- proof hash audit
- proof quality scoring
- CLV and beat-close tracking
- public/private client reporting
- no-vig and implied-probability review
- model-vs-market edge review
- bankroll and drawdown analysis
- exposure limits and stake sizing
- closing-line value diagnostics
- loss review and future-rule generation
- sport-specific model routing
- walk-forward validation
- cumulative learning memory
- probability calibration from graded results
- Spanish/English UI support

## Data proof rules

The system distinguishes between historical backfill, learning-only rows, result-only rows, future lock-ready rows, and official forward-proof rows.

A future prediction is strongest when it has event name, sport, market type, prediction, model probability, decimal price, bookmaker/odds source, event start time, lock timestamp before event start, proof ID, proof hash, and final result added later.

A row does not count as a public proof row unless it has both `proof_id` and `locked_at_utc`.

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

Do not put real API keys in GitHub, README files, screenshots, or public CSVs.

## Run tests

```bash
python -m unittest discover -s tests
```

The repository also includes a GitHub Actions workflow for tests, but a green badge or workflow run should be checked directly in GitHub before claiming that a deployment passed.

## Commercial positioning

This project is intended to become a licensable product, not a free open-source prediction bot. It can support private sports-analysis dashboards, paid research tools, white-label prediction-review systems, client-facing sports analytics reports, internal research workflows, custom API integrations, private deployment, support, and model-tuning packages.

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
