# Prospective evidence preparation contract

`autonomous_betting_agent.prospective_evidence` is a pure, non-writing module.
Its v1 JSON schemas accept no unknown fields. JSON duplicate keys, NaN/Infinity,
non-numeric probabilities, ambiguous identities, duplicate selections, future
source availability, started events and stale (>300 second) odds are rejected.
No fields are silently inferred, normalized, deduplicated or filled from results.
Only one raw model version, one baseline version, and one declared event namespace
are accepted per cohort; that declaration still
needs external reconciliation. Multiple selections remain distinct rows but do
not increase the distinct-event count.

## Interfaces

- `preparation_template()` returns an unfilled object with `protocol` and
  `predictions`. No example event or invented result is presented as real data.
- `prepare_packet(input_text)` stamps the current aware local time. Its `now`
  argument is a deterministic test seam, not an input field or UI backdating
  control. It retains UTF-8 `original_input` text verbatim, its SHA256, the exact
  declared protocol and per-row identities bound to the protocol and preparation
  timestamp. The packet hash is content integrity, not a trusted timestamp or
  source authentication. All trust/promotion flags are false.
- `validate_packet(packet)` reconstructs the exact expected envelope and compares
  canonical JSON bytes, including JSON types, original input and every field.
  A fully rehashed fabricated packet can be internally consistent and will still
  remain **UNVERIFIED_SUPPLIED_CLAIMS**.
- `receipt_template(packet)` supplies only the packet/row identity link. All
  result/source/reviewer fields remain blank until actually supplied.
- `review_packet(packet_text, receipts_text)` retains the entire original cohort,
  both original texts, and every indexed receipt/rejection. Receipts must match
  packet, namespace, event, market and selection. They must assert final status,
  exact `win`/`loss`/`void`, source URL and SHA256, observation and verification
  times and settlement explanation. Chronology requires start < result available
  <= source observed <= reviewed <= current review clock. A final-status string
  or time after start does not independently prove the event ended.

Repeated or revised receipts quarantine that selection until independently
reconciled; there is no last-write-wins. Unknown-target receipts are rejected and
retained, not silently dropped. All rows remain unverified. Counts describe
supplied claims only; there is no computed certified win rate, ROI, training,
ledger persistence, network access or model promotion.

Input limits: 1–1000 predictions, at most 3000 receipts, 2 MB preparation/receipt
JSON, 8 MB imported packet JSON. Protocol/text fields are nonempty, no surrounding
whitespace/control characters, max 10,000 characters. Odds are finite decimal
numbers greater than 1; probabilities are original numeric values in [0,1].

This preparation schema is not directly admissible as `offline-learning-v1`.
The preparation timestamp is not a reconstructed historical decision timestamp.
No original decision time, independently verified outcome, or authentic source
availability is invented for export to the evaluator.

## Integration and compatibility

The existing `pages/forward_test_tracker.py` now uses this contract and shared
bilingual navigation/theme. It no longer reconstructs historical snapshots or
labels them official forward proof. The history pane explains the limit and
links to existing Odds Lock; no legacy records/writers/inference are changed.
The separate learning-admission guard, evaluator thresholds, prediction logic,
existing weights and other historical pages are unchanged. Legacy proof labels
elsewhere are not certified by this workflow.

Session results are bound to exact input fingerprints. Any edit hides the old
packet/review; a failed action clears the previous output. Preserve downloaded
originals. This does not prove browser download completion, host-volume
persistence, independent commitment, source authenticity or predictive gains.
