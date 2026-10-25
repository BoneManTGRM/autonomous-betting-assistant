# Offline learning validation: evidence before activation

## What this adds—and does not add

This is an isolated, **observation-only** experiment runner. It reads an explicitly
provided JSON file and prints a report. It does not discover or train on existing
ledgers, change saved learning state, alter live predictions, place bets, call a
provider, install dependencies, or promote a model. It does not write files.

`live_mutation_allowed`, `promotion_allowed`, and `predictive_gain_proven` are
always `false`, including for a `REVIEW_CANDIDATE` report. That status means only
that the supplied data passed the local experimental checks. Independently
verified source records and a genuinely untouched prospective evaluation are
still required. **Synthetic test success is software-correctness evidence, not
an improvement in prediction accuracy or profitability.**

The first candidate is intentionally simple: fixed, regularized, intercept-only
logistic calibration of immutable raw probabilities. Each event has total
training weight one, regardless of its number of selections. The intercept is
fitted only from eligible training data, bounded to [-2, 2], with fixed L2
strength 1.0. No feature search, hyperparameter search, development tuning, or
holdout feedback occurs. Audited context fields are not fitted by this version.

The existing Phase 3 gates, model settings and README doctrine are unchanged.
The legacy `learning.py` interleaved cross-validation, compact learning-memory
exports, and `walk_forward_backtest.py` are **not temporal validation evidence**
and are not called by this runner. Their separate limitations remain unresolved.
In particular, old compact records do not retain sufficient temporal provenance;
do not manufacture missing timestamps or relabel questionable history to admit it.

## Minimum input contract

The input is a JSON array. Each row must contain:

| Field | Requirement |
|---|---|
| `event_id` | Stable, independently reconciled event identity; not a display-name guess |
| `selection_id` | Stable selection identity within the event and market |
| `market_id` | Immutable market identity including period, line and settlement rules |
| `sport`, `market_type` | Explicit sport and market family |
| `decision_time` | Actual prediction decision time, ISO timestamp with timezone |
| `prediction_recorded_at` | When the immutable prediction was recorded; no later than decision time |
| `event_start` | Verified start; strictly after decision time |
| `result_available_at` | When the final outcome became available; no earlier than event start |
| `verified_at` | When the final grade was independently verified; no earlier than availability |
| `outcome_verified` | JSON `true`; a string such as `"true"` is not accepted |
| `result_status` | Exact final win/loss (numeric 1/0 and recognized exact aliases supported) |
| `raw_model_probability`, `baseline_probability` | Explicit finite decimals in [0,1]; never derived from confidence words or odds |
| `raw_probability_available_at`, `baseline_probability_available_at` | Both no later than decision time |
| `raw_model_version`, `baseline_model_version` | One frozen raw-model version and one frozen incumbent version per experiment |
| `event_source`, `prediction_source`, `result_source` | References to independent evidence; nonempty strings are necessary but not proof of authenticity |
| `features` | Optional allowlisted context object, with value, availability time and source for every feature |

All timestamps require an explicit timezone. Missing, malformed, naive, future,
conflicting or conditional records are rejected with reasons. Multiple supplied
grade fields must agree, including normalized aliases. The CLI rejects duplicate
JSON object keys before parsing records; last-write-wins cannot hide conflicting
grades, verification flags or timestamps. Pushes, voids, cancellations and unresolved grades are
excluded from this binary calibration experiment, not converted to losses.

The runner does not fetch or authenticate evidence references. An operator must
independently establish correct opponents, selection, market/rules, locked
prediction, result, and timestamp authenticity before interpreting a real-data
report. An `outcome_verified: true` claim alone does not certify a result.

### Context availability

Only the following feature names are admitted. Each uses the object shape:

```json
{"rest_days": {"value": 2, "available_at": "2026-01-01T10:00:00Z", "source": "verified-reference"}}
```

Features must be known at decision time and within their fixed maximum age:

- 1 hour: `source_disagreement`, `weather_wind_kph`
- 6 hours: `injury_count`, `lineup_confirmed`, `expected_minutes`
- 24 hours: `rest_days`, `travel_distance_km`, `starter_rating`, `bullpen_workload`, `short_notice_days`
- 7 days: `recent_form`, `opponent_strength`, `pace`, `surface_rating`, `weight_class`

These are conservative engineering defaults, not empirically validated feature
lifetimes or predictive effects. Domain validation is required before using a
feature in a future model. Closing CLV, closing odds, grades, winners and profits
are not decision features. Extra top-level fields are never copied into the
candidate's decision view. Unknown feature names fail closed.

### Optional market benchmark

`market_snapshot` may provide a complete `moneyline_2way` (home/away),
`moneyline_3way` (home/draw/away), or `total_2way` (over/under) market.
The snapshot and every quote must agree on event, market, bookmaker, snapshot ID
and availability timestamp. The timestamp must precede decision time by no more
than five minutes. Decimal prices must be finite and greater than one.

Example shape:

```json
{
  "event_id": "event-1", "market_id": "full-game-moneyline",
  "market_type": "moneyline_2way", "bookmaker": "one-book",
  "snapshot_id": "locked-snapshot", "available_at": "2026-01-01T10:00:00Z",
  "outcomes": [
    {"event_id": "event-1", "market_id": "full-game-moneyline", "bookmaker": "one-book", "snapshot_id": "locked-snapshot", "available_at": "2026-01-01T10:00:00Z", "selection_id": "home", "decimal_odds": 1.8},
    {"event_id": "event-1", "market_id": "full-game-moneyline", "bookmaker": "one-book", "snapshot_id": "locked-snapshot", "available_at": "2026-01-01T10:00:00Z", "selection_id": "away", "decimal_odds": 2.2}
  ]
}
```

Proportional de-vig divides each inverse price by the sum of all inverse prices.
This is an explicit benchmark convention, not a claim of true probability.
Mixed-book best prices, incomplete three-way markets, mismatched lines, stale
quotes and unsupported market types never receive an inferred complement. The
benchmark is marked unavailable with its reason instead. The frozen incumbent
baseline remains mandatory. Market metrics use only the same covered rows for
candidate and market; a partial benchmark cannot imply full-sample superiority.

## Split, deduplication and evaluation policy

Before viewing the final holdout, register the dataset, model versions, split
dates, candidate specification and primary metrics. Keep all attempted variants
and failed experiments; do not recycle the final holdout to select another model.
The pure runner cannot enforce external experiment history or certify that an
operator has never inspected the holdout. Partition SHA-256 digests in its report
support comparison against independently retained manifests, not certification.

- Training decisions are strictly before `train_before`; **all verified labels
  used for training must also be strictly before that cutoff**.
- Development decisions lie from `train_before` up to `holdout_from`.
- Holdout decisions lie from `holdout_from` up to `evaluation_as_of`. Final grades
  must be verified by `evaluation_as_of` to be scored.
- Whole event groups stay in one partition. Groups spanning a split or having
  inconsistent identity are quarantined, never divided by individual rows.
- Identical repeated predictions are counted once. Conflicting duplicate
  predictions quarantine the event. If one member fails admission, otherwise
  valid members of the same event are also quarantined.
- Losses and calibration statistics are event-balanced. Additional selections
  for one event do not become independent evidence.
- Candidate and frozen baseline are evaluated on identical rows. Development
  outcomes are diagnostic only and cannot alter the fitted candidate.

Outputs include Brier score, log loss, ten-bin expected calibration error,
calibration bias/reliability bins, paired metric differences, per-sport/market
subgroups, record rejection reasons and eligibility coverage. Coverage means
**data eligibility, not betting-selection coverage**. There is no forced minimum
selection and no wagering or stake recommendation.

Uncertainty first averages within events, then uses a deterministic UTC
decision-day block bootstrap (500 replicates, seed 1729). It retains same-day
clustering but does not fully model longer temporal/team dependence. Confidence
intervals do not repair bad labels, selection bias, multiple testing or a reused
holdout.

`REVIEW_CANDIDATE` additionally requires at least 50 diverse training events,
100 diverse holdout events, 20 holdout decision-day blocks, no rejected records,
both Brier and log-loss upper 95% paired-bootstrap bounds below zero, no ECE
deterioration greater than 0.005, and at least 50 diverse events with non-worsening
Brier/log loss in every observed sport/market subgroup. These local review
thresholds are not statistical guarantees and do not replace existing gates.

## Run

```bash
python -m tools.run_offline_learning_validation verified-experiment.json \
  --train-before 2026-01-01T00:00:00Z \
  --holdout-from 2026-02-01T00:00:00Z \
  --evaluation-as-of 2026-06-01T00:00:00Z
```

The command writes JSON to stdout only. Exit 0 means local `REVIEW_CANDIDATE`,
not deployable or profitable; exit 2 means insufficient evidence or invalid CLI
input. No existing data file or learned state is selected implicitly.

## What to teach next, after verified evidence exists

Evaluate one predeclared family at a time with timestamped, source-backed data,
ablation tests and fresh held-out evidence:

1. Data quality, entity/market matching, missingness and source disagreement.
2. Opponent-adjusted prior performance, availability, rest and travel.
3. Sport-specific hypotheses: baseball starter/lineup/handedness/bullpen/park;
   basketball minutes/rotations/pace; football/soccer/hockey position-specific
   availability and confirmed starters; tennis surface/workload; combat sports
   weight-class, opponent quality and short-notice context.
4. Subgroup calibration and shift by sport, market, time and probability range.
5. Calibrated abstention under stale inputs, insufficient sample, disagreement
   or distribution shift. Evaluate all eligible predictions, not just winners.

These are research hypotheses, not activated capabilities or guaranteed edges.
Prefer a simple model with defensible unseen improvement over complexity without
evidence. No paid data/API, installation, budget expansion or live promotion is
authorized by this module. Independently verified untouched data—not more
aggressive retraining—is the current prerequisite for real learning claims.
