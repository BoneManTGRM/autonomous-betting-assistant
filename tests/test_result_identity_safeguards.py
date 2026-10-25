"""Synthetic prospective result identity regressions; never read saved ledgers."""
import pandas as pd
import pytest
from autonomous_betting_agent import result_grading_v2 as grading
from autonomous_betting_agent import full_auto_update as full

PAIRS = [
 ('Croatia','Panama','Ghana','Croatia'),
 ('Ghana','England','England','Panama'),
 ('Canada','Switzerland','Algeria','Switzerland'),
 ('Sport Recife','Fortaleza','Ponte Preta','Fortaleza'),
 ('Houston Astros','Toronto Blue Jays','Texas Rangers','Toronto Blue Jays'),
 ('Baltimore Orioles','Los Angeles Angels','Athletics','Los Angeles Angels'),
]

def ledger(**changes):
 row=dict(proof_id='SYNTHETIC',locked_at_utc='2026-01-01T00:00:00Z',event='Houston Astros at Toronto Blue Jays',event_start_utc='2026-01-02T01:00:00Z',sport='Baseball',sport_key='baseball_mlb',market_type='h2h',prediction='Toronto Blue Jays',decimal_price=1.8,stake_units=1,result_status='pending')
 row.update(changes);return row

def result(**changes):
 row=dict(event='Houston Astros at Toronto Blue Jays',away_team='Houston Astros',home_team='Toronto Blue Jays',event_start_utc='2026-01-02T01:00:00Z',sport='Baseball',sport_key='baseball_mlb',winner='Toronto Blue Jays',result_source='SYNTHETIC_ONLY')
 row.update(changes);return row

@pytest.mark.parametrize('a,b,c,d',PAIRS)
@pytest.mark.parametrize('outcome',['win','loss','void'])
@pytest.mark.parametrize('different_date',[False,True])
def test_wrong_opponent_never_grades(a,b,c,d,outcome,different_date):
 shared=next(iter({a,b}&{c,d}));other=c if c!=shared else d
 l=ledger(event=f'{a} at {b}',prediction=shared)
 r=result(event=f'{c} at {d}',away_team=c,home_team=d,winner=shared if outcome=='win' else other)
 if outcome=='void':r['result_status']='void'
 if different_date:r['event_start_utc']='2026-02-02T01:00:00Z'
 rows,stats=grading.apply_fuzzy_updates([l],[r]);row=rows.iloc[0]
 assert row['result_status']=='pending'
 assert row['grading_match_status']=='identity_needs_review'
 assert row['review_reason']=='event_identity_mismatch'
 assert not row.get('matched_result_event')
 assert stats['updated_rows']==0

@pytest.mark.parametrize('date',['2026-02-02T01:00:00Z','2026-01-03T01:00:00Z','2026-01-02','2026-01-02T01:00:00','','bad',None])
@pytest.mark.parametrize('outcome',['win','loss','void'])
def test_wrong_or_ambiguous_date_never_grades(date,outcome):
 r=result(event_start_utc=date,winner='Houston Astros' if outcome=='loss' else 'Toronto Blue Jays')
 if outcome=='void':r['result_status']='void'
 rows,_=grading.apply_fuzzy_updates([ledger()],[r]);row=rows.iloc[0]
 assert row['result_status']=='pending'
 assert row['grading_match_status']=='identity_needs_review'
 assert not row.get('matched_result_event')

@pytest.mark.parametrize('outcome',['win','loss','void'])
def test_exact_identity_all_outcomes_still_grade(outcome):
 r=result(winner='Houston Astros' if outcome=='loss' else 'Toronto Blue Jays')
 if outcome=='void':r['result_status']='void'
 rows,_=grading.apply_fuzzy_updates([ledger()],[r])
 assert rows.iloc[0]['result_status']==outcome
 assert rows.iloc[0]['matched_result_source']=='SYNTHETIC_ONLY'

def test_utc_offset_cross_midnight_is_same_date():
 rows,_=grading.apply_fuzzy_updates([ledger()],[result(event_start_utc='2026-01-01T20:00:00-05:00')])
 assert rows.iloc[0]['result_status']=='win'

def test_same_local_date_different_utc_day_rejected():
 rows,_=grading.apply_fuzzy_updates([ledger()],[result(event_start_utc='2026-01-02T23:00:00-05:00')])
 assert rows.iloc[0]['result_status']=='pending'

def test_explicit_alias_and_swapped_pair_allowed():
 rows,_=grading.apply_fuzzy_updates([ledger()],[result(event='Blue Jays at Astros',away_team='Blue Jays',home_team='Astros')])
 assert rows.iloc[0]['result_status']=='win'

@pytest.mark.parametrize('change',[
 {'event':'Texas Rangers at Toronto Blue Jays'},
 {'away_team':'Texas Rangers'},
 {'away_team':'Houston'},
 {'away_team':'Houston Astros Reserves'},
 {'event_start_utc':'2026-02-02T01:00:00Z'},
])
def test_proof_id_cannot_override_identity_conflict(change):
 rows,_=grading.apply_fuzzy_updates([ledger()],[result(proof_id='SYNTHETIC',**change)])
 assert rows.iloc[0]['result_status']=='pending'
 assert not rows.iloc[0].get('matched_result_event')

@pytest.mark.parametrize('old_grade',['win','loss','void'])
@pytest.mark.parametrize('has_receipt',[False,True])
def test_rejected_resolved_preserves_receipt_including_absence(old_grade,has_receipt):
 old=ledger(result_status=old_grade,final_score='OLD SCORE',winner='OLD WINNER',graded_at_utc='OLD TIME')
 if has_receipt:old.update(matched_result_event='OLD EVENT',matched_result_source='OLD SOURCE',grading_match_status='OLD STATUS',grading_match_confidence=.99,best_match_components='OLD COMPONENTS',review_reason='OLD REASON')
 rows,_=grading.apply_fuzzy_updates([old],[result(event_start_utc='2026-02-02T01:00:00Z')],regrade_resolved=True)
 row=rows.iloc[0].to_dict()
 for field in ['result_status','final_score','winner','graded_at_utc','matched_result_event','matched_result_source','grading_match_status','grading_match_confidence','best_match_components','review_reason']:
  if field in old:assert row[field]==old[field]
  else:assert field not in row

@pytest.mark.parametrize('old_receipt',[False,True])
def test_win_protection_restores_receipt_atomically(old_receipt):
 old=ledger(result_status='win',winner='Toronto Blue Jays',final_score='ORIGINAL',graded_at_utc='ORIGINAL')
 if old_receipt:old.update(matched_result_event='OLD EVENT',matched_result_source='OLD SOURCE',grading_match_confidence=.99,grading_match_status='matched')
 proposed=dict(old,result_status='loss',winner='Houston Astros',matched_result_event='NEW EVENT',matched_result_source='NEW SOURCE',grading_match_confidence=.9,grading_match_status='matched',best_match_components='NEW COMPONENTS',review_reason='NEW REASON')
 rows,count=full._protect_existing_wins(pd.DataFrame([old]),pd.DataFrame([proposed]));row=rows.iloc[0].to_dict()
 assert count==1 and row['result_status']=='win' and row['winner']==old['winner']
 for field in ['matched_result_event','matched_result_source','grading_match_confidence','grading_match_status','best_match_components','review_reason']:
  if field in old:assert row[field]==old[field]
  else:assert field not in row

def test_default_resolved_skip_unchanged():
 old=ledger(result_status='win',matched_result_event='OLD EVENT')
 rows,stats=grading.apply_fuzzy_updates([old],[result()])
 assert rows.iloc[0]['matched_result_event']=='OLD EVENT'
 assert stats['skipped_resolved']==1

def test_manual_grade_override_does_not_get_new_receipt():
 old=ledger(result_status='win',manual_grade='win',matched_result_event='OLD EVENT',winner='Toronto Blue Jays')
 rows,_=grading.apply_fuzzy_updates([old],[result(winner='Houston Astros')],regrade_resolved=True)
 assert rows.iloc[0]['result_status']=='win'
 assert rows.iloc[0]['matched_result_event']=='OLD EVENT'
 assert rows.iloc[0]['winner']=='Toronto Blue Jays'

@pytest.mark.parametrize('field,left,right',[
 ('sport','Baseball','Soccer'),('sport_key','baseball_mlb','soccer_epl'),
 ('event_id','event-1','event-2'),('game_id','game-1','game-2'),('fixture_id','fixture-1','fixture-2'),
])
@pytest.mark.parametrize('outcome',['win','loss','void'])
def test_contradictory_sport_or_ids_with_same_proof_id_rejected(field,left,right,outcome):
 l=ledger(**{field:left})
 r=result(proof_id='SYNTHETIC',**{field:right})
 if outcome=='loss':r['winner']='Houston Astros'
 if outcome=='void':r['result_status']='void'
 rows,_=grading.apply_fuzzy_updates([l],[r])
 assert rows.iloc[0]['result_status']=='pending'
 assert rows.iloc[0]['grading_match_status']=='identity_needs_review'
 assert not rows.iloc[0].get('matched_result_event')

@pytest.mark.parametrize('outcome',['win','loss','void'])
def test_utc_equivalent_offset_all_outcomes_equal(outcome):
 r=result(event_start_utc='2026-01-01T20:00:00-05:00')
 if outcome=='loss':r['winner']='Houston Astros'
 if outcome=='void':r['result_status']='void'
 rows,_=grading.apply_fuzzy_updates([ledger()],[r])
 assert rows.iloc[0]['result_status']==outcome

@pytest.mark.parametrize('reverse',[False,True])
def test_conflicting_results_defer_regardless_of_order(reverse):
 candidates=[result(winner='Toronto Blue Jays'),result(winner='Houston Astros')]
 if reverse:candidates.reverse()
 rows,stats=grading.apply_fuzzy_updates([ledger()],candidates)
 assert rows.iloc[0]['result_status']=='pending'
 assert rows.iloc[0]['review_reason']=='conflicting_result_evidence'
 assert stats['updated_rows']==0

@pytest.mark.parametrize('outcome',['win','loss','void'])
def test_same_city_distinct_teams_do_not_create_false_win(outcome):
 l=ledger(event='Los Angeles Dodgers at Los Angeles Angels',prediction='Los Angeles Dodgers')
 r=result(event=l['event'],away_team='Los Angeles Dodgers',home_team='Los Angeles Angels',winner='Los Angeles Dodgers' if outcome=='win' else 'Los Angeles Angels')
 if outcome=='void':r['result_status']='void'
 rows,_=grading.apply_fuzzy_updates([l],[r])
 assert rows.iloc[0]['result_status']==outcome

@pytest.mark.parametrize('outcome',['win','loss','void'])
def test_unidentified_selected_team_never_grades(outcome):
 r=result()
 if outcome=='void':r['result_status']='void'
 rows,_=grading.apply_fuzzy_updates([ledger(prediction='Toronto')],[r])
 assert rows.iloc[0]['result_status']=='pending'

RECEIPT_FIELDS=['result_source_name','result_source_url','grade_confidence','graded_by','result_source','resolved_at_utc']
@pytest.mark.parametrize('present',[False,True])
def test_protected_source_receipt_and_absence(present):
 old=ledger(result_status='win',profit_units=7.25)
 if present:old.update({field:'ORIGINAL' for field in RECEIPT_FIELDS})
 proposed=dict(old,result_status='loss',profit_units=-1,**{field:'NEW' for field in RECEIPT_FIELDS})
 rows,count=full._protect_existing_wins(pd.DataFrame([old]),pd.DataFrame([proposed]))
 row=rows.iloc[0].to_dict()
 assert count==1 and row['profit_units']==7.25
 for field in RECEIPT_FIELDS:
  if present:assert row[field]=='ORIGINAL'
  else:assert field not in row

@pytest.mark.parametrize('status',['pending','win','loss','void'])
def test_rejected_raw_profit_is_not_normalized(status):
 old=ledger(result_status=status,profit_units=7.25,result_source_url='ORIGINAL')
 rows,_=grading.apply_fuzzy_updates([old],[result(event_start_utc='2026-02-02T01:00:00Z')],regrade_resolved=True)
 assert rows.iloc[0]['profit_units']==7.25
 assert rows.iloc[0]['result_source_url']=='ORIGINAL'
 assert not any(str(k).startswith('__aba_result_receipt_index') for k in rows.columns)

@pytest.mark.parametrize('lock',['manual_grade','verified_grade','verified_result'])
def test_same_outcome_manual_lock_preserves_raw_receipt(lock):
 old=ledger(result_status='win',profit_units=7.25,matched_result_event='HUMAN EVENT',matched_result_source='HUMAN SOURCE',graded_at_utc='HUMAN TIME',**{lock:'win'})
 rows,stats=grading.apply_fuzzy_updates([old],[result()],regrade_resolved=True)
 for field in ['profit_units','matched_result_event','matched_result_source','graded_at_utc',lock]:assert rows.iloc[0][field]==old[field]
 assert stats['updated_rows']==0

@pytest.mark.parametrize('left,right',[
 ({'sport':'Baseball','sport_key':''},{'sport':'','sport_key':'soccer'}),
 ({'sport':'Soccer','sport_key':'baseball_mlb'},{'sport':'Baseball','sport_key':'baseball_mlb'}),
 ({'sport':'','sport_key':''},{'sport':'Baseball','sport_key':'baseball_mlb'}),
])
def test_cross_column_or_unverified_sport_defers(left,right):
 rows,_=grading.apply_fuzzy_updates([ledger(**left)],[result(**right)])
 assert rows.iloc[0]['result_status']=='pending'
 assert rows.iloc[0]['review_reason']=='event_sport_unverified'

@pytest.mark.parametrize('namespace,reason',[
 ('same','event_id_mismatch'),('different','event_id_namespace_unverified'),('','event_id_namespace_unverified')])
def test_id_namespace_reason_does_not_guess_provider(namespace,reason):
 l=ledger(event_id='one',event_id_namespace='odds' if namespace else '')
 r=result(event_id='two',event_id_namespace='odds' if namespace=='same' else ('espn' if namespace else ''))
 rows,_=grading.apply_fuzzy_updates([l],[r])
 assert rows.iloc[0]['result_status']=='pending'
 assert rows.iloc[0]['review_reason']==reason


def test_cross_alias_event_ids_share_namespace_but_conflict():
 rows,_=grading.apply_fuzzy_updates([ledger(event_id='one',id_namespace='odds')],[result(game_id='two',id_namespace='odds')])
 assert rows.iloc[0]['result_status']=='pending'
 assert rows.iloc[0]['review_reason']=='event_id_mismatch'

def test_explicit_competition_contradiction_with_blank_sport_keys():
 rows,_=grading.apply_fuzzy_updates([ledger(sport='NBA',sport_key='')],[result(sport='WNBA',sport_key='')])
 assert rows.iloc[0]['result_status']=='pending'

@pytest.mark.parametrize('suffix,grade',[('-1.5','win'),('+1.5','win'),('-4','void'),('-4.5','loss')])
def test_spread_line_suffix_is_not_part_of_team_name(suffix,grade):
 l=ledger(market_type='spread',prediction='Toronto Blue Jays '+suffix,line_point=float(suffix))
 rows,_=grading.apply_fuzzy_updates([l],[result(home_score=6,away_score=2)])
 assert rows.iloc[0]['result_status']==grade

def test_conflicting_spread_suffix_and_line_defer():
 rows,_=grading.apply_fuzzy_updates([ledger(market_type='spread',prediction='Toronto Blue Jays -1.5',line_point=1.5)],[result(home_score=6,away_score=2)])
 assert rows.iloc[0]['result_status']=='pending'

def test_missing_original_proof_id_still_protects_win_after_normalization():
 old=ledger(result_status='win',profit_units=7.25,matched_result_event='ORIGINAL')
 old.pop('proof_id')
 proposed,_=grading.apply_fuzzy_updates([old],[result(winner='Houston Astros')],regrade_resolved=True)
 rows,count=full._protect_existing_wins(pd.DataFrame([old]),proposed)
 assert count==1
 assert rows.iloc[0]['result_status']=='win'
 assert rows.iloc[0]['profit_units']==7.25
 assert rows.iloc[0]['matched_result_event']=='ORIGINAL'

@pytest.mark.parametrize('reverse',[False,True])
def test_colliding_raw_fallback_identity_preserves_all_original_receipts(reverse):
 a=ledger(result_status='win',profit_units=7.25,matched_result_source='SOURCE A',bookmaker='BOOK A')
 a.pop('proof_id')
 b=dict(a,profit_units=8.25,matched_result_source='SOURCE B',bookmaker='BOOK B',decimal_price=2.0)
 originals=[a,b]
 if reverse:originals.reverse()
 proposed,_=grading.apply_fuzzy_updates(originals,[result(winner='Houston Astros')],regrade_resolved=True)
 rows,_=full._protect_existing_wins(pd.DataFrame(originals),proposed)
 assert rows.to_dict('records')==originals

@pytest.mark.parametrize('reverse',[False,True])
def test_full_auto_colliding_originals_defers_before_fetch_or_write(monkeypatch,reverse):
 a=ledger(result_status='win',profit_units=7.25,matched_result_source='SOURCE A');a.pop('proof_id')
 b=dict(a,profit_units=8.25,matched_result_source='SOURCE B')
 originals=[a,b]
 if reverse:originals.reverse()
 monkeypatch.setattr(full,'load_persistent_ledger',lambda **kw:pd.DataFrame(originals))
 def forbidden(*args,**kw):raise AssertionError('ambiguous raw originals must not fetch or persist')
 monkeypatch.setattr(full,'fetch_completed_scores_for_ledger',forbidden)
 monkeypatch.setattr(full,'sync_dashboard_state',forbidden)
 rows,stats=full.full_update_and_sync(workspace_id='SYNTHETIC')
 assert rows.to_dict('records')==originals
 assert stats['reason']=='ambiguous_original_identity_needs_review'
 assert not stats['dashboard_synced']

@pytest.mark.parametrize('reverse',[False,True])
def test_direct_grader_defers_raw_collision_before_dedup(reverse):
 a=ledger(result_status='win',profit_units=7.25,matched_result_source='SOURCE A');a.pop('proof_id')
 b=dict(a,profit_units=8.25,matched_result_source='SOURCE B')
 originals=[a,b]
 if reverse:originals.reverse()
 rows,stats=grading.apply_fuzzy_updates(originals,[result(winner='Houston Astros')],regrade_resolved=True)
 assert rows.to_dict('records')==originals
 assert stats['reason']=='ambiguous_original_identity_needs_review'

def test_explicit_proof_ids_do_not_cross_restore_receipts():
 originals=[ledger(proof_id='ONE',result_status='win',profit_units=7.25),ledger(proof_id='TWO',result_status='win',profit_units=8.25)]
 proposed=[dict(row,result_status='loss',profit_units=-1) for row in reversed(originals)]
 rows,count=full._protect_existing_wins(pd.DataFrame(originals),pd.DataFrame(proposed))
 assert count==2
 assert {row['proof_id']:row['profit_units'] for row in rows.to_dict('records')}=={'ONE':7.25,'TWO':8.25}

@pytest.mark.parametrize('old_profit,should_sync',[(7.25,False),(.8,True)])
def test_full_auto_mixed_batch_preflight_prevents_receipt_mutation(monkeypatch,old_profit,should_sync):
 from autonomous_betting_agent.commercial_platform_tools import filter_locked_proof_rows
 old=ledger(proof_id='OLD',result_status='win',profit_units=old_profit,matched_result_event='HUMAN EVENT',matched_result_source='HUMAN',manual_grade='win')
 new=ledger(proof_id='NEW',prediction='Houston Astros')
 # Canonical old frame establishes all optional empty fields; deliberately preserve profit.
 old=filter_locked_proof_rows(pd.DataFrame([old])).iloc[0].to_dict();old['profit_units']=old_profit
 originals=pd.DataFrame([old,new])
 monkeypatch.setattr(full,'load_persistent_ledger',lambda **kw:originals.copy())
 monkeypatch.setattr(full,'get_api_key',lambda *a:'')
 monkeypatch.setattr(full,'fetch_completed_scores_for_ledger',lambda *a,**kw:(pd.DataFrame([result(winner='Houston Astros')]),[{'status':'ok'}]))
 calls=[]
 def sync(frame,**kw):
  calls.append(frame.copy())
  assert should_sync,'no persistence/session side effects allowed on unsafe preflight'
  return filter_locked_proof_rows(frame)
 monkeypatch.setattr(full,'sync_dashboard_state',sync)
 rows,stats=full.full_update_and_sync(workspace_id='SYNTHETIC')
 assert bool(calls)==should_sync
 if not should_sync:
  assert stats['reason']=='retained_receipt_normalization_needs_review'
  assert not stats['dashboard_synced'] and stats['updated_rows']==0
  assert rows.iloc[0]['profit_units']==7.25
  assert rows.iloc[1]['result_status']=='pending'
 else:
  assert stats['dashboard_synced']
  assert rows.iloc[0]['matched_result_event']=='HUMAN EVENT'
  assert rows.iloc[1]['result_status']=='win'

def test_default_persistent_wrapper_also_defers_unsafe_receipt(monkeypatch):
 old=pd.DataFrame([ledger(result_status='win',profit_units=7.25)])
 monkeypatch.setattr(grading,'load_persistent_ledger',lambda:old.copy())
 def forbidden(*a,**kw):raise AssertionError('must not save mutated receipt')
 monkeypatch.setattr(grading,'save_persistent_ledger',forbidden)
 rows,stats=grading.grade_persistent_with_fuzzy([result()])
 assert rows.iloc[0]['profit_units']==7.25
 assert stats['persisted'] is False
 assert stats['updated_rows']==0
