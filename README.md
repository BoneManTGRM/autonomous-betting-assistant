# ABA Signal Pro

**Powered by Reparodynamics**

[![CI](https://github.com/BoneManTGRM/autonomous-betting-agent/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/BoneManTGRM/autonomous-betting-agent/actions/workflows/ci.yml)

ABA Signal Pro is a proprietary, source-available sports analytics, proof-tracking, and prediction-review platform. It is designed to help operators scan data, review signals, lock proof rows, grade results, export reports, and evaluate calibration.

**Important:** this software does not execute transactions, does not guarantee winners, and does not guarantee returns. It is an analytics and research system. Any real-world decision remains the responsibility of the user.

## Local-first commercial workflow

```text
Pro Predictor Volume -> Odds Lock Pro -> LocalStorage -> Public Proof Dashboard -> Report Studio Local Export -> Calibration -> Learning Safety
```

No cloud server is required for the local-first layer. The app keeps no-login mode as the default and can run locally or on Streamlit.

## Phase 1 Cloud and Subscriber Roadmap

ABA Signal Pro Phase 1 will expand the current local-first proof, grading, bankroll, and report system into a subscriber-ready sports analytics platform.

The goal is to support personalized research reports, sportsbook-specific market review, transparent proof tracking, bankroll-aware risk summaries, and scalable subscriber delivery. This roadmap does not change the core limitation: ABA Signal Pro remains an analytics and research system, does not execute transactions, does not guarantee outcomes, and does not guarantee returns.

### Phase 1 Core Technology Stack

Required APIs:

1. The Odds API
2. SportsDataIO
3. Weather API
4. Supabase
5. Telegram Bot API
6. Mercado Pago API

High-value additions:

7. API-Football
8. NewsAPI
9. X/Twitter API
10. Google Sheets API

### Important Build Rule

Do not add extra APIs, delivery channels, or future-stack services unless explicitly requested.

Phase 1 should not include WhatsApp, OpenAI, Discord, Twilio, Firebase, Airtable, Sportradar, Reddit, Perplexity, Stripe, PayPal, or Wise unless they are moved into a later roadmap phase.

### Phase 1 Objectives

1. Personalized subscriber analytics with individual bankroll profile, risk tolerance profile, preferred sportsbooks, preferred sports, preferred market types, unit sizing preferences, daily/weekly/monthly performance tracking, and custom filters.

2. Multi-sportsbook line review for Caliente, Playdoit, Codere, Bet365 Mexico, Betcris, 1xBet, Betway, RushBet, and Novibet, including best available line, best available price, market inefficiencies, and Closing Line Value review.

3. Advanced analysis engine covering team statistics, player statistics, injuries, suspensions, weather, travel, rest advantages, historical matchups, market movement, and line movement behavior.

4. Research outputs including confidence score from 0 to 100, expected value estimate, edge percentage, fair odds estimate, implied probability, and risk rating.

5. Market intelligence layer using NewsAPI and X/Twitter API to track injury reports, breaking news, lineup announcements, suspensions, coaching changes, and late developments.

6. Subscriber Report Studio for daily reports, weekly reports, sport-specific reports, personalized reports, bankroll reports, risk reports, PDF export, CSV export, Google Sheets export, custom branding, custom backgrounds, and white-label reports.

7. Smart bankroll management covering flat-stake review, Kelly-style calculations, fractional Kelly review, unit sizing, risk exposure, portfolio diversification, and warnings for excessive risk or over-concentration.

8. Learning system stored in Supabase, including every prediction, every result, Closing Line Value, edge calculations, confidence scores, and market conditions.

9. Official performance tracking for wins, losses, pushes, ROI, units won, yield, hit rate, and Closing Line Value, with locked proof reports, public proof dashboards, and subscriber proof dashboards.

10. Telegram delivery for instant alerts, daily reports, weekly reports, high-confidence research alerts, and closing line movement alerts, with subscriber-specific delivery preferences.

11. Mexican market optimization for Liga MX, international soccer, NBA, MLB, NFL, and UFC, with specific review support for Caliente, Playdoit, Codere, Bet365 Mexico, and Betcris.

12. Selection logic requiring positive expected value threshold, verified statistical edge, market confirmation, risk assessment, and supporting analytical evidence. Do not surface a selection solely because a team is favored.

### Ultimate Goal

Create a personalized, data-driven sports analytics platform focused on long-term research quality, sustainable bankroll-aware risk review, accurate grading, continuous learning, sportsbook-specific optimization, professional subscriber experience, transparent performance tracking, and scalable delivery to hundreds of subscribers.

## Main tools and pages

| Tool/page | Main job |
| --- | --- |
| **Pro Predictor Volume** | High-volume scan and ranking workflow using probability, score, Pattern Points, and review fields. |
| **Odds Lock Pro** | Creates research or official locked rows and now also saves to local SQLite/CSV fallback after the existing ledger/session save. |
| **Public Proof Dashboard** | Public-safe proof metrics, proof audit, CLV, report cards, and exports. |
| **Report Studio** | Branded report presentation layer. |
| **Report Studio Local Export** | Local Markdown, print-to-PDF-ready HTML, and messenger-ready report output. |
| **Proof ID Verification** | Local proof ID lookup for proof hash, lock time, event start time, grade, ledger type, and client-safe explanation. |
| **Local First Admin** | Local storage/admin overview, ledger counts, row-level/event-level summaries, audit log, and CSV exports. |
| **Local Calibration Dashboard** | Brier score, expected vs actual win rate, confidence buckets, and odds-band performance from local graded rows. |
| **Local Bankroll Risk** | Conservative risk-management review, stake suggestions, and correlation warnings. |
| **Learning Memory Safety** | Learning-safe row export, import preview, reset/version placeholders, and blocked-row review. |
| **Local License Admin** | Manual local client/license tracking only. No payment processing. |
| **Buyer Demo Local** | Sample buyer walkthrough with no API keys or cloud server. |
| **Local Admin Workflow Guide** | Operator guide for the local-first workflow. |

## Local-first modules

| Module | Purpose |
| --- | --- |
| `autonomous_betting_agent/ledger_types.py` | Separates official, research, all-high-confidence, quarantine, learning-only, and client-facing rows. |
| `autonomous_betting_agent/sqlite_store.py` | Local SQLite proof rows and audit events at `data/aba_signal_pro.sqlite`. |
| `autonomous_betting_agent/storage.py` | SQLite-first storage facade with CSV fallback in `data/ledgers`. |
| `autonomous_betting_agent/explanations.py` | Client-safe pick explanations covering Pattern Points, odds audit, probability, edge, book coverage, and risk. |
| `autonomous_betting_agent/report_exports.py` | Markdown, print-ready HTML, and messenger report exports. |
| `autonomous_betting_agent/grading_rules.py` | Row-level vs event-level result summaries. |
| `autonomous_betting_agent/bankroll.py` | Conservative flat-stake and Kelly-style risk helpers. |
| `autonomous_betting_agent/local_access.py` | Optional local admin/client/demo access with no-login default. |
| `autonomous_betting_agent/local_calibration.py` | Brier score, calibration buckets, and odds-band summaries. |
| `autonomous_betting_agent/market_support.py` | Supported-market review flags, tennis review/block mode, and market hints. |
| `autonomous_betting_agent/correlation.py` | Duplicate proof ID, duplicate event/pick, same-event exposure, and related-market warnings. |
| `autonomous_betting_agent/local_alerts.py` | Structured local alert messages. |
| `autonomous_betting_agent/license_status.py` | Manual local license/client status records. No Stripe dependency. |
| `autonomous_betting_agent/learning_memory_controls.py` | Learning-safe row checks, version placeholder, and reset confirmation helper. |

## 20-update checklist

Complete or locally implemented:

1. Official vs research ledger separation.
2. Local SQLite storage with CSV fallback.
3. Pick explanation engine.
4. Markdown, HTML, messenger, and print-to-PDF-ready report exports.
5. Row-level vs event-level grading helpers and grade-conflict protection in local storage.
6. Optional local admin/client/demo access, disabled by default.
7. Local client delivery helpers.
8. Conservative bankroll/risk helpers and local UI.
9. Correlation and duplicate exposure safeguards.
10. Local calibration dashboard.
11. Learning Memory safety controls with safe placeholders.
12. Market support/review rules.
13. Local proof ID verification page.
14. Local audit log in SQLite storage.
15. Local alert helpers.
16. Expanded test suite.
17. Local buyer demo and workflow guide.
18. Local admin dashboard.
19. Manual license-status placeholder with no payment dependency.
20. README and local-first status documentation.

Local placeholders remain for heavier future work: true generated PDF files, automated payment processing, destructive memory reset, full cooldown/drawdown automation, and advanced team-level correlation modeling.

## Optional local access

No-login mode remains the default.

To enable local access:

```text
ABA_REQUIRE_LOGIN=true
```

Optional local access values:

```text
ABA_ADMIN_NAME
ABA_ADMIN_CODE
ABA_CLIENT_NAME
ABA_CLIENT_CODE
ABA_DEMO_NAME
ABA_DEMO_CODE
```

This does not require OAuth, email verification, cloud auth, or a separate server.

## Print-to-PDF report flow

Use **Report Studio Local Export** to download the print-ready HTML report. Open the HTML file in a browser, then use **Print** or **Save as PDF**. This avoids heavy PDF dependencies and keeps reporting local-first.

## Safe operating flow

1. Run **Pro Predictor Volume** or upload rows.
2. Use **Odds Lock Pro** to create research or official locks.
3. Use **Local First Admin** to review local storage and audit events.
4. Use **Proof ID Verification** to inspect specific proof IDs.
5. Use **Report Studio Local Export** to create client-ready local reports.
6. Use **Local Bankroll Risk** for conservative exposure review.
7. Use **Local Calibration Dashboard** after rows are graded.
8. Use **Learning Memory Safety** before training memory.
9. Use **Local License Admin** for manual license status tracking.
10. Use **Buyer Demo Local** for a no-key buyer walkthrough.

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

## API keys and local settings

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
ABA_REQUIRE_LOGIN
ABA_ADMIN_NAME
ABA_ADMIN_CODE
ABA_CLIENT_NAME
ABA_CLIENT_CODE
ABA_DEMO_NAME
ABA_DEMO_CODE
```

Do not put real API keys, private access codes, secrets, screenshots with secrets, or private CSVs into GitHub.

## Run tests and CI

```bash
python -m compileall autonomous_betting_agent pages tests
python -m pytest tests -q
```

GitHub Actions runs the CI workflow on pushes to `main`, pull requests, and manual `workflow_dispatch` runs.

## More details

See:

```text
docs/local_first_upgrade_status.md
```

## Limitations

- The system is only as strong as the data supplied to it.
- Short samples can look excellent by luck and should not be sold as proof.
- Result-only rows are not enough for calibration.
- A model can have a high hit rate and still perform poorly if the prices are too short.
- Pattern Points are a ranking and review signal, not a guarantee.
- Price audit flags data-quality risk; it does not prove the pick itself is wrong.
- API outages, missing keys, low quota, unsupported sports, or bad market coverage can reduce output quality.
- Local SQLite/CSV storage protects against cloud dependency but is not a replacement for backups.
- This software does not execute transactions or provide guarantees.
