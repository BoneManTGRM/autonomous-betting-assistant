# Autonomous Betting Agent

Autonomous Betting Agent is a standalone sports research agent built from the ARA/TGRM idea: run repeatable research cycles, detect weak evidence, repair the analysis, verify uncertainty, and produce a transparent probability report.

This is **research-only software**. It does not place bets, does not guarantee winners, and should not be treated as proof of profitability without rigorous backtesting and prospective testing.

## What it does

- estimates win probabilities for two-outcome sports events
- explains which factors moved the model
- tracks confidence, evidence strength and uncertainty
- compares model probabilities with no-vig market probabilities
- calculates expected-value diagnostics for later testing
- logs a TGRM-style TEST, DETECT, REPAIR, VERIFY cycle
- supports backtesting metrics such as Brier score and log loss
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

## Run the Streamlit app

```bash
streamlit run app_streamlit.py
```

## Run tests

```bash
python -m unittest discover -s tests
```

## Current model signals

The baseline supports:

- rating difference
- recent form
- injury impact
- rest and schedule advantage
- matchup-specific edge
- weather or playing-condition fit
- home advantage
- data completeness
- source diversity

All inputs are normalized so results remain interpretable. Future sport-specific modules should replace generic signals with validated features for each sport.

## Recommended development path

1. Pick the first sport.
2. Add official schedule and statistics providers.
3. Add injury, lineup and weather providers.
4. Add odds-provider interfaces with timestamped market snapshots.
5. Build historical event storage.
6. Add strict time-aware backtesting that prevents future-data leakage.
7. Tune weights only on training data.
8. Evaluate on untouched historical data.
9. Run prospective tests before making any performance claims.

## Validation standard

No claim of accuracy or profitability should be made until the system is tested on a large untouched historical dataset and then evaluated prospectively. Sports outcomes are uncertain, market prices include margins, and backtests can be misleading if they contain leakage, overfitting or unrealistic execution assumptions.

## License

MIT License.
