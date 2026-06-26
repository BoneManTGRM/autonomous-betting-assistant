from pathlib import Path
import json

import pandas as pd
import streamlit as st

import autonomous_betting_agent.adaptive_learning as adaptive_learning
from autonomous_betting_agent.auto_learning_cycle import run_auto_learning_cycle
from autonomous_betting_agent.dashboard_sync import sync_dashboard_state
from autonomous_betting_agent.full_auto_update import full_update_and_sync
from autonomous_betting_agent.odds_lock_tools import lock_rows, now_utc
from autonomous_betting_agent.pick_hold_store import normalize_workspace_id
from autonomous_betting_agent.profit_guard import add_profit_guard, filter_profit_guard

_original_number_input = st.number_input
if not hasattr(adaptive_learning, '_aba_original_apply_adaptive_learning'):
    adaptive_learning._aba_original_apply_adaptive_learning = adaptive_learning.apply_adaptive_learning
_original_apply_adaptive_learning = adaptive_learning._aba_original_apply_adaptive_learning


def volume_number_input(label, *args, **kwargs):
    text = str(label)
    if text.startswith('Max large-list') or text.startswith('Máximo de filas'):
        kwargs['max_value'] = 1000
        kwargs['value'] = 700
    elif text.startswith('Minimum model probability') or text.startswith('Probabilidad mínima'):
        kwargs['value'] = 0.50
    elif text.startswith('Large-list min learned score') or text.startswith('Puntaje aprendido mínimo'):
        kwargs['value'] = 50.0
    return _original_number_input(label, *args, **kwargs)


def _num(frame: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    if col not in frame.columns:
        return pd.Series(default, index=frame.index, dtype='float64')
    return pd.to_numeric(frame[col], errors='coerce').fillna(default)


def _prob_series(frame: pd.DataFrame, primary: str, fallback: str = 'model_probability_clean') -> pd.Series:
    primary_values = _num(frame, primary, 0.0)
    fallback_values = _num(frame, fallback, 0.0)
    values = primary_values.where(primary_values.gt(0), fallback_values)
    return values.where(values <= 1.0, values / 100.0).clip(0.0, 1.0)


def _implied_from_price(frame: pd.DataFrame) -> pd.Series:
    odds = _num(frame, 'decimal_price', 0.0)
    implied = _num(frame, 'market_implied_probability', 0.0)
    implied = implied.where(implied.gt(0), 1.0 / odds.where(odds.gt(1.0)))
    return implied.replace([float('inf'), -float('inf')], pd.NA).fillna(0.0).clip(0.0, 1.0)


def _recompute_learned_probability_edge(frame: pd.DataFrame) -> pd.DataFrame:
    """Use learned/model probability as the model side and Odds API price as the market side."""
    if frame is None or frame.empty:
        return frame
    out = frame.copy()
    raw_market_prob = _num(out, 'market_implied_probability', 0.0).where(
        _num(out, 'market_implied_probability', 0.0).gt(0), _num(out, 'market_probability', 0.0)
    )
    model_prob = _prob_series(out, 'learned_model_probability')
    market_implied = _implied_from_price(out).where(lambda s: s.gt(0), raw_market_prob)
    odds = _num(out, 'decimal_price', 0.0)
    valid_market = odds.gt(1.0) & market_implied.gt(0.0)

    if 'raw_market_probability' not in out.columns:
        out['raw_market_probability'] = raw_market_prob.round(6)
    out['market_implied_probability'] = market_implied.where(valid_market, pd.NA).round(6)
    out['model_probability'] = model_prob.round(6)
    out['model_probability_clean'] = model_prob.round(6)
    out['model_probability_source'] = 'adaptive_learning_model_probability'
    out.loc[_num(out, 'learned_model_probability', 0.0).le(0), 'model_probability_source'] = 'base_market_probability_no_learning_adjustment'
    out['model_market_edge'] = (model_prob - market_implied).where(valid_market, pd.NA).round(6)
    out['expected_value_per_unit'] = (model_prob * odds - 1.0).where(valid_market, pd.NA).round(6)
    out['edge_status'] = 'computed_from_model_probability_vs_odds_api_price'
    out.loc[~valid_market, 'edge_status'] = 'odds_unavailable_no_edge'
    return out


def _pattern_tier(score: float) -> str:
    if score >= 85:
        return 'A+ Pattern Lock'
    if score >= 75:
        return 'A High Confidence'
    if score >= 65:
        return 'B Strong Pattern'
    if score >= 55:
        return 'C Research Edge'
    return 'D Review Only'


def _pattern_label(probability: float, score: float, patterns: float, adjustment: float) -> str:
    if probability < 0.58 and score >= 65 and patterns >= 2 and adjustment > 0:
        return 'low_confidence_pattern_edge'
    if score >= 75:
        return 'high_confidence_pattern_edge'
    if score >= 55:
        return 'research_pattern_edge'
    return 'no_pattern_edge'


def apply_volume_pattern_points(frame, *args, **kwargs):
    out = _original_apply_adaptive_learning(frame, *args, **kwargs)
    if out is None or out.empty:
        return out
    out = _recompute_learned_probability_edge(out)
    prob = _prob_series(out, 'model_probability')
    base_score = _num(out, 'learned_agent_score', 0.0)
    adjust = _num(out, 'learning_adjustment_score', 0.0)
    patterns = _num(out, 'learning_pattern_count', 0.0)
    edge = _num(out, 'model_market_edge', 0.0)
    ev = _num(out, 'expected_value_per_unit', 0.0)
    signal = _num(out, 'scanner_strength_score', 0.0)
    books = _num(out, 'books', 0.0).where(_num(out, 'books', 0.0).gt(0), _num(out, 'bookmaker_count', 0.0))
    odds = _num(out, 'decimal_price', 0.0)
    odds_band_bonus = pd.Series(0.0, index=out.index)
    odds_band_bonus += odds.between(1.30, 1.89, inclusive='both').astype(float) * 8.0
    odds_band_bonus += odds.between(1.90, 2.24, inclusive='both').astype(float) * 4.0
    odds_band_bonus -= odds.ge(3.00).astype(float) * 15.0
    odds_band_bonus -= odds.le(1.05).astype(float) * 10.0
    book_bonus = books.clip(0, 10) * 0.8
    pattern_bonus = patterns.clip(0, 5) * 4.0 + adjust.clip(-12, 12) * 1.4
    edge_bonus = edge.clip(-0.08, 0.12) * 130.0
    signal_bonus = signal.clip(0, 100) * 0.12
    probability_bonus = prob.clip(0, 1) * 25.0
    audit_penalty = pd.Series(0.0, index=out.index)
    if 'odds_audit_status' in out.columns:
        audit_penalty = out['odds_audit_status'].astype(str).str.lower().ne('pass').astype(float) * 30.0
    pattern_score = (base_score * 0.35 + probability_bonus + edge_bonus + signal_bonus + book_bonus + odds_band_bonus + pattern_bonus - audit_penalty).clip(0, 100).round(3)
    out['pattern_points'] = pattern_score
    out['pattern_confidence_tier'] = pattern_score.map(_pattern_tier)
    out['pattern_edge_label'] = [_pattern_label(float(prob.iloc[i]), float(pattern_score.iloc[i]), float(patterns.iloc[i]), float(adjust.iloc[i])) for i in range(len(out))]
    out['pattern_high_confidence'] = pattern_score.ge(75)
    out['low_confidence_pattern_candidate'] = (prob.lt(0.58) & pattern_score.ge(65) & patterns.ge(2) & adjust.gt(0))
    out = add_profit_guard(out)

    out['agent_decision'] = 'watch_only'
    out.loc[out.get('profit_volume_safe', pd.Series(False, index=out.index)).astype(bool) & pattern_score.ge(55), 'agent_decision'] = 'research_watch'
    out.loc[out.get('profit_balanced_ok', pd.Series(False, index=out.index)).astype(bool) & pattern_score.ge(65) & edge.ge(0.0) & ev.ge(0.0), 'agent_decision'] = 'play_small'
    out.loc[out.get('profit_official_ok', pd.Series(False, index=out.index)).astype(bool) & edge.ge(0.015) & ev.ge(0.015) & pattern_score.ge(75), 'agent_decision'] = 'play_strong'
    out['decision_rank'] = out['agent_decision'].map({'play_strong': 1, 'play_small': 2, 'research_watch': 3, 'watch_only': 4}).fillna(5)

    if 'decision_signals' in out.columns:
        out['decision_signals'] = out['decision_signals'].astype(str) + '; pattern_points_v3; learned_edge_recomputed; nonnegative_ev_decisions; profit_guard_v2'
    return out


def publish_predictor_handoff_to_dashboard(handoff: pd.DataFrame | list[dict], workspace_id: str) -> dict:
    frame = pd.DataFrame(handoff) if isinstance(handoff, list) else handoff
    if frame is None or frame.empty:
        return {'status': 'empty_handoff', 'input_rows': 0, 'locked_rows': 0}
    frame = frame.copy()
    input_rows = int(len(frame))
    if 'lock_ready' in frame.columns:
        frame = frame[frame['lock_ready'].astype(bool)].copy()
    if frame.empty:
        return {'status': 'no_future_lock_ready_rows', 'input_rows': input_rows, 'locked_rows': 0}
    locked = lock_rows(frame, analyst='ABA Signal Pro · Powered by Reparodynamics', max_units=1.0, include_watch=True, strict=False, require_future=True)
    if locked.empty:
        return {'status': 'lock_rows_empty', 'input_rows': input_rows, 'future_rows': int(len(frame)), 'locked_rows': 0}
    if 'proof_status' in locked.columns:
        locked = locked[locked['proof_status'].astype(str).eq('locked_before_start')].copy()
    if locked.empty:
        return {'status': 'no_locked_before_start_rows', 'input_rows': input_rows, 'future_rows': int(len(frame)), 'locked_rows': 0}
    active_id = f'{normalize_workspace_id(workspace_id)}:predictor:{now_utc()}'
    locked['test_window_id'] = normalize_workspace_id(workspace_id)
    locked['ledger_batch_id'] = active_id
    locked['active_list_id'] = active_id
    locked['source_file'] = 'pro_predictor_volume_auto_lock'
    synced = sync_dashboard_state(locked, workspace_id=workspace_id)
    return {
        'status': 'synced',
        'input_rows': input_rows,
        'future_rows': int(len(frame)),
        'locked_rows': int(len(locked)),
        'synced_rows': int(len(synced)),
        'active_list_id': active_id,
    }


def run_predictor_full_update(workspace_id: str, *, api_key_override: str, days_from: int, run_learning_after: bool) -> dict:
    updated, stats = full_update_and_sync(workspace_id=workspace_id, api_key_override=api_key_override, days_from=int(days_from))
    actual_changed = int(stats.get('actual_changed_rows') or 0)
    matched_rows = int(stats.get('matched_rows') or 0)
    status = 'updated' if actual_changed > 0 else ('matched_no_change' if matched_rows > 0 else 'no_updates')
    report = {
        'version': 'predictor-full-auto-update-v3-actual-change-aware',
        'workspace_id': workspace_id,
        'locked_rows': int(stats.get('locked_rows') or len(updated) or 0),
        'status': status,
        'reason': stats.get('reason', 'no_matching_completed_scores'),
        'grading': stats,
        'updated_rows': int(stats.get('updated_rows') or 0),
        'actual_changed_rows': actual_changed,
        'matched_rows': matched_rows,
        'total_result_rows': int(stats.get('total_result_rows') or 0),
        'active_list_identity': stats.get('active_list_identity', {}),
        'sports_checked': stats.get('sports_checked', []),
    }
    if run_learning_after and actual_changed > 0:
        report['learning'] = run_auto_learning_cycle(workspace_id, save_to_github=True)
    return report


AUTO_TEXT = {
    'en': {
        'title': 'Automation / Maintenance: results → learning',
        'caption': 'Use this after picks have been locked. It can update finished wins/losses, save the ledger, and feed new results into learning memory.',
        'workspace': 'Workspace ID', 'days': 'Days back for result sync', 'threshold': 'Match threshold', 'run_learning': 'Run learning after result sync', 'api_key': 'Optional Odds API key override',
        'matcher': 'Active full-auto matcher: V3 actual-change-aware workspace sync. Threshold display: {threshold:.2f}.',
        'find': 'Find & update wins/losses', 'learning_only': 'Run learning update only', 'full_auto': 'Full auto update',
        'result_report': 'Result sync report', 'result_updated': 'Wins/losses updated and dashboard synced.', 'result_status': 'Result sync status: {status} / {reason}', 'download_result': 'Download result sync report', 'result_error': 'Auto Result Sync failed: {error}',
        'learning_report': 'Learning update report', 'learning_updated': 'Learning memory updated.', 'learning_skipped': 'Learning update skipped: {reason}', 'download_learning': 'Download learning report', 'learning_error': 'Auto Learning Cycle failed: {error}',
        'full_report': 'Full auto update report', 'full_updated': 'Results, dashboard sync, and learning update completed where new results were found.', 'full_status': 'Full auto update status: {status} / {reason}', 'download_full': 'Download full auto update report', 'full_error': 'Full auto update failed: {error}',
    },
    'es': {
        'title': 'Automatización / mantenimiento: resultados → aprendizaje',
        'caption': 'Úsalo después de bloquear picks. Puede actualizar ganadas/perdidas finalizadas, guardar el ledger y enviar nuevos resultados a la memoria de aprendizaje.',
        'workspace': 'ID de workspace', 'days': 'Días atrás para sincronizar resultados', 'threshold': 'Umbral de coincidencia', 'run_learning': 'Ejecutar aprendizaje después de sincronizar resultados', 'api_key': 'Clave opcional de Odds API',
        'matcher': 'Matcher full-auto activo: sincronización workspace V3 con cambios reales. Umbral mostrado: {threshold:.2f}.',
        'find': 'Buscar y actualizar ganadas/perdidas', 'learning_only': 'Ejecutar solo actualización de aprendizaje', 'full_auto': 'Actualización automática completa',
        'result_report': 'Reporte de sincronización de resultados', 'result_updated': 'Ganadas/perdidas actualizadas y dashboard sincronizado.', 'result_status': 'Estado de sincronización: {status} / {reason}', 'download_result': 'Descargar reporte de sincronización', 'result_error': 'Falló la sincronización automática de resultados: {error}',
        'learning_report': 'Reporte de actualización de aprendizaje', 'learning_updated': 'Memoria de aprendizaje actualizada.', 'learning_skipped': 'Actualización de aprendizaje omitida: {reason}', 'download_learning': 'Descargar reporte de aprendizaje', 'learning_error': 'Falló el ciclo automático de aprendizaje: {error}',
        'full_report': 'Reporte de actualización automática completa', 'full_updated': 'Resultados, dashboard y aprendizaje completados donde hubo nuevos resultados.', 'full_status': 'Estado de actualización automática completa: {status} / {reason}', 'download_full': 'Descargar reporte automático completo', 'full_error': 'Falló la actualización automática completa: {error}',
    },
}

VOLUME_UI_TEXT = {
    'en': {
        'pattern_mode': 'Pattern Points mode',
        'profit_mode': 'Profit Protection mode',
        'profit_help': 'Volume-safe only blocks obvious bad prices. Balanced and above are stricter for proof/ROI.',
        'dashboard_synced': 'Dashboard proof ledger synced: {rows} locked rows.',
        'dashboard_status': 'Dashboard proof ledger sync: {status}',
    },
    'es': {
        'pattern_mode': 'Modo de puntos de patrón',
        'profit_mode': 'Modo de protección de ganancias',
        'profit_help': 'Volumen seguro solo bloquea precios claramente malos. Balanceado y superiores son más estrictos para prueba/ROI.',
        'dashboard_synced': 'Ledger de prueba del dashboard sincronizado: {rows} filas bloqueadas.',
        'dashboard_status': 'Sincronización del ledger de prueba: {status}',
    },
}


def _ui_lang() -> str:
    candidates = [globals().get('LANG'), st.session_state.get('aba_global_language'), st.session_state.get('pro_predictor_language')]
    for value in candidates:
        text = str(value or '').strip().lower()
        if text.startswith('es') or 'español' in text or 'espanol' in text or 'spanish' in text:
            return 'es'
    return 'en'


def auto_t(key: str, **kwargs) -> str:
    text = AUTO_TEXT.get(_ui_lang(), AUTO_TEXT['en']).get(key, AUTO_TEXT['en'].get(key, key))
    return text.format(**kwargs) if kwargs else text


def volume_ui_t(key: str, **kwargs) -> str:
    text = VOLUME_UI_TEXT.get(_ui_lang(), VOLUME_UI_TEXT['en']).get(key, VOLUME_UI_TEXT['en'].get(key, key))
    return text.format(**kwargs) if kwargs else text


def localized_options(options: list[tuple[str, str]]) -> dict[str, str]:
    if _ui_lang() == 'es':
        return {es: en for en, es in options}
    return {en: en for en, es in options}


def render_predictor_automation_panel() -> None:
    with st.expander(auto_t('title'), expanded=False):
        st.caption(auto_t('caption'))
        workspace_input = st.text_input(auto_t('workspace'), value=st.session_state.get('aba_test_window_id', 'test_01'), key='predictor_auto_workspace')
        workspace_id = normalize_workspace_id(workspace_input)
        st.session_state['aba_test_window_id'] = workspace_id
        cols = st.columns(4)
        days_from = cols[0].number_input(auto_t('days'), min_value=1, max_value=7, value=7, step=1, key='predictor_auto_days')
        threshold = cols[1].number_input(auto_t('threshold'), min_value=0.70, max_value=0.98, value=0.82, step=0.01, key='predictor_auto_threshold')
        run_learning = cols[2].toggle(auto_t('run_learning'), value=True, key='predictor_auto_run_learning')
        api_key = cols[3].text_input(auto_t('api_key'), value='', type='password', key='predictor_auto_api_key')
        st.caption(auto_t('matcher', threshold=float(threshold)))
        actions = st.columns(3)
        if actions[0].button(auto_t('find'), use_container_width=True, key='predictor_auto_result_sync'):
            try:
                report = run_predictor_full_update(workspace_id, api_key_override=api_key, days_from=int(days_from), run_learning_after=bool(run_learning))
                st.subheader(auto_t('result_report'))
                if report.get('status') == 'updated':
                    st.success(auto_t('result_updated'))
                else:
                    st.warning(auto_t('result_status', status=report.get('status'), reason=report.get('reason', 'no reason')))
                st.json(report)
                st.download_button(auto_t('download_result'), json.dumps(report, indent=2, sort_keys=True), file_name='auto_result_sync_report.json', mime='application/json')
            except Exception as exc:
                st.error(auto_t('result_error', error=exc))
        if actions[1].button(auto_t('learning_only'), use_container_width=True, key='predictor_auto_learning'):
            try:
                report = run_auto_learning_cycle(workspace_id, min_new_rows=1, min_total_rows=5, save_to_github=True)
                st.subheader(auto_t('learning_report'))
                if report.get('status') == 'trained':
                    st.success(auto_t('learning_updated'))
                else:
                    st.warning(auto_t('learning_skipped', reason=report.get('reason')))
                st.json(report)
                st.download_button(auto_t('download_learning'), json.dumps(report, indent=2, sort_keys=True), file_name='auto_learning_cycle_report.json', mime='application/json')
            except Exception as exc:
                st.error(auto_t('learning_error', error=exc))
        if actions[2].button(auto_t('full_auto'), type='primary', use_container_width=True, key='predictor_full_auto_update'):
            try:
                report = run_predictor_full_update(workspace_id, api_key_override=api_key, days_from=int(days_from), run_learning_after=True)
                st.subheader(auto_t('full_report'))
                if report.get('status') == 'updated':
                    st.success(auto_t('full_updated'))
                else:
                    st.warning(auto_t('full_status', status=report.get('status'), reason=report.get('reason', 'no reason')))
                st.json(report)
                st.download_button(auto_t('download_full'), json.dumps(report, indent=2, sort_keys=True), file_name='full_auto_update_report.json', mime='application/json')
            except Exception as exc:
                st.error(auto_t('full_error', error=exc))


def _replace_required(source: str, old: str, new: str, label: str) -> str:
    if old not in source:
        st.error(f'Pro Predictor wrapper injection failed: missing anchor {label}. The predictor was stopped before running with partial automation.')
        st.stop()
    return source.replace(old, new, 1)


adaptive_learning.apply_adaptive_learning = apply_volume_pattern_points
st.number_input = volume_number_input
code = Path(__file__).with_name('pro_predictor.py').read_text(encoding='utf-8')
code = _replace_required(code, "latest_event_date = st.date_input(t('latest_date'), value=next_sunday())", "latest_event_date = st.date_input(t('latest_date'), value=date.today() + timedelta(days=14))", 'latest_event_date_14_day_default')
code = _replace_required(code, "min_agent = h3.number_input(t('min_agent'), min_value=0.0, max_value=100.0, value=DEFAULTS['min_agent'], step=1.0)", "min_agent = h3.number_input(t('min_agent'), min_value=0.0, max_value=100.0, value=DEFAULTS['min_agent'], step=1.0)\n    pattern_options = localized_options([('Research learning 55+', 'Investigación aprendizaje 55+'), ('Strong test 65+', 'Prueba fuerte 65+'), ('Official proof 75+', 'Prueba oficial 75+'), ('Elite proof 85+', 'Prueba élite 85+'), ('Low-confidence pattern candidates', 'Candidatos de patrón con baja confianza')])\n    pattern_mode_label = st.selectbox(volume_ui_t('pattern_mode'), list(pattern_options.keys()), index=0)\n    pattern_mode = pattern_options[pattern_mode_label]\n    profit_options = localized_options([('Research no profit guard', 'Investigación sin guardia de ganancias'), ('Volume-safe profit guard', 'Guardia de ganancias volumen-seguro'), ('Balanced ROI guard', 'Guardia ROI balanceada'), ('Official ROI guard', 'Guardia ROI oficial'), ('Elite ROI guard', 'Guardia ROI élite')])\n    profit_mode_labels = list(profit_options.keys())\n    profit_mode_label = st.selectbox(volume_ui_t('profit_mode'), profit_mode_labels, index=1, help=volume_ui_t('profit_help'))\n    profit_mode = profit_options[profit_mode_label]", 'pattern_mode_insert')
code = _replace_required(code, "decisions = decisions[pd.to_numeric(decisions.get('agent_score'), errors='coerce').fillna(0) >= float(min_agent)]", "decisions = decisions[pd.to_numeric(decisions.get('agent_score'), errors='coerce').fillna(0) >= float(min_agent)]\n    decisions = filter_profit_guard(decisions, profit_mode)\n    pp = pd.to_numeric(decisions.get('pattern_points'), errors='coerce').fillna(0)\n    if pattern_mode.startswith('Research'):\n        decisions = decisions[pp >= 55]\n    elif pattern_mode.startswith('Strong'):\n        decisions = decisions[pp >= 65]\n    elif pattern_mode.startswith('Official'):\n        decisions = decisions[pp >= 75]\n    elif pattern_mode.startswith('Elite'):\n        decisions = decisions[pp >= 85]\n    else:\n        decisions = decisions[decisions.get('low_confidence_pattern_candidate', pd.Series(False, index=decisions.index)).astype(bool)]", 'pattern_mode_filter')
code = _replace_required(code, "persist_handoff(decisions=decisions, large=large, handoff=handoff)", "persist_handoff(decisions=decisions, large=large, handoff=handoff)\n    dashboard_sync_report = publish_predictor_handoff_to_dashboard(handoff, str(st.session_state.get('aba_test_window_id', 'test_01') or 'test_01'))\n    st.session_state['predictor_dashboard_sync_report'] = dashboard_sync_report", 'auto_dashboard_sync')
code = _replace_required(code, "st.success(t('saved'))", "st.success(t('saved'))\n    if st.session_state.get('predictor_dashboard_sync_report', {}).get('status') == 'synced':\n        st.success(volume_ui_t('dashboard_synced', rows=st.session_state['predictor_dashboard_sync_report'].get('synced_rows', 0)))\n    else:\n        st.warning(volume_ui_t('dashboard_status', status=st.session_state.get('predictor_dashboard_sync_report', {}).get('status', 'unknown')))", 'auto_dashboard_sync_message')
code = _replace_required(code, "['learned_agent_score', 'agent_score', 'learning_adjustment_score', 'scanner_strength_score', 'model_probability_clean', 'model_market_edge']", "['portfolio_priority_score', 'profit_protection_score', 'pattern_points', 'learned_agent_score', 'agent_score', 'learning_adjustment_score', 'scanner_strength_score', 'model_probability_clean', 'model_market_edge']", 'pattern_sort_columns')
code = _replace_required(code, "'event', 'sport', 'market_type', 'line_point', 'prediction',", "'event', 'sport', 'market_type', 'line_point', 'prediction', 'pattern_points', 'pattern_confidence_tier', 'pattern_edge_label', 'profit_lane', 'profit_guard_status', 'portfolio_priority_score', 'portfolio_group_rank', 'suggested_stake_units', 'profit_protection_score', 'profit_expected_value', 'profit_volume_safe', 'profit_balanced_ok', 'pattern_high_confidence', 'low_confidence_pattern_candidate',", 'pattern_display_columns')
exec(code, globals())
render_predictor_automation_panel()
