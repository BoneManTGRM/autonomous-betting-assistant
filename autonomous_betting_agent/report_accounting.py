"""Report-only settlement accounting. Never writes or regrades stored proof rows.

Net profit, stake, gross return, ROI and probability are different quantities.
Only explicit stake units support derived settlement profit; absent fees are
identified in the basis rather than silently described as an actual net receipt.
"""
from __future__ import annotations

import json
import math
from typing import Any, Mapping

INPUT_FIELD = 'report_accounting_input_json'
GRADE_FIELDS = (
    'verified_grade', 'verified_result', 'verified_status', 'verified_outcome',
    'verified_result_status', 'manual_grade', 'proof_grade', 'pick_grade',
    'row_grade', 'result_grade', 'result_status', 'result', 'final_result',
    'grade', 'outcome', 'bet_result', 'status', 'settled_status', 'win_loss',
    'final_grade', 'pick_result', 'settlement_status', 'graded_result', 'resultado',
)
NET_FIELDS = (
    'actual_profit_units', 'resolved_profit_units', 'graded_profit_units',
    'profit_units', 'net_units', 'pnl_units', 'profit_loss', 'pnl', 'profit', 'net_profit',
)
STAKE_FIELDS = ('actual_stake_units', 'stake_units', 'wagered_stake_units')
FEE_FIELDS = ('fees_units', 'commission_units')
PRICE_FIELDS = ('odds_at_pick', 'decimal_price', 'decimal_odds', 'best_price', 'odds_decimal')
INPUT_FIELDS = GRADE_FIELDS + NET_FIELDS + STAKE_FIELDS + FEE_FIELDS + PRICE_FIELDS + ('units', 'roi', 'return_units')
SETTLED = {'WIN', 'LOSS', 'PUSH', 'CANCELLED'}


def _token(value: Any) -> str:
    return '' if value is None else ' '.join(str(value).strip().lower().replace('_', ' ').replace('-', ' ').split())


def _snapshot_value(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def preserve_accounting_input(row: Mapping[str, Any]) -> dict[str, Any]:
    """Keep original accounting before generic aliases or repeat report enrichment."""
    out = dict(row)
    if isinstance(out.get(INPUT_FIELD), str):
        try:
            if isinstance(json.loads(out[INPUT_FIELD]), dict):
                return out
        except (ValueError, TypeError):
            pass
    values = {key: _snapshot_value(row[key]) for key in INPUT_FIELDS if key in row}
    out[INPUT_FIELD] = json.dumps(values, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return out


def _grade(value: Any) -> str | None:
    text = _token(value)
    if text in {'', 'none', 'null', 'nan', '<na>', 'n/a', 'na'}:
        return None
    if text in {'win', 'won', 'winner', 'w', 'graded win', 'cash', 'cashed', 'success', 'correct', 'hit', 'true', 'yes', '1', '1.0', 'ganada', 'ganó', 'gano', 'victoria', 'acierto'}:
        return 'WIN'
    if text in {'loss', 'lost', 'loser', 'l', 'graded loss', 'failed', 'lose', 'incorrect', 'miss', 'false', 'no', '0', '0.0', 'perdida', 'perdió', 'perdio', 'derrota', 'fallo'}:
        return 'LOSS'
    if text in {'push', 'void', 'tie', 'draw', 'refund', 'refunded', 'returned', 'no action', 'draw no bet push'}:
        return 'PUSH'
    if text in {'cancel', 'cancelled', 'canceled', 'postponed', 'abandoned', 'no contest'}:
        return 'CANCELLED'
    if text in {'pending', 'open', 'ungraded', 'not graded', 'scheduled', 'live'}:
        return 'PENDING'
    return 'UNKNOWN'


def _amount(values: Mapping[str, Any], fields: tuple[str, ...]) -> tuple[float | None, bool, bool]:
    """Return value, explicit-presence, invalid/conflicting aliases (no fallback)."""
    numbers = []
    present = False
    for field in fields:
        value = values.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        present = True
        if isinstance(value, bool):
            return None, True, True
        try:
            number = float(str(value).replace(',', '').strip())
        except (TypeError, ValueError, OverflowError):
            return None, True, True
        if not math.isfinite(number):
            return None, True, True
        numbers.append(number)
    if numbers and any(not math.isclose(numbers[0], other, rel_tol=1e-9, abs_tol=1e-9) for other in numbers[1:]):
        return None, True, True
    return (numbers[0] if numbers else None), present, False


def accounting_result(row: Mapping[str, Any]) -> dict[str, Any]:
    preserved = preserve_accounting_input(row)
    source = json.loads(preserved[INPUT_FIELD])
    issues = []
    grades = {_grade(source.get(field)) for field in GRADE_FIELDS}
    grades.discard(None)
    # Generic provider lifecycle values are not settlement results.
    if _token(source.get('status')) in {'final', 'finished', 'completed', 'settled'}:
        grades = {_grade(source.get(field)) for field in GRADE_FIELDS if field != 'status'}
        grades.discard(None)
    grade = next(iter(grades)) if len(grades) == 1 else 'UNKNOWN'
    if len(grades) > 1:
        issues.append('conflicting_result_fields')
    elif grade == 'UNKNOWN':
        issues.append('missing_or_unknown_result')
    stake, _, bad_stake = _amount(source, STAKE_FIELDS)
    if bad_stake or (stake is not None and stake <= 0):
        stake = None
        issues.append('invalid_or_conflicting_stake_units')
    net, has_net, bad_net = _amount(source, NET_FIELDS)
    fees, has_fees, bad_fees = _amount(source, FEE_FIELDS)
    if bad_fees or (fees is not None and fees < 0):
        fees = None
        issues.append('invalid_or_conflicting_fee_units')
    profit = None
    basis = 'unavailable'
    if bad_net:
        issues.append('invalid_or_conflicting_net_profit')
    if grade in SETTLED and has_net and not bad_net:
        inconsistent = (grade in {'LOSS', 'PUSH', 'CANCELLED'} and net > 0) or (grade == 'WIN' and net < 0 and (fees is None or fees < abs(net)))
        if inconsistent:
            issues.append('settlement_net_profit_conflict')
        else:
            profit, basis = net, 'explicit_net_profit'
    elif grade in SETTLED and not has_net and stake is not None and not bad_fees and (fees is None or fees >= 0):
        gross = None
        if grade == 'WIN':
            for field in PRICE_FIELDS:
                price, present, invalid = _amount(source, (field,))
                if present:
                    if not invalid and price > 1:
                        gross = stake * (price - 1)
                    else:
                        issues.append('invalid_settlement_decimal_price')
                    break
        elif grade == 'LOSS':
            gross = -stake
        else:
            gross = 0.0
        if gross is not None:
            profit = gross - (fees or 0.0)
            if not math.isfinite(profit):
                profit = None
                issues.append('nonfinite_derived_profit')
            else:
                profit = round(profit, 12)
                basis = 'derived_after_explicit_fees' if has_fees else 'derived_before_unspecified_fees'
    if grade in SETTLED and profit is None:
        issues.append('settlement_profit_unavailable')
    quarantined = any(any(token in issue for token in ('conflicting_', 'invalid_', '_conflict', 'nonfinite_')) for issue in issues)
    return {
        INPUT_FIELD: preserved[INPUT_FIELD],
        'result_status': grade,
        'profit_units': profit,
        'report_stake_units': stake,
        'report_profit_basis': basis,
        'report_accounting_status': 'review' if issues else ('settled' if grade in SETTLED else 'pending'),
        'report_accounting_quarantined': quarantined,
        'report_accounting_issues': '; '.join(dict.fromkeys(issues)),
    }
