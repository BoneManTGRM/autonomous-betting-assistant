# Chain Bet Optimizer v2

Chain Bet Optimizer v2 is a conservative chain-review layer for ABA Signal Pro. It is designed to recommend fewer chains, reject random filler legs, compare every chain to the straight option, and explain why a chain is approved, rejected, aggressive-only, or watch-only.

It does not execute bets and does not guarantee wins, ROI, profit, or a higher win rate.

## Core principle

The optimizer should often return:

```text
NO CHAIN RECOMMENDED TODAY
```

That is preferred when the chain does not pass probability, EV, risk, correlation, or chain-killer rules.

## Main modules

```text
autonomous_betting_agent/chain_optimizer_v2.py
autonomous_betting_agent/chain_optimizer_report.py
```

## What Chain Optimizer v2 checks

1. Straight bet vs chain comparison
2. Leg purpose scoring
3. EV and probability quality
4. Volatility and dependency risk
5. Correlation scoring
6. Target payout fit
7. Chain killer rules
8. Client profile risk floors

## Straight bet vs chain

The optimizer compares:

- Straight probability, odds, EV, and risk
- Chain probability, odds, EV, and risk
- Probability drop
- Payout gain
- Risk increase
- EV delta

If the straight option has a better EV-adjusted risk profile, the chain is marked:

```text
STRAIGHT BET BETTER THAN CHAIN
```

## Leg purpose scoring

Each leg receives:

- Purpose score
- Correlation score
- Volatility score
- Dependency risk
- Leg quality score
- Accepted/rejected status
- Rejection reason

Bad filler legs are rejected or penalized.

## Correlation labels

Supported labels:

- Positive script correlation
- Neutral correlation
- Risky correlation
- Contradictory correlation

Contradictory correlation can trigger a chain killer.

## Target payout fit

Target payout mode calculates:

- Required decimal odds
- Actual chain decimal odds
- Estimated payout
- Target distance
- Target fit label

A good payout fit cannot override bad EV, poor probability, excessive risk, or chain killers.

## Client profile floors

- Conservative: 2-leg max, 45% adjusted probability floor
- Balanced: 3-leg max, 30% adjusted probability floor
- Aggressive: 4-leg max, 20% adjusted probability floor

Below 20% should not be recommended as a chain.

## Report helpers

Use:

```python
from autonomous_betting_agent.chain_optimizer_report import (
    render_chain_optimizer_card,
    render_chain_optimizer_magazine_section,
    chain_optimizer_results_to_rows,
    split_chain_optimizer_sections,
)
```

Sections:

- Best Approved Chains
- Straight Bet Better Than Chain
- Rejected Chains
- Aggressive Only Chains
- No Chain Recommended

## How to wire into Client_Magazine.py

1. Import:

```python
from autonomous_betting_agent.chain_optimizer_v2 import optimize_chain_candidates
from autonomous_betting_agent.chain_optimizer_report import (
    render_chain_optimizer_magazine_section,
    chain_optimizer_results_to_rows,
    split_chain_optimizer_sections,
    render_chain_optimizer_card,
)
```

2. Add sidebar controls:

```python
enable_chain_optimizer_v2 = st.checkbox("Enable Chain Optimizer v2", value=True)
show_chain_optimizer_cards = st.checkbox("Show Chain Optimizer v2 cards", value=True)
target_payout_mode = st.checkbox("Target payout mode", value=False)
```

3. Group rows by game/event.

4. Pick the best straight candidate per group by EV, probability, risk, and market type.

5. Use the remaining same-game rows as candidate legs.

6. Call:

```python
result = optimize_chain_candidates(
    straight_pick,
    candidate_legs,
    target_payout=target_payout if target_payout_mode else None,
    stake=stake_amount if target_payout_mode else None,
    external_context=external_context if available else None,
    client_profile=profile,
)
```

7. Render:

```python
st.markdown(render_chain_optimizer_card(result))
```

8. Add to magazine:

```python
magazine += "\n" + render_chain_optimizer_magazine_section(chain_optimizer_results)
```

9. Add to CSV export:

```python
optimizer_rows = chain_optimizer_results_to_rows(chain_optimizer_results)
```

## Safety note

Every chain section should include:

```text
This is not a guaranteed result. Chain bets can lose if any leg fails.
```

Chain bets are higher risk because one failed leg can lose the full ticket. These are projected probabilities, not guaranteed outcomes.
