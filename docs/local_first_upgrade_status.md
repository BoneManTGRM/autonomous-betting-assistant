# Local-First Upgrade Status

This document tracks the local-first commercial agent upgrade for ABA Signal Pro.

## Current status

The repo now includes a local-first foundation that does not require a cloud server.

Implemented:

- Local SQLite proof storage with CSV fallback.
- Official/research/quarantine/client/learning ledger separation.
- Client-safe pick explanations.
- Markdown, HTML, and messenger-ready local report exports.
- Optional local access helper with no-login as the default.
- Proof ID Verification page.
- Local First Admin page.
- Report Studio Local Export page.
- Local Calibration Dashboard page.
- Learning Memory Safety page.
- Local Admin Workflow Guide page.
- Odds Lock Pro now also saves locked rows to LocalStorage after existing persistent/session saves.

## New pages

- `pages/local_first_admin.py`
- `pages/report_studio_local_export.py`
- `pages/proof_id_verification.py`
- `pages/local_calibration_dashboard.py`
- `pages/learning_memory_safety.py`
- `pages/local_admin_workflow_guide.py`

## New modules

- `autonomous_betting_agent/ledger_types.py`
- `autonomous_betting_agent/sqlite_store.py`
- `autonomous_betting_agent/storage.py`
- `autonomous_betting_agent/explanations.py`
- `autonomous_betting_agent/report_exports.py`
- `autonomous_betting_agent/grading_rules.py`
- `autonomous_betting_agent/bankroll.py`
- `autonomous_betting_agent/local_access.py`
- `autonomous_betting_agent/local_calibration.py`

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

## Local storage flow

Odds Lock Pro keeps its existing persistent/session behavior and now also calls `LocalStorage` after locks are published.

Local storage priority:

1. SQLite at `data/aba_signal_pro.sqlite`.
2. CSV fallback under `data/ledgers` if SQLite is unavailable.

## Safe operating flow

1. Run Pro Predictor Volume.
2. Use Odds Lock Pro to create research or official locks.
3. Use Local First Admin to review local row counts and audit events.
4. Use Proof ID Verification to inspect individual proof rows.
5. Use Report Studio Local Export to create local client-ready reports.
6. Use Local Calibration Dashboard after rows are graded.
7. Use Learning Memory Safety before training memory.

## Testing added

- `tests/test_local_first_core.py`
- `tests/test_sqlite_storage.py`
- `tests/test_local_calibration.py`
- `tests/test_local_access.py`

## Caution

This system is for analytics, proof tracking, reporting, and risk review only. It does not execute transactions and does not guarantee wins, returns, or outcomes.
