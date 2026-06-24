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
