# ABA Signal Pro

**Powered by Reparodynamics**

[![CI](https://github.com/BoneManTGRM/autonomous-betting-assistant/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/BoneManTGRM/autonomous-betting-assistant/actions/workflows/ci.yml)
[![Sale Readiness](https://github.com/BoneManTGRM/autonomous-betting-assistant/actions/workflows/sale-readiness.yml/badge.svg?branch=main)](https://github.com/BoneManTGRM/autonomous-betting-assistant/actions/workflows/sale-readiness.yml)

ABA Signal Pro is a proprietary, source-available sports analytics, proof-tracking, and prediction-review platform. It is designed to help operators scan data, review signals, lock proof rows, grade results, export reports, evaluate calibration, and safely simulate adaptive repair logic before any live behavior changes.

**Important:** this software does not execute transactions, does not guarantee winners, and does not guarantee returns. It is an analytics and research system. Any real-world decision remains the responsibility of the user.

## Local-first commercial workflow

```text
Pro Predictor Volume -> Odds Lock Pro -> LocalStorage -> Public Proof Dashboard -> Report Studio Local Export -> Calibration -> Learning Safety -> Adaptive Repair Simulation
```

No cloud server is required for the local-first layer. The app keeps no-login mode as the default and can run locally or on Streamlit.

## Current sale-readiness gates

The repository now has two buyer-facing validation layers:

1. `CI` runs compile checks and the full unit-test suite.
2. `Sale Readiness` runs the critical magazine/report checks required for the API-enriched Full Pick Magazine flow:
   - `python -m py_compile autonomous_betting_agent/magazine_api_sources.py autonomous_betting_agent/magazine_live_api_enrichment.py pages/report_studio.py`
   - `python -m pytest -q tests/test_magazine_api_sources_display.py`
   - `python -m scripts.report_studio_regression_check`
   - `python scripts/magazine_autofit_stress_test.py`
   - `python -m pytest -q`

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
| **ABA Adaptive Repair Simulation** | Phase 0-2 simulation gate for graded-list ingestion, row-level vs unique-event protection, duplicate detection, and watchlist-only pattern discovery. |
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
| `autonomous_betting_agent/adaptive_repair_engine.py` | Simulation-first Adaptive Repair Engine Phase 0-2 helpers for graded-list ingestion, row/event separation, duplicate detection, and safe watchlist-only pattern discovery. |
| `scripts/run_adaptive_repair_simulation.py` | CLI entrypoint for running an Adaptive Repair simulation on a graded CSV/export file. |
| `autonomous_betting_agent/bankroll.py` | Conservative flat-stake and Kelly-style risk helpers. |
| `autonomous_betting_agent/local_access.py` | Optional local admin/client/demo access with no-login default. |
| `autonomous_betting_agent/local_calibration.py` | Brier score, calibration buckets, and odds-band summaries. |
| `autonomous_betting_agent/market_support.py` | Supported-market review flags, tennis review/block mode, and market hints. |
| `autonomous_betting_agent/correlation.py` | Duplicate proof ID, duplicate event/pick, same-event exposure, and related-market warnings. |
| `autonomous_betting_agent/local_alerts.py` | Structured local alert messages. |
| `autonomous_betting_agent/license_status.py` | Manual local license/client status records. No Stripe dependency. |
| `autonomous_betting_agent/learning_memory_controls.py` | Learning-safe row checks, version placeholder, and reset confirmation helper. |

## ABA Adaptive Repair Engine

The **ABA Adaptive Repair Engine** is the simulation-first self-repair layer for ABA Signal Pro. It is designed to detect prediction drift, diagnose specific weaknesses, learn from graded files and the Learning Page, hunt for repeatable patterns, and eventually apply bounded targeted repairs only after validation.

Phase 0-2 is now intentionally conservative:

- **Simulation Gate:** runs a safe report before production repair activation.
- **Graded List Ingestion:** reads graded CSV/export rows and normalizes wins, losses, pushes, voids, cancels, pending, and unknown statuses.
- **Row-level vs Unique-event Protection:** keeps individual pick rows separate from unique games/events so duplicate markets do not inflate game counts.

No production repairs are activated in Phase 0-2. Candidate patterns are watchlist-only until later Shadow Mode and RYE validation exist.

### RYE and TGRM

- **RYE = Repair Yield per Energy.** It measures useful improvement per unit of cost, risk, complexity, and pick-volume impact.
- **TGRM = Targeted Gradient Repair Mechanism.** It applies small, bounded, reversible repairs only to the part of the system that is drifting or underperforming.

Current Phase 0-2 implementation does not activate TGRM repairs. It prepares safe simulation data for future RYE/TGRM scoring.

### Data-quality rules

Bad data can create bad learning. The Adaptive Repair Engine must exclude pushes, voids, canceled picks, pending picks, and unknowns from win/loss rates. It must detect duplicate events and keep row-level and unique-event records separate.

### Current tracker simulation example

The uploaded tracker baseline used for Phase 0-2 validation produced:

- 81 total rows
- 75 completed win/loss rows
- 55 wins
- 20 losses
- 4 unknown
- 2 void
- 0 duplicate event names found
- Row-level win rate: 73.33%
- Unique-event win rate: 73.33%

This does not justify a full retrain because the system is performing well overall. It supports only targeted watchlist patterns such as soccer draw-trap detection and combat pick volatility detection.

### Run an Adaptive Repair simulation

```bash
python scripts/run_adaptive_repair_simulation.py path/to/graded_tracker.csv
python scripts/run_adaptive_repair_simulation.py path/to/graded_tracker.csv --json
```

## Adaptive Repair implementation status

| Stage | Status |
| --- | --- |
| Phase 0: Simulation Gate | Implemented for CSV/export rows. |
| Phase 1: Graded List Ingestion | Implemented for local CSV/export rows. |
| Phase 2: Row-level vs unique-event tracking | Implemented with duplicate event reporting. |
| Phase 3: Learning Page integration | Planned. |
| Phase 4: Pattern Library | Planned. |
| Phase 5: RYE scoring | Planned. |
| Phase 6: Shadow Mode | Planned. |
| Phase 7: Pick tiering / Playability Score | Planned. |
| Phase 8: Soccer draw-trap detection | Watchlist-only candidate detection. |
| Phase 9: Combat volatility detection | Watchlist-only candidate detection. |
| Phase 10: Hidden Value Score | Planned. |
| Phase 11: Confidence calibration | Planned. |
| Phase 12: TGRM repair activation | Planned; no production activation yet. |
| Phase 13: Admin dashboard upgrades | Planned. |
| Phase 14: Report generator upgrades | Planned. |
| Phase 15: README documentation update | Implemented for Phase 0-2. |

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
21. ABA Adaptive Repair Engine Phase 0-2 simulation gate, graded-list ingestion, and row-level vs unique-event protection.

Local placeholders remain for heavier future work: true generated PDF files, automated payment processing, destructive memory reset, full cooldown/drawdown automation, advanced team-level correlation modeling, Shadow Mode repair activation, full RYE scoring, Hidden Value Score activation, and TGRM production repairs.

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
9. Run **ABA Adaptive Repair Simulation** on graded exports before trusting new learning or repair candidates.
10. Use **Local License Admin** for manual license status tracking.
11. Use **Buyer Demo Local** for a no-key buyer walkthrough.

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
python -m py_compile autonomous_betting_agent/magazine_api_sources.py autonomous_betting_agent/magazine_live_api_enrichment.py pages/report_studio.py autonomous_betting_agent/adaptive_repair_engine.py
python -m scripts.report_studio_regression_check
python scripts/magazine_autofit_stress_test.py
python -m pytest -q tests/test_adaptive_repair_engine.py
python -m pytest -q
```
