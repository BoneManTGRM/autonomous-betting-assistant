# Autonomous Betting Agent

Autonomous Betting Agent is a standalone sports research agent built from the ARA/TGRM idea: run repeatable research cycles, detect weak evidence, repair the analysis, verify uncertainty, and produce a transparent probability report.

This is **research-only software**. It does not place bets, does not guarantee winners, and should not be treated as proof of profitability without rigorous backtesting and prospective testing.

## What it does

- estimates win probabilities for two-outcome sports events
- lets each app user paste their own provider access token
- scans live market feeds when a provider token is supplied
- ranks the most likely outcome for upcoming games
- estimates likely scorelines such as 1-1, 2-1 and 2-3
- explains which factors moved the manual ARA model
- tracks confidence, evidence strength and uncertainty
- compares model probabilities with no-vig market probabilities
- calculates expected-value diagnostics for later testing
- logs a TGRM-style TEST, DETECT, REPAIR, VERIFY cycle
- supports backtesting metrics such as Brier score, accuracy and closing-line delta
- learns probability calibration from graded results and applies it to future predictions
- includes a CLI, sample event file, Streamlit UI and tests

## ARA/TGRM lineage

This project is separated from the original ARA repository so the original research agent remains clean. The new repo keeps the useful architecture pattern:

1. **TEST** the available event data.
2. **DETECT** weak sources, incomplete inputs and unstable signals.
3. **REPAIR** the analysis by converting evidence into auditable factors.
4. **VERIFY** with confidence, RYE-style efficiency and stability metrics.

The domain target is now sports analytics rather than longevity or scientific literature review.

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

## Run the sample

```bash
python run_agent.py examples/sample_event.json
```

Write JSON output to a file:

```bash
python run_agent.py examples/sample_event.json --json-output result.json
```

Run with a learned calibration state:

```bash
python run_agent.py examples/sample_event.json --learned-state learned_state.json
```

## Make it learn from graded results

The learning loop is now:

```text
prediction -> final result -> graded CSV -> train calibration -> learned_state.json -> future predictions
```

Train from a graded CSV:

```bash
python learn_from_results.py pro_predictor_updated_win_loss.csv --output learned_state.json
```

The CSV parser accepts common columns such as:

- `probability`, `predicted_probability`, `favorite_probability`, `model_probability` or `market_probability`
- `result`, `outcome`, `win_loss`, or `graded_result` with values like `won`, `lost`, `1`, or `0`
- optional `prediction` / `pick` and `winner` / `actual_winner` columns

The learned state stores calibration parameters, events trained, Brier score before/after, log loss before/after, and accuracy before/after. If `learned_state.json` exists in the project root, the live market scanner applies it automatically.

This is probability calibration, not proof of edge. It learns whether the raw market/model probabilities have been too confident, too cautious, or biased based on past graded predictions. Retrain it whenever more finished games are added.

## Run the Streamlit app

```bash
streamlit run app_streamlit.py
```

The Streamlit app asks each user for a provider access token on the app screen. This means the app owner does not have to store a shared token in Streamlit secrets.

Optional owner fallback: the app can still read `THE_ODDS_API_KEY` from Streamlit secrets or environment variables, but this is not required when each user provides their own token.

If `learned_state.json` exists in the app root, live market probabilities are calibrated from the graded-result learning loop before the favorite is displayed.

## Run tests

```bash
python -m unittest discover -s tests
```

## Current model signals

The baseline supports:

- live market feed scanning
- fuzzy team-name matching
- market-implied no-vig probabilities
- learned probability calibration from graded historical predictions
- likely outcome ranking
- expected-goals scoreline estimation
- scoreline and spread table generation
- ARA/TGRM cycle notes
- Brier score, accuracy and closing-line delta backtesting helpers

All inputs are normalized so results remain interpretable. Future sport-specific modules should replace generic signals with validated features for each sport.

## Recommended development path

1. Pick the first sport.
2. Add official schedule and statistics providers.
3. Add injury, lineup and weather providers.
4. Add market-provider interfaces with timestamped snapshots.
5. Build historical event storage.
6. Add strict time-aware backtesting that prevents future-data leakage.
7. Tune weights only on training data.
8. Evaluate on untouched historical data.
9. Run prospective tests before making any performance claims.

## Validation standard

No claim of accuracy or profitability should be made until the system is tested on a large untouched historical dataset and then evaluated prospectively. Sports outcomes are uncertain, market prices include margins, and backtests can be misleading if they contain leakage, overfitting or unrealistic execution assumptions.

## License

MIT License.
