# SportsDataIO integration

This repo can fetch SportsDataIO data without hardcoding one league or one endpoint. The client works with whichever SportsDataIO feeds your account has access to.

## API key

Set your SportsDataIO key as an environment variable:

```bash
export SPORTSDATAIO_API_KEY="your_key_here"
```

On Windows PowerShell:

```powershell
$env:SPORTSDATAIO_API_KEY="your_key_here"
```

The client defaults to the documented header auth mode:

```text
Ocp-Apim-Subscription-Key: {key}
```

You can use query-string auth with `--auth-mode query` if needed.

## Fetch any endpoint

```bash
python tools/fetch_sportsdataio.py ScoresByDate/2026-JAN-15 --sport nfl --subfeed scores --output data/sportsdataio_nfl_scores.json
```

The CLI builds a URL like:

```text
https://api.sportsdata.io/v3/nfl/scores/json/ScoresByDate/2026-JAN-15
```

## Save flattened CSV too

Raw JSON is useful for debugging, but the betting pipeline usually needs CSV. Add `--csv-output`:

```bash
python tools/fetch_sportsdataio.py ScoresByDate/2026-JAN-15 --sport nfl --subfeed scores --output data/sportsdataio_nfl_scores.json --csv-output data/sportsdataio_nfl_scores.csv
```

If the JSON payload is an object with multiple lists, choose the list to flatten with `--record-key`:

```bash
python tools/fetch_sportsdataio.py SomeEndpoint --sport nfl --subfeed scores --output data/raw.json --csv-output data/flat.csv --record-key Games
```

Nested objects are flattened into columns such as `Score_Home`. Nested lists are preserved as JSON strings so CSV export stays safe.

## Save canonical model-ready CSV

Flattened SportsDataIO fields can vary by endpoint. The canonical normalizer converts common game, player and team payloads into stable columns for the model/tracker.

```bash
python tools/fetch_sportsdataio.py ScoresByDate/2026-JAN-15 --sport nfl --subfeed scores --output data/raw_scores.json --csv-output data/flat_scores.csv --canonical-output data/canonical_games.csv --dataset-type games
```

Use `--dataset-type auto` when you want the tool to infer `games`, `players` or `teams` from the payload keys:

```bash
python tools/fetch_sportsdataio.py Players --sport nfl --subfeed scores --output data/raw_players.json --canonical-output data/canonical_players.csv --dataset-type auto
```

Canonical game columns include:

```text
sdio_game_id
sport
season
week
start_time
status
is_final
home_team
away_team
home_score
away_score
winner
source_quality_flags
```

Canonical player columns include:

```text
sdio_player_id
sport
display_name
team
position
status
injury_status
source_quality_flags
```

Canonical team columns include:

```text
sdio_team_id
sport
team_key
city
name
full_name
conference
division
source_quality_flags
```

`source_quality_flags` marks missing critical fields so bad rows do not silently enter the model.

## Common examples

Teams:

```bash
python tools/fetch_sportsdataio.py Teams --sport nfl --subfeed scores --output data/sportsdataio_nfl_teams.json --csv-output data/sportsdataio_nfl_teams.csv --canonical-output data/canonical_teams.csv --dataset-type teams
```

Players:

```bash
python tools/fetch_sportsdataio.py Players --sport nfl --subfeed scores --output data/sportsdataio_nfl_players.json --csv-output data/sportsdataio_nfl_players.csv --canonical-output data/canonical_players.csv --dataset-type players
```

Games by season:

```bash
python tools/fetch_sportsdataio.py Games/2026 --sport nfl --subfeed scores --output data/sportsdataio_nfl_games.json --csv-output data/sportsdataio_nfl_games.csv --canonical-output data/canonical_games.csv --dataset-type games
```

Stats feed endpoint:

```bash
python tools/fetch_sportsdataio.py PlayerSeasonStats/2026 --sport nfl --subfeed stats --output data/sportsdataio_player_season_stats.json --csv-output data/sportsdataio_player_season_stats.csv
```

Exact endpoint names depend on your SportsDataIO product, sport, and feed access. If SportsDataIO says an endpoint requires production access, the client will raise a clear HTTP error.

## How this helps the betting agent

SportsDataIO should be used for the independent-data layer:

- schedules
- final scores/results
- teams
- players
- player stats
- team stats
- injuries
- lineups/depth charts when included in your plan
- historical results

The odds and CLV layer still needs odds history from an odds provider. SportsDataIO can help with betting data if that is included in your plan, but do not assume every feed is available in the free trial.

## No guarantee

SportsDataIO improves input quality. It does not guarantee a 70% win rate or profit. The system still needs deduped tracking, closing-line value, ROI, and hundreds of prospectively tracked finished picks.
