# Player Props Layer

The player props layer scores individual player outcomes while still using market odds.

Supported examples include:

- anytime touchdown
- home run
- goal
- shot on goal
- assist
- hit
- strikeout
- reception
- rushing yards
- receiving yards
- passing yards

## Core idea

The layer does not throw away the market. It uses the market as a baseline, then compares it against an independent player probability.

```text
market probability + player model probability + data confidence -> blended probability -> edge -> status
```

Market probability can come from:

- decimal price such as `best_price`
- American odds such as `+150` or `-120`
- direct `market_probability`
- binary no-vig prices such as `over_price` and `under_price`

Player probability can come from:

- direct `model_probability`
- recent player rate
- season player rate
- opponent allowed rate
- usage rate
- SportsDataIO player feature enrichment

## Recommended CSV inputs

Minimum useful columns:

```text
player_name
prop_type
best_price or market_probability
model_probability or player rates
books
data_quality
sample_size
injury_status
```

Better inputs:

```text
recent_rate
season_rate
opponent_allowed_rate
usage_rate
recent_games
season_games
book_count
over_price
under_price
```

## SportsDataIO feature enrichment

After building SportsDataIO player features, enrich player props before scoring them:

```bash
python tools/enrich_player_props_with_features.py player_props.csv data/sportsdataio_player_features.csv --output data/player_props_enriched_with_features.csv
python tools/run_player_props.py data/player_props_enriched_with_features.csv
```

The enrichment layer joins by:

```text
player id, when present
unique normalized player name
```

It adds:

```text
feature_match_status
feature_match_key
feature_expected_value
feature_season_rate
feature_usage_rate
feature_sample_size
feature_data_quality
feature_reason
```

Then it fills the existing player-prop model inputs when they are missing:

```text
season_rate
usage_rate
sample_size
data_quality
```

For line props such as passing yards, rushing yards, receiving yards, receptions, strikeouts and shots on goal, it compares the SportsDataIO per-game feature to the prop line. For binary props such as touchdown, home run, goal, assist and hit, it uses a conservative Poisson-style estimate from the per-game event rate.

Rows with no unique feature match are not force-enriched. Ambiguous player-name matches are left alone so the scorer does not use the wrong player.

## Command

```bash
python tools/run_player_props.py player_props.csv
```

Default outputs:

```text
data/player_props_checked.csv
data/player_props_ranked.csv
```

Use this when you want to inspect watch/reject rows too:

```bash
python tools/run_player_props.py player_props.csv --include-watch
```

## Important output columns

- `prop_player_name`
- `prop_type_normalized`
- `prop_market_source`
- `prop_market_probability`
- `prop_no_vig_probability`
- `prop_model_probability`
- `prop_blended_probability`
- `prop_implied_edge`
- `prop_fair_decimal_price`
- `prop_data_quality`
- `prop_confidence_score`
- `prop_status`
- `prop_stake_units`
- `prop_reasons`
- `prop_required_data`

## Final statuses

Candidate statuses:

```text
QUALIFIED_STRONG
QUALIFIED
QUALIFIED_SMALL
```

Not-ready statuses:

```text
WATCH
TRACK_ONLY_NEEDS_PLAYER_MODEL_DATA
REJECT
```

## Status controls

Rows can be blocked or watched for:

- missing player name
- missing prop type
- missing market probability or price
- missing player model probability or player rates
- low book coverage
- missing book coverage
- low data quality
- missing data quality
- missing sample size
- small sample size
- bad player status such as out, doubtful, inactive or IR
- watch player status such as questionable, probable or limited

## Required caution

Player props are volatile. A player can be limited by injury, playing time, lineup role, game script, weather, defense, substitutions, foul trouble, or coaching decisions. Use the output as a research shortlist, not as proof of edge.
