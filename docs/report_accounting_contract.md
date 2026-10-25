# Report accounting contract

This change is report-only. It does not save, migrate, regrade, or rewrite proof
ledgers or learning histories, and does not change prediction weights or filters.

## Observable rules

- Preserve original accounting input before generic row normalization in
  `report_accounting_input_json`. Repeated report/export enrichment reads this
  same evidence rather than treating a previously generated value as a receipt.
- Recognize canonical `result_status` and existing settlement aliases. Unknown,
  pending and conflicting outcomes are not inferred from profit signs. Conflicting
  accounting is quarantined from report publication and learning readiness.
- Explicit finite net-profit fields (including zero) take precedence. Conflicting
  net-profit aliases or invalid/nonfinite amounts remain unavailable.
- An existing net-profit column containing NaN fails closed, including pandas
  sparse/padded cells: absence cannot be inferred from NaN alone. This reduces
  usable sparse-row coverage but avoids deriving over an invalid receipt.
  A genuinely absent column may support derivation from other explicit evidence.
- `units`, percentages/ROI and `return_units` are not net profit. A generic
  normalizer may still have legacy aliases for other workflows; report accounting
  uses the preserved original inputs and ignores those invented aliases.
- The export verification gate honors `report_accounting_quarantined`; current
  provider price verification cannot override an accounting quarantine.
- No default one-unit wager is assumed. Derivation requires explicit positive
  `actual_stake_units`, `stake_units` or `wagered_stake_units`. A win additionally
  requires valid decimal settlement odds. Recommended/suggested stake is not an
  actual-stake receipt.
- For explicit stakes, gross settlement profit is `stake * (odds - 1)` for a win,
  `-stake` for a loss, and zero for a push/void/cancellation. Explicit nonnegative
  `fees_units` (or its alias `commission_units`) are subtracted only when deriving
  profit, never a second time from explicit net profit. Without fee data, derived
  output is labeled `derived_before_unspecified_fees`, not a verified net receipt.
- A fee-adjusted net loss does not turn a winning selection into a losing result.
  An unexplained positive loss/refund profit or negative win profit requires review.
- Group ROI requires complete finite profit and explicit positive stakes; missing
  amounts are not filled with zero and the denominator is not decision count.
  Aggregate/ratio overflow also makes ROI unavailable. `roi_basis` distinguishes
  missing accounting, explicit net accounting, and estimates before unspecified
  fees; incomplete/unspecified-fee accounting cannot suggest a research promotion.
  The denominator includes all reported settled stakes, including pushes/cancels;
  this is a report return-on-stated-stake convention, not a turnover estimate.

## Verification

`tests/test_report_accounting_contract.py` covers aliases, zero, invalid values,
conflicts, stake/net/gross distinction, fees, repeat enrichment and group ROI.

`python -I -B scripts/report_accounting_runtime_regression.py` exercises actual
`build_report_studio_state` and JSON exports in English and Spanish. It loads real
package/site/user startup hooks without conftest. File writes, subprocesses and
network operations are denied. Known loopback/auth-directory startup probes are
recorded as denied; report data and exports remain in memory.

## Separate recommendations — not implemented here

1. Make offline calibration preserve immutable raw probabilities and accept
   canonical/numeric result aliases without dropping numeric zero losses.
2. Make walk-forward evaluation use decision-time features and result-availability
   timestamps; exclude future closing CLV and deduplicate overlapping test events.
3. Keep market-baseline/heuristic confidence distinct from demonstrated held-out
   model improvement. Phase 3A remains observation-only. No live-weight changes or
   research-to-verified performance promotion is authorized by this report repair.
