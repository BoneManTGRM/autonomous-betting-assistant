# Audit Method

## Purpose

The audit layer exists to make prediction performance measurable and harder to misrepresent.

## Core rules

- Every pick should have a timestamp before the event.
- Every pick should preserve the event, market, selection, model probability, odds, and source.
- Results should be graded as win, loss, void, pending, or review_needed.
- Rows requiring manual review should not be counted as official performance until resolved.
- Duplicates should be excluded from official performance.

## Proof Ledger

The Proof Ledger stores enriched prediction rows with:

- `prediction_id`
- `prediction_timestamp`
- `event`
- `prediction`
- `model_probability`
- `decimal_price`
- `confidence_tier`
- `result_status`
- `profit_units`
- `previous_hash`
- `row_hash`

## Hash-chain verification

Each row hash is computed from the row contents, including the previous hash. If any earlier row changes, the row hash check fails. This is tamper-evident, not tamper-proof. It is local proof, not blockchain notarization.

## Official metrics

Official performance should focus on:

- clean wins
- clean losses
- voids excluded from win rate
- review_needed excluded until resolved
- ROI calculated only where odds and stake are known

## Important limitation

High win rate alone is not enough. Positive ROI after actual odds is the key metric.
