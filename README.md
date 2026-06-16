# Autonomous Sports Analytics Agent

[![tests](https://github.com/BoneManTGRM/autonomous-betting-agent/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/BoneManTGRM/autonomous-betting-agent/actions/workflows/tests.yml)

Autonomous Sports Analytics Agent is a proprietary, source-available sports research and prediction-analysis platform built from the ARA/TGRM workflow: test available evidence, detect weak signals, repair the analysis, verify uncertainty, and produce auditable probability reports.

It is designed for sports analysts, market researchers, prediction reviewers, private research groups, influencers, and commercial operators that need a repeatable decision layer instead of manual guesswork.

**Important:** this software does not execute transactions, does not guarantee winners, and does not guarantee returns. It is an analytics and research system. Any real-world decision remains the responsibility of the user.

## Current product structure

The app is organized around a no-password commercial workflow:

```text
Deployment Health -> Scanner Pro -> Pro Predictor -> What Are the Odds -> Odds Lock Pro -> Daily Workflow -> Auto Result Grading -> Public Proof Dashboard -> Learning Memory
```

| Tool | Main job |
| --- | --- |
| **Deployment Health** | Checks integration status, page/file presence, persistent ledger health, proof quality, and action items. |
| **Scanner Pro** | Scans live odds feeds, normalizes markets, ranks market quality, and sends clean rows forward. |
| **Pro Predictor** | Builds model probabilities, applies learned memory, scores agent decisions, and produces prediction-ready rows. |
| **What Are the Odds** | Runs the market/value command board: edge, agent decision, scanner strength, CLV, loss review, sport routing, and lock-ready review. |
| **Odds Lock Pro** | Creates timestamped proof ledgers, client-safe reports, bankroll controls, persistent-ledger saves, and audit-ready proof IDs. |
| **One-Click Daily Workflow** | Takes current/session/uploaded rows, locks qualified rows, optionally saves them, and generates report output in one guided flow. |
| **Auto Result Grading** | Grades the persistent proof ledger from finished-result CSV uploads or an explicit one-click score fetch. |
| **Public Proof Dashboard** | Displays no-login proof metrics, demo mode, proof audit, CLV, result uploads, persistent ledger storage, and report cards. |
| **Buyer Demo Mode** | Shows a polished buyer-ready dashboard with demo locked rows, audit, proof table, and report cards without API keys. |
| **Learning Memory** | Trains durable calibration and pattern memory from finished, graded results. |

Older duplicate scanner, market-finder, league-specific, and legacy self-learning pages were removed or consolidated.

## No-password commercial mode

The app now includes the most valuable platform upgrades without requiring users to log in every time:

1. **Persistent ledger storage** through a local CSV ledger at `data/odds_lock_pro_ledger.csv`.
2. **Auto-grading from finished-result uploads** by `proof_id` or event/pick matching.
3. **Optional explicit score fetch** for one sport key at a time from Auto Result Grading; this runs only when the button is pressed.
4. **Public proof dashboard** for record, ROI, units, pending picks, sport breakdowns, market breakdowns, and client-safe ledgers.
5. **Report-card generator** for Markdown, HTML, and daily copy/paste reports.
6. **Proof audit layer** that checks proof hashes and pre-start lock status.
7. **Proof quality score** for buyer/demo review.
8. **CLV tracking** from locked price vs closing price when closing odds are supplied.
9. **Demo ledger mode** so a buyer can see the dashboard without an API key or real locked picks.
10. **Deployment Health** so the operator can see readiness and blockers before daily use.
11. **One-Click Daily Workflow** so non-technical users can run the daily lock/report process.
12. **Public-safe exports** and private audit exports.

This is not a full password-protected client portal yet. Login, paid accounts, Stripe, and client roles can be added later.

## Recommended daily workflow

1. Open **Deployment Health** and confirm the deployment is usable.
2. Use **Scanner Pro** and/or **Pro Predictor** to create rows.
3. Use **What Are the Odds** for market/value review.
4. Use **One-Click Daily Workflow** to lock qualified rows and generate reports.
5. Save locked rows into the persistent proof ledger.
6. Use **Auto Result Grading** when finished results are available.
7. Use **Public Proof Dashboard** to review public metrics, proof audit, CLV, report cards, and exports.
8. Use **Learning Memory** after results are graded and probabilities/prices are available.

## Data proof rules

The system distinguishes between historical backfill, learning-only rows, result-only rows, future lock-ready rows, and official forward-proof rows.

A future prediction is strongest when it has event name, sport, market type, prediction, model probability, decimal price, bookmaker/odds source, event start time, lock timestamp before event start, proof ID, proof hash, and final result added later.

A row does not count as a public proof row unless it has both `proof_id` and `locked_at_utc`.

A high hit rate alone is not enough. ROI, average price, CLV, book coverage, sample size, duplicate control, and prospective timestamped proof matter more than headline accuracy.

## API and background behavior

The report/dashboard/demo pages do not scan live APIs by themselves.

Auto Result Grading only fetches score data when the user presses the fetch button for a specific sport key. Otherwise, result grading is done from uploaded result CSVs or already available rows.

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
