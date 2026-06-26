# ABA Signal Pro

**Powered by Reparodynamics**

[![CI](https://github.com/BoneManTGRM/autonomous-betting-assistant/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/BoneManTGRM/autonomous-betting-assistant/actions/workflows/ci.yml)
[![Sale Readiness](https://github.com/BoneManTGRM/autonomous-betting-assistant/actions/workflows/sale-readiness.yml/badge.svg?branch=main)](https://github.com/BoneManTGRM/autonomous-betting-assistant/actions/workflows/sale-readiness.yml)

ABA Signal Pro is a proprietary, source-available sports analytics, proof-tracking, and prediction-review platform. It helps operators scan data, review signals, lock proof rows, grade results, export reports, evaluate calibration, and safely simulate adaptive repair logic before any live behavior changes.

**Important:** this software does not execute transactions, does not guarantee winners, and does not guarantee returns. It is an analytics and research system. Any real-world decision remains the responsibility of the user.

## Local-first commercial workflow

```text
Pro Predictor Volume -> Odds Lock Pro -> LocalStorage -> Public Proof Dashboard -> Report Studio Local Export -> Calibration -> Learning Safety -> Adaptive Repair Runner
```

No cloud server is required for the local-first layer. The app keeps no-login mode as the default and can run locally or on Streamlit.

## Main tools and pages

| Tool/page | Main job |
| --- | --- |
| **Pro Predictor Volume** | High-volume scan and ranking workflow using probability, score, Pattern Points, and review fields. |
| **Odds Lock Pro** | Creates research or official locked rows and saves to local SQLite/CSV fallback. |
| **Public Proof Dashboard** | Public-safe proof metrics, proof audit, CLV, report cards, and exports. |
| **Report Studio** | Branded report presentation layer. |
| **Report Studio Local Export** | Local Markdown, print-to-PDF-ready HTML, and messenger report output. |
| **Proof ID Verification** | Local proof ID lookup for proof hash, lock time, event start time, grade, ledger type, and client-safe explanation. |
| **Local First Admin** | Local storage/admin overview, ledger counts, row-level/event-level summaries, audit log, and CSV exports. |
| **Local Calibration Dashboard** | Brier score, expected vs actual win rate, confidence buckets, and odds-band performance from local graded rows. |
| **Local Bankroll Risk** | Conservative risk-management review, stake suggestions, and correlation warnings. |
| **Learning Memory Safety** | Learning-safe row export, import preview, reset/version placeholders, and blocked-row review. |
| **Adaptive Repair Simulation** | Dashboard/control page for the internal Adaptive Repair Runner. Simulation-only. |
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
| `autonomous_betting_agent/adaptive_repair_engine.py` | Phase 0-2 graded-list ingestion, row/event separation, duplicate detection, and watchlist-only pattern discovery. |
| `autonomous_betting_agent/adaptive_repair_diagnostics.py` | Data-quality scoring, column coverage, exact duplicate-row detection, same-event review, mixed-event handling, and missing-field examples. |
| `autonomous_betting_agent/adaptive_repair_runner.py` | Compatibility exports for the Phase 3A runner. |
| `autonomous_betting_agent/adaptive_repair_runner_core.py` | Phase 3A internal system-wide runner. Event-triggered, simulation-only, source-adapter based, with persistent scan memory. |
| `autonomous_betting_agent/reparodynamics_doctrine.py` | Single source of truth for the Phase 3A Reparodynamics operating doctrine used by runner reports and dashboard display. |
| `scripts/run_adaptive_repair_simulation.py` | CLI entrypoint for runner scans, CSV simulations, JSON/Markdown output, and optional saved runs. |
| `pages/adaptive_repair_simulation.py` | Streamlit dashboard/control page for the internal runner. Not the main engine. |
| `autonomous_betting_agent/bankroll.py` | Conservative flat-stake and Kelly-style risk helpers. |
| `autonomous_betting_agent/local_access.py` | Optional local admin/client/demo access with no-login default. |
| `autonomous_betting_agent/local_calibration.py` | Brier score, calibration buckets, and odds-band summaries. |
| `autonomous_betting_agent/market_support.py` | Supported-market review flags, tennis review/block mode, and market hints. |
| `autonomous_betting_agent/correlation.py` | Duplicate proof ID, duplicate event/pick, same-event exposure, and related-market warnings. |
| `autonomous_betting_agent/local_alerts.py` | Structured local alert messages. |
| `autonomous_betting_agent/license_status.py` | Manual local license/client status records. No Stripe dependency. |
| `autonomous_betting_agent/learning_memory_controls.py` | Learning-safe row checks, version placeholder, and reset confirmation helper. |

## Reparodynamics Doctrine

Reparodynamics is ABA's operating doctrine of measured self-repair. ABA observes first, diagnoses carefully, preserves data integrity, conserves repair energy, and repairs only after controlled evidence shows a targeted change improves measurable performance without increasing hidden risk.

Reparodynamics means:

- self-awareness without panic
- adaptation without overfitting
- repair without reckless mutation
- learning without live model contamination
- evidence before activation
- targeted repair instead of blind retraining
- repair energy must be conserved
- every future repair must show value before promotion

For this PR:

- Phase 3A is observation-only.
- Pattern candidates are watchlist-only.
- RYE readiness is not RYE activation.
- Shadow Mode readiness is not Shadow Mode activation.
- No live model mutation exists in this PR.
- Reparodynamics is being used here as ABA's operating doctrine, not as a guarantee of outcomes.

## ABA Adaptive Repair Engine

The **ABA Adaptive Repair Engine** is the simulation-first self-repair layer for ABA Signal Pro. It is designed to detect prediction drift, diagnose specific weaknesses, learn from graded files and local system sources, hunt for repeatable patterns, and eventually apply bounded targeted repairs only after validation.

### Phase 0-2 foundation

Phase 0-2 is intentionally conservative:

- **Simulation Gate:** runs a safe report before production repair activation.
- **Graded List Ingestion:** reads graded CSV/export rows and normalizes wins, losses, pushes, voids, cancels, pending, and unknown statuses.
- **Row-level vs Unique-event Protection:** keeps individual pick rows separate from unique games/events so duplicate markets do not inflate game counts.
- **Enhanced Data-Quality Diagnostics:** reports column coverage, exact duplicate rows, missing required fields, same-event mixed outcomes, same-event multi-market exposure, and readiness for later Shadow Mode.

No production repairs are activated in Phase 0-2.

### Phase 3A Adaptive Repair Runner

The **Adaptive Repair Runner** is the real engine. It is not a live repair daemon yet. It is an event-triggered, callable, system-wide scanner that can be called from the CLI, Streamlit page, and future Learning Page or grading hooks.

The page/dashboard is only a control panel for visibility, review, manual upload, and audit control. The runner is where scanning, summarizing, source isolation, watchlist pattern extraction, RYE readiness, Shadow Mode readiness, and persistent simulation memory happen.

In Phase 3A, "watch and learn" means:

- observe available local data sources
- scan uploaded or local rows
- summarize row-level and unique-event performance
- save JSON and Markdown simulation reports
- detect watchlist-only pattern candidates
- prepare future RYE/Shadow readiness

It does **not** mean changing the live model, live picks, confidence, filters, bet tiers, bankroll logic, sportsbook recommendations, or production behavior.

### Runner sources

The runner safely scans sources when available:

- uploaded CSV rows
- local proof ledger
- graded prediction exports
- Learning Page compatible rows
- local CSV ledgers
- existing row/event grading helpers
- Public Proof Dashboard compatible graded rows when present

Unavailable sources are recorded as unavailable. Failed sources are recorded with a safe load error. Partially loaded CSV source folders are recorded as warnings so good rows are preserved while bad files remain visible. One bad source must not crash the whole scan.

### Runner safety state

Every runner report includes:

```text
Repair Mode: OFF
Shadow Mode: OFF
Live Pick Changes: OFF
Learning Impact: Simulation only
TGRM Activation: OFF
Hidden Value Activation: OFF
Confidence Calibration Activation: OFF
Bet Tier Changes: OFF
Production Model Mutation: OFF
```

### RYE and TGRM

- **RYE = Repair Yield per Energy.** It measures useful improvement per unit of cost, risk, complexity, and pick-volume impact.
- **TGRM = Targeted Gradient Repair Mechanism.** It applies small, bounded, reversible repairs only to the part of the system that is drifting or underperforming.

Phase 3A adds **RYE readiness only**. RYE readiness is not RYE activation. Shadow Mode readiness is not Shadow Mode activation. Neither changes the model.

### Pattern candidates

Pattern candidates are watchlist-only in Phase 3A. Candidate types include:

- soccer draw-trap watchlist
- combat round/method volatility watchlist
- low-confidence winner watchlist when confidence exists
- high-confidence failure watchlist when confidence exists
- duplicate-event risk watchlist
- mixed-event risk watchlist
- missing-odds limitation
- missing-closing-odds limitation
- missing-confidence limitation
- missing-start-time limitation
- weak-sample-size limitation

Each candidate must remain `status = watchlist` and `repair_allowed = false`.

### Data-quality rules

Bad data can create bad learning. The Adaptive Repair Engine excludes pushes, voids, canceled picks, pending picks, unknowns, and mixed unique events from pure win/loss rates. It detects duplicate events and keeps row-level and unique-event records separate.

Enhanced diagnostics check:

- result/event/sport column coverage
- odds, closing-odds, confidence, edge, start-time, and market column coverage
- exact duplicate extra rows
- duplicate event names and keys
- same-event mixed outcomes
- same-event multi-market groups
- missing required field examples
- data-quality score and status
- whether later RYE and Shadow Mode readiness may be possible

The data-quality score does **not** activate repairs. It only tells the operator whether the data is strong enough for later readiness checks.

### Current tracker simulation example

The uploaded tracker baseline used for validation remains:

- 81 total rows
- 75 completed win/loss rows
- 55 wins
- 20 losses
- 4 unknown
- 2 void
- 0 duplicate event names found
- Row-level win rate: 73.33%
- Unique-event win rate: 73.33%
- Production repairs active: No

This does not justify a full retrain. It supports only simulation-only and watchlist-only review.

## Running Adaptive Repair scans

Run the internal runner on an uploaded/graded CSV:

```bash
python scripts/run_adaptive_repair_simulation.py path/to/graded_tracker.csv
python scripts/run_adaptive_repair_simulation.py path/to/graded_tracker.csv --json
python scripts/run_adaptive_repair_simulation.py path/to/graded_tracker.csv --output reports/adaptive_repair_report.md
python scripts/run_adaptive_repair_simulation.py path/to/graded_tracker.csv --json --output reports/adaptive_repair_report.json
python scripts/run_adaptive_repair_simulation.py path/to/graded_tracker.csv --save-run
python scripts/run_adaptive_repair_simulation.py path/to/graded_tracker.csv --system-scan
python scripts/run_adaptive_repair_simulation.py path/to/graded_tracker.csv --fail-below-quality 70
```

Run a local system-wide scan without an uploaded CSV:

```bash
python scripts/run_adaptive_repair_simulation.py --system-scan
python scripts/run_adaptive_repair_simulation.py --system-scan --save-run
```

Saved simulation runs are written locally to:

```text
data/adaptive_repair/simulation_runs/
```

Generated simulation runs are ignored by git and should not be committed.

## Streamlit page

Run the app:

```bash
streamlit run streamlit_app.py
```

Open **Adaptive Repair Simulation**. The page can run a system-wide scan, upload a graded CSV for manual simulation, display the Reparodynamics doctrine banner, display source availability, source failures, source warnings, row-level metrics, unique-event metrics, mixed events, duplicate events, data-quality score, column coverage, watchlist-only patterns, RYE readiness, Shadow Mode readiness, saved runs, and downloadable Markdown/JSON reports.

The page is not the main engine. It is the dashboard/control panel for the internal runner.

## Adaptive Repair implementation status

| Stage | Status |
| --- | --- |
| Phase 0: Simulation Gate | Implemented for CSV/export rows with enhanced diagnostics. |
| Phase 1: Graded List Ingestion | Implemented for local CSV/export rows. |
| Phase 2: Row-level vs unique-event tracking | Implemented with duplicate event, duplicate row, mixed outcome, and same-event review reporting. |
| Phase 3A: Internal Adaptive Repair Runner | Implemented as event-triggered, simulation-only, source-adapter based runner with activation-gate reporting and stable watchlist candidate IDs. |
| Phase 3B: Live Learning Page hook | Planned; no direct model mutation. |
| Phase 4: Pattern Library | Planned; current candidates are watchlist-only. |
| Phase 5: Full RYE scoring | Planned; current output is readiness-only. |
| Phase 6: Shadow Mode activation | Planned; current output is readiness-only. |
| Phase 7: Pick tiering / Playability Score | Planned; no bet-tier changes active. |
| Phase 8: Soccer draw-trap detection | Watchlist-only candidate detection. |
| Phase 9: Combat volatility detection | Watchlist-only candidate detection. |
| Phase 10: Hidden Value Score | Planned; not active. |
| Phase 11: Confidence calibration | Planned; not active. |
| Phase 12: TGRM repair activation | Planned; no production activation. |

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
21. ABA Adaptive Repair Engine Phase 0-2 simulation gate, graded-list ingestion, row-level vs unique-event protection, and enhanced data-quality diagnostics.
22. ABA Adaptive Repair Runner Phase 3A with source adapters, persistent simulation memory, watchlist-only candidates, and readiness-only RYE/Shadow checks.
23. Reparodynamics doctrine layer for runner JSON, Markdown reports, dashboard display, and README documentation.
24. Runner polish for schema versioning, activation-gate checks, stable candidate IDs, and partial CSV warning/failure reporting.

Local placeholders remain for heavier future work: true generated PDF files, automated payment processing, destructive memory reset, full cooldown/drawdown automation, advanced team-level correlation modeling, Shadow Mode activation, full RYE scoring, Hidden Value Score activation, confidence calibration activation, and TGRM production repairs.

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
9. Run **Adaptive Repair Simulation** or the CLI runner before trusting new learning or repair candidates.
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

Do not put real API keys, private access codes, secrets, screenshots with secrets, generated simulation runs, or private CSVs into GitHub.

## Run tests and CI

```bash
python -m compileall autonomous_betting_agent pages tests scripts
python -m py_compile autonomous_betting_agent/magazine_api_sources.py autonomous_betting_agent/magazine_live_api_enrichment.py pages/report_studio.py autonomous_betting_agent/adaptive_repair_engine.py autonomous_betting_agent/adaptive_repair_diagnostics.py autonomous_betting_agent/adaptive_repair_runner.py autonomous_betting_agent/adaptive_repair_runner_core.py autonomous_betting_agent/reparodynamics_doctrine.py pages/adaptive_repair_simulation.py
python -m scripts.report_studio_regression_check
python scripts/magazine_autofit_stress_test.py
python -m pytest -q tests/test_adaptive_repair_engine.py tests/test_adaptive_repair_runner.py tests/test_doctrine.py tests/test_runner_polish.py
python -m pytest -q
```
