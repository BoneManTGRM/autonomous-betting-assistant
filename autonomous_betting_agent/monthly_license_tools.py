from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .commercial_platform_tools import dashboard_metrics, proof_audit_summary
from .row_normalizer import safe_text

REPO_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_COMMERCIAL_PAGES = {
    'Deployment Health': 'pages/deployment_health.py',
    'Odds Lock Pro': 'pages/odds_lock_pro.py',
    'Public Proof Dashboard': 'pages/public_proof_dashboard.py',
    'Auto Result Grading': 'pages/auto_result_grading.py',
    'Daily Workflow': 'pages/daily_workflow.py',
    'Buyer Demo Mode': 'pages/buyer_demo_mode.py',
}

PRICING_TIERS = [
    {
        'tier': 'Private beta license',
        'target_price': '$500-$1,000/mo',
        'best_for': 'First 2-3 serious testers',
        'include': 'private dashboard, daily reports, proof ledger, result tracking',
        'minimum_proof': '25+ locked rows and clean proof audit',
    },
    {
        'tier': 'Private analyst license',
        'target_price': '$1,000-$2,500/mo',
        'best_for': 'Serious bettors, analysts, small private groups',
        'include': 'ranked predictions, proof dashboard, reports, ROI/CLV tracking, support',
        'minimum_proof': '100+ future-locked rows, positive ROI, clean audit',
    },
    {
        'tier': 'Operator license',
        'target_price': '$2,500-$5,000/mo',
        'best_for': 'Influencer, Discord/Telegram operator, paid research group',
        'include': 'operator dashboard, branded reports, proof exports, weekly review calls',
        'minimum_proof': '250+ locked rows, stable ROI/CLV, documented workflow',
    },
    {
        'tier': 'White-label/private deployment',
        'target_price': '$10,000 setup + $5,000-$10,000/mo',
        'best_for': 'Client wants their own branded deployment',
        'include': 'private deployment, branding, API setup, onboarding, priority support',
        'minimum_proof': 'operator-ready proof plus access control and deployment SOP',
    },
]

CLIENT_PACKAGE_ITEMS = [
    'Private analytics dashboard access or private report delivery',
    'Future-only locked proof ledger with proof ID and proof hash',
    'Daily ranked prediction report with model probability, odds, and bookmaker',
    'Public/client-safe proof dashboard with record, ROI, pending picks, and audit quality',
    'Auto result grading workflow for finished games',
    'Weekly performance review: wins/losses, ROI, CLV, sport breakdown, and blockers',
    'Clear analytics-only disclaimer: no guaranteed wins, no managed funds, no transaction execution',
]


def pct(value: Any, digits: int = 1) -> str:
    if value is None or value == '':
        return 'N/A'
    try:
        return f'{float(value) * 100:.{digits}f}%'
    except (TypeError, ValueError):
        return 'N/A'


def _safe_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def _status(ok: bool, warn: bool = False) -> str:
    if ok:
        return 'pass'
    if warn:
        return 'warning'
    return 'blocker'


def _page_present(path: str, root: Path = REPO_ROOT) -> bool:
    return (root / path).exists()


def readiness_checklist(frame: pd.DataFrame | list[dict[str, Any]], root: Path = REPO_ROOT) -> pd.DataFrame:
    metrics = dashboard_metrics(frame)
    audit = proof_audit_summary(frame)
    locked = _safe_int(metrics.get('locked_picks'))
    resolved = _safe_int(metrics.get('resolved_picks'))
    pending = _safe_int(metrics.get('pending_picks'))
    wins = _safe_int(metrics.get('wins'))
    losses = _safe_int(metrics.get('losses'))
    proof_quality = _safe_float(audit.get('proof_quality_score')) or 0.0
    hash_mismatch = _safe_int(audit.get('hash_mismatch'))
    locked_before = _safe_int(audit.get('locked_before_start'))
    roi = _safe_float(metrics.get('roi'))
    clv = _safe_float(metrics.get('avg_clv_percent'))
    beat_close = _safe_float(metrics.get('beat_close_rate'))

    rows: list[dict[str, Any]] = []

    def add(area: str, item: str, status: str, beta_weight: int, operator_weight: int, details: str) -> None:
        rows.append({
            'area': area,
            'item': item,
            'status': status,
            'beta_weight': beta_weight,
            'operator_weight': operator_weight,
            'details': details,
        })

    add(
        'Proof',
        'Future-only locked proof rows exist',
        _status(locked >= 25, warn=locked > 0),
        20,
        15,
        f'{locked} locked proof rows. Beta target: 25+. Operator target: 100+.',
    )
    add(
        'Proof',
        'Enough resolved rows to discuss performance honestly',
        _status(resolved >= 20, warn=resolved > 0),
        15,
        15,
        f'{resolved} resolved rows, {pending} pending. Current record: {wins}-{losses}.',
    )
    add(
        'Proof',
        'Proof audit is clean',
        _status(proof_quality >= 90 and hash_mismatch == 0, warn=proof_quality >= 70),
        20,
        20,
        f'Proof quality: {proof_quality}/100. Hash mismatches: {hash_mismatch}. Locked before start: {locked_before}.',
    )
    add(
        'Performance',
        'ROI is visible and not hidden behind hit rate only',
        _status(roi is not None, warn=False),
        10,
        15,
        f'ROI: {pct(roi)}. Hit rate: {pct(metrics.get("hit_rate"))}.',
    )
    add(
        'Performance',
        'CLV/closing-price tracking is available',
        _status(clv is not None or beat_close is not None, warn=False),
        5,
        10,
        f'Average CLV: {pct(clv, 2)}. Beat-close rate: {pct(beat_close)}.',
    )
    for label, path in REQUIRED_COMMERCIAL_PAGES.items():
        add(
            'Product',
            f'{label} page is present',
            _status(_page_present(path, root=root)),
            4 if label in {'Odds Lock Pro', 'Public Proof Dashboard', 'Daily Workflow'} else 2,
            4,
            path,
        )
    add(
        'Client safety',
        'Analytics-only positioning is explicit',
        'pass',
        8,
        8,
        'Sell analytics/research access only. Do not promise guaranteed wins or returns.',
    )
    add(
        'Client safety',
        'Monthly license package is defined',
        'pass',
        6,
        8,
        'Use beta, private analyst, operator, and white-label tiers instead of selling the repo outright.',
    )
    add(
        'Operations',
        'Private support/onboarding path exists',
        'warning',
        4,
        8,
        'Document setup, daily workflow, result grading, and who handles API keys before selling higher tiers.',
    )
    return pd.DataFrame(rows)


def readiness_scores(frame: pd.DataFrame | list[dict[str, Any]], root: Path = REPO_ROOT) -> dict[str, Any]:
    checks = readiness_checklist(frame, root=root)
    if checks.empty:
        return {'beta_score': 0, 'operator_score': 0, 'beta_status': 'not_ready', 'operator_status': 'not_ready'}

    def weighted_score(weight_col: str) -> int:
        total = float(checks[weight_col].sum())
        if total <= 0:
            return 0
        earned = 0.0
        for row in checks.to_dict(orient='records'):
            weight = float(row.get(weight_col) or 0)
            status = safe_text(row.get('status')).lower()
            if status == 'pass':
                earned += weight
            elif status == 'warning':
                earned += weight * 0.5
        return int(round((earned / total) * 100))

    beta_score = weighted_score('beta_weight')
    operator_score = weighted_score('operator_weight')
    beta_blockers = int(((checks['status'] == 'blocker') & (checks['beta_weight'] > 0)).sum())
    operator_blockers = int(((checks['status'] == 'blocker') & (checks['operator_weight'] > 0)).sum())
    return {
        'beta_score': beta_score,
        'operator_score': operator_score,
        'beta_status': 'ready_for_private_beta' if beta_score >= 80 and beta_blockers <= 1 else 'needs_work',
        'operator_status': 'ready_for_operator_license' if operator_score >= 85 and operator_blockers == 0 else 'needs_more_proof',
        'beta_blockers': beta_blockers,
        'operator_blockers': operator_blockers,
    }


def pricing_tiers_frame() -> pd.DataFrame:
    return pd.DataFrame(PRICING_TIERS)


def client_package_frame() -> pd.DataFrame:
    return pd.DataFrame([{'included_item': item} for item in CLIENT_PACKAGE_ITEMS])


def next_build_queue(checks: pd.DataFrame) -> pd.DataFrame:
    if checks.empty:
        return pd.DataFrame()
    queue = checks[checks['status'].isin(['blocker', 'warning'])].copy()
    if queue.empty:
        return pd.DataFrame([{'priority': 1, 'task': 'Keep collecting future-locked proof rows and result updates.', 'reason': 'No current blockers.'}])
    queue['priority_score'] = queue['operator_weight'].fillna(0) * queue['status'].map({'blocker': 2, 'warning': 1}).fillna(0)
    queue = queue.sort_values(['priority_score', 'operator_weight'], ascending=False)
    rows = []
    for index, row in enumerate(queue.to_dict(orient='records'), start=1):
        rows.append({'priority': index, 'task': row['item'], 'reason': row['details'], 'status': row['status']})
    return pd.DataFrame(rows)


def license_offer_text(frame: pd.DataFrame | list[dict[str, Any]], brand: str = 'Private Analytics') -> str:
    metrics = dashboard_metrics(frame)
    scores = readiness_scores(frame)
    hit_rate = pct(metrics.get('hit_rate'))
    roi = pct(metrics.get('roi'))
    clv = pct(metrics.get('avg_clv_percent'), 2)
    record = f"{metrics.get('wins', 0)}-{metrics.get('losses', 0)}"
    return '\n'.join([
        f'{brand} private sports analytics license',
        '',
        'Offer: private access to a sports analytics and proof-tracking system that scans markets, ranks predictions, locks official picks before event start, grades finished results, and produces client-safe proof reports.',
        '',
        'Current proof dashboard snapshot:',
        f"- Locked proof rows: {metrics.get('locked_picks', 0)}",
        f"- Resolved: {metrics.get('resolved_picks', 0)}",
        f'- Record: {record}',
        f'- Hit rate: {hit_rate}',
        f'- ROI: {roi}',
        f'- Average CLV: {clv}',
        f"- Beta readiness score: {scores.get('beta_score', 0)}/100",
        f"- Operator readiness score: {scores.get('operator_score', 0)}/100",
        '',
        'Recommended starting package:',
        '- 30-day private beta license',
        '- $500-$1,000/month for early testers',
        '- Includes dashboard/report access, future-only proof ledger, result grading, and weekly review',
        '',
        'Important terms:',
        '- Analytics and research software only',
        '- No guaranteed wins or returns',
        '- No managed funds and no transaction execution',
        '- Client is responsible for all real-world decisions',
    ])
