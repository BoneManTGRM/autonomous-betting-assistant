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
| **Reparodynamics** | Phase 3A doctrine and real audit-log visibility. Observation-only. |
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
| `autonomous_betting_agent/reparodynamics_audit.py` | Phase 3A audit-log event builder and persistence for Learning Page uploads and Adaptive Repair scans. |
| `scripts/run_adaptive_repair_simulation.py` | CLI entrypoint for runner scans, CSV simulations, JSON/Markdown output, and optional saved runs. |
| `pages/adaptive_repair_simulation.py` | Streamlit dashboard/control page for the internal runner. Not the main engine. |
| `pages/reparodynamics.py` | Streamlit doctrine and audit-log visibility page. Shows real run data or “No run recorded yet.” |
| `autonomous_betting_agent/bankroll.py` | Conservative flat-stake and Kelly-style risk helpers. |
| `autonomous_betting_agent/local_access.py` | Optional local admin/client/demo access with no-login default. |
| `autonomous_betting_agent/local_calibration.py` | Brier score, calibration buckets, and odds-band summaries. |
| `autonomous_betting_agent/market_support.py` | Supported-market review flags, tennis review/block mode, and market hints. |
| `autonomous_betting_agent/correlation.py` | Duplicate proof ID, duplicate event/pick, same-event exposure, and related-market warnings. |
| `autonomous_betting_agent/local_alerts.py` | Structured local alert messages. |
| `autonomous_betting_agent/license_status.py` | Manual local license/client status records. No Stripe dependency. |
| `autonomous_betting_agent/learning_memory_controls.py` | Learning-safe row checks, version placeholder, and reset confirmation helper. |

## Reparodynamics Phase 3A audit mode

Current mode: **observation-only**.

Direct prediction improvement: **0%**. Phase 3A does not change live picks, confidence, bet tiers, bankroll sizing, sportsbook recommendations, filters, or model weights.

Purpose:

- write an audit event when a Learning Page graded upload or Adaptive Repair scan is processed
- count total pick rows separately from unique events
- detect duplicate-event pressure from row-level vs unique-event differences
- surface observation-only drift signals
- count watchlist-only pattern and repair candidates
- explain why every candidate remains blocked

Expected future benefit after validation: **5–20% improvement in calibration, drift resistance, and learning quality**. That future range requires simulation evidence and Shadow Mode comparison against historical graded data.

Live mutation remains **forbidden** until simulation and Shadow Mode prove measurable improvement without adding hidden risk.

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
