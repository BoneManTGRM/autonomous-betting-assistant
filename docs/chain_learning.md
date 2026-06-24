# Chain Bet Learning Memory

Chain bet learning memory adds leg-level post-game analytics for ABA Signal Pro. It learns from completed chain results without placing bets and without guaranteeing future results.

## What it does

The learning layer grades chains at the leg level so the system can distinguish:

- Main read wrong
- Main read correct but add-on leg failed
- Straight bet would have won while the chain lost
- Game script correct but selected add-on leg bad
- Target payout chase caused a weak filler leg
- Push/void/unknown legs that should not create strong learning

## Why leg-level learning matters

A chain can lose even when the main read was correct. For example, a favorite wins but an opponent-corner add-on fails. Without leg-level grading, the system may wrongly punish the main read instead of the weak add-on structure.

## Main modules

```text
autonomous_betting_agent/chain_learning.py
autonomous_betting_agent/chain_learning_store.py
```

## Core outputs

`ChainResultBreakdown` tracks:

- chain_id
- game
- final_status
- straight_pick_status
- chain_status
- failed_leg_count
- failed_legs
- main_read_correct
- game_script_correct
- target_payout_chase_detected
- straight_bet_would_have_won
- chain_was_better_than_straight
- learning_summary

`ChainLearningSignal` tracks:

- signal_type
- market_type
- script_type
- leg_type
- adjustment_direction
- adjustment_strength
- reason
- sample_size
- confidence

## Straight-bet-better detection

If the main read or straight pick would have won but the chain lost, the system marks this pattern so future chains can be downgraded or shown as watch-only.

## Target payout chasing

If a filler leg is added mainly to reach a payout target and that leg fails, the system marks a target-payout chase pattern. This helps prevent the optimizer from forcing chains just to get closer to double-money payout.

## Memory store

Memory is stored in JSON-safe form at:

```text
data/chain_learning_memory.json
```

The store tracks:

- chain_learning_summary
- leg_failure_patterns
- successful_chain_patterns
- bad_filler_leg_patterns
- straight_bet_better_patterns
- target_payout_chase_patterns
- game_script_accuracy_patterns

## Safety limits

Chain learning can lower confidence, flag weak add-on markets, or mark future chains as watch-only. It should not create a bet by itself, override bad EV, or guarantee wins, ROI, profit, or higher win rate.

## Typical workflow

1. Generate chains with Chain Bet Optimizer v2.
2. Grade completed chain legs after results finish.
3. Run `grade_chain_result()`.
4. Save the result with `append_chain_learning_result()`.
5. Use summarized memory to inform future chain warnings.
