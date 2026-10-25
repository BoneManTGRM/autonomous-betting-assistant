# Learning intake: observation-only evidence review

## Intentional behavior change

The Learning Memory page, Auto Learning Cycle entry point, learning actions in
Pro Predictor/result-sync, and `learn_from_results.py` now review evidence only.
They do not fit calibrators, rebuild patterns, prune/replace historical memory,
write learning artifacts, or publish to GitHub. Legacy tuning flags, including
`min_new_rows=1`, `min_total_rows=5`, and `save_to_github=True`, cannot enable
training. The CLI accepts `--output` only to report the requested path; its JSON
explicitly says `REVIEW_ONLY_NOT_TRAINED` and `output_written: false`.

This disables the former training action; it is not a claim that a model was
improved or a trained replacement file was produced. UI labels say review in
English and Spanish. Existing result-sync behavior remains distinct: it can
still update its ledger; its subsequent **learning review** cannot write learned
artifacts. Unrelated application startup/profile hooks are not covered by this
no-learning-write guarantee.

## Admission and trust boundary

`learning_evidence_admission.py` reuses the existing `offline-learning-v1`
observation validator and exact canonical grade logic. It requires original
pre-event probabilities and model versions, event/market/selection identity,
chronology, source provenance and an explicit unambiguous final result. It
rejects missing evidence, unverified outcomes, pending/conditional/conflicting
grades, known identity mismatches and unresolved review markers. Confidence
labels and odds do not create historical model probabilities.

Every loaded original record and its indexed reason remains in the report.
Conflicting/rejected event members quarantine that event; duplicates do not
inflate unique-event counts. A rejected batch is not silently reduced to a
favorable subset. Compact previews retain a deep copy of all original evidence.
Their versioned envelope must have exactly the emitted canonical shape and
values; missing, unknown, nested or changed outer assertions fail review rather
than overriding or disappearing. The intake filename is not verification; the
envelope uses a fixed review marker and keeps source claims in raw evidence.
CSV parsing rejects
duplicate/blank headers, malformed widths and invalid UTF-8 rather than losing
or replacing evidence. JSON sources and embedded JSON reject duplicate keys and
non-finite literals instead of last-key-wins selection. No timestamps, IDs,
versions or verification receipts
are manufactured for old records.

**A supplied boolean, URL or well-formed receipt is not independently verified
proof.** All reports carry `UNVERIFIED_SUPPLIED_CLAIMS` and
`independently_verified: false`. Structural readiness only means the supplied
claims can proceed to independent verification/offline review. Even complete
or forged-but-well-formed claims always retain `trained: false`,
`artifacts_written: false`, `live_mutation_allowed: false`,
`promotion_allowed: false`, and `predictive_gain_proven: false`. No new
promotion mechanism is provided. The existing minimum of 50 distinct admitted
events and outcome diversity cannot be lowered by legacy flags; an untouched
holdout experiment is still required and is not run by these entry points.

## Coverage and preservation

Automatic review reads raw local workspace ledger CSV and both local proof-held
JSON/backup snapshots, plus the existing compact-memory records. It deliberately
does not call normalizing/deduplicating ledger loaders, storage constructors,
remote GitHub fetches or cache updates. Remote-only, session-only and SQLite-only
records are explicitly outside this review. Source parse/read errors are
reported and block readiness. No original ledger or learned artifact is
rewritten, even when its records fail admission.

## Unchanged paths and remaining risks

- `learning.py`, `live_odds.py` and `adaptive_learning.py` saved-weight loading
  and inference behavior are unchanged. Already-saved weights/patterns can
  therefore still influence predictions, and their legacy provenance is **not
  certified** by this patch. Disabling/replacing them requires a separate,
  explicit inference decision and validation—not a silent filtered retrain.
- Optional-history bucket calibration (`accuracy_calibration.py`, its CLI,
  pipeline callers and walk-forward tooling) is not changed in this slice.
  Its canonical-grade-only provenance gap remains. Gating that path would
  change computed `calibrated_probability`; zero admissible history should
  preserve raw probability and report calibration unavailable in a separately
  reviewed patch, rather than use a manufactured replacement estimate.
- Pure fitting/serialization primitives remain available to explicit library
  callers. This is an intake-entry-point boundary, not a claim that every
  possible invocation of every model helper is globally disabled.

All implementation verification uses isolated synthetic records and synthetic
saved-state fixtures. No actual history, learned weights, training cycle or
provider request is run as part of this work.
