from __future__ import annotations
from pathlib import Path
from typing import Any
import pandas as pd
from .odds_lock_tools import client_view, daily_report, lock_status, proof_hash, summarize_locked_picks, update_profit_columns
from .pick_hold_store import load_held_rows, save_held_rows
from .row_normalizer import normalize_frame, result_status, safe_text
REPO_ROOT=Path(__file__).resolve().parents[1]
DEFAULT_LEDGER_PATH=REPO_ROOT/'data'/'odds_lock_pro_ledger.csv'
LOCKED_STORE_KEY='odds_lock_pro_locked_rows'; REFRESH_STORE_KEY='public_proof_dashboard_refresh_rows'; PROOF_REQUIRED_COLUMNS={'proof_id','locked_at_utc'}
def normalize_workspace_id(v:Any)->str:
 t=safe_text(v).strip().lower() or 'default'; c=''.join(x if x.isalnum() or x in {'-','_'} else '_' for x in t); return ('_'.join(p for p in c.split('_') if p) or 'default')[:48]
def persistent_ledger_path(workspace_id:Any='', path:Path=DEFAULT_LEDGER_PATH)->Path:
 w=normalize_workspace_id(workspace_id); return path if w in {'default','shared','main'} else path.with_name(f'{path.stem}_{w}{path.suffix}')
def ensure_data_dir(path:Path=DEFAULT_LEDGER_PATH)->None: path.parent.mkdir(parents=True,exist_ok=True)
def filter_locked_proof_rows(frame):
 raw=pd.DataFrame(frame) if isinstance(frame,list) else frame
 out=update_profit_columns(raw) if raw is not None and not raw.empty else pd.DataFrame()
 if out.empty or not PROOF_REQUIRED_COLUMNS.issubset(out.columns): return pd.DataFrame()
 return out[out['proof_id'].map(safe_text).ne('') & out['locked_at_utc'].map(safe_text).ne('')].copy()
def has_locked_proof_rows(frame)->bool: return not filter_locked_proof_rows(frame).empty
def latest_active_list(frame):
 out=filter_locked_proof_rows(frame)
 if out.empty: return pd.DataFrame()
 for col in ['active_list_id','ledger_batch_id','list_id','source_file']:
  if col in out.columns:
   lab=out[col].map(safe_text); ne=lab[lab.ne('')]
   if not ne.empty:
    sel=out[lab.eq(ne.iloc[-1])].copy()
    if not sel.empty: return sel
 if 'locked_at_utc' in out.columns:
  d=pd.to_datetime(out['locked_at_utc'],errors='coerce',utc=True)
  if d.notna().any(): return out[d.eq(d.max())].copy()
 return out
def merge_ledgers(*frames, active_only:bool=True):
 parts=[]
 for f in frames:
  if f is None: continue
  raw=pd.DataFrame(f) if isinstance(f,list) else f
  if raw is not None and not raw.empty:
   p=filter_locked_proof_rows(raw)
   if not p.empty: parts.append(p)
 if not parts: return pd.DataFrame()
 out=pd.concat(parts,ignore_index=True,sort=False)
 if 'proof_id' in out.columns: out=out.drop_duplicates(subset=['proof_id'],keep='last')
 cols=[c for c in ['event','prediction','event_start_utc','market_type'] if c in out.columns]
 if cols: out=out.drop_duplicates(subset=cols,keep='last')
 return latest_active_list(out) if active_only else filter_locked_proof_rows(out)
def load_persistent_ledger(path:Path=DEFAULT_LEDGER_PATH, workspace_id:Any='', active_only:bool=True):
 disk=pd.DataFrame(); p=persistent_ledger_path(workspace_id,path)
 try:
  if p.exists(): disk=pd.read_csv(p)
 except Exception: pass
 held=load_held_rows(LOCKED_STORE_KEY,workspace_id) or load_held_rows(REFRESH_STORE_KEY,workspace_id)
 return merge_ledgers(disk, held, active_only=active_only)
def save_persistent_ledger(frame,path:Path=DEFAULT_LEDGER_PATH,workspace_id:Any=''):
 out=latest_active_list(frame)
 if out.empty: return pd.DataFrame()
 save_held_rows(LOCKED_STORE_KEY,out,workspace_id); save_held_rows(REFRESH_STORE_KEY,out,workspace_id)
 try:
  p=persistent_ledger_path(workspace_id,path); ensure_data_dir(p); out.to_csv(p,index=False)
 except Exception: pass
 return out
def apply_result_updates(ledger, results): return latest_active_list(ledger), {'updated_rows':0,'matched_by_proof_id':0,'matched_by_event_pick':0,'unmatched_results':0}
def proof_audit_frame(frame):
 locked=latest_active_list(frame); rows=[]
 for r in locked.to_dict('records'):
  h=safe_text(r.get('proof_hash')); rh=proof_hash(r); hs='hash_match' if h and h==rh else 'hash_mismatch'; ls=lock_status(r); au='pass' if hs=='hash_match' and ls=='locked_before_start' else 'review'; rows.append({'proof_id':safe_text(r.get('proof_id')),'event':safe_text(r.get('event')),'prediction':safe_text(r.get('prediction')),'locked_at_utc':safe_text(r.get('locked_at_utc')),'event_start_utc':safe_text(r.get('event_start_utc')),'hash_status':hs,'lock_status':ls,'audit_status':au})
 return pd.DataFrame(rows) if rows else pd.DataFrame(columns=['proof_id','hash_status','lock_status','audit_status'])
def proof_audit_summary(frame):
 a=proof_audit_frame(frame); n=len(a)
 if n==0: return {'proof_rows':0,'hash_match':0,'hash_mismatch':0,'locked_before_start':0,'needs_review':0,'proof_quality_score':0.0}
 hm=int(a['hash_status'].eq('hash_match').sum()); hx=int(a['hash_status'].eq('hash_mismatch').sum()); lb=int(a['lock_status'].eq('locked_before_start').sum()); nr=int(a['audit_status'].eq('review').sum()); return {'proof_rows':n,'hash_match':hm,'hash_mismatch':hx,'locked_before_start':lb,'needs_review':nr,'proof_quality_score':round(50*hm/n+35*lb/n+15*max(0,1-nr/n),2)}
def dashboard_metrics(frame):
 c=latest_active_list(frame); s=summarize_locked_picks(c); s.update(proof_audit_summary(c)); st=c.get('result_status',pd.Series(dtype=str)).astype(str).str.lower() if not c.empty else pd.Series(dtype=str); s['pending_picks']=int(st.isin(['pending','unknown','scheduled','live','','needs_review']).sum()); s['avg_clv_percent']=None; s['beat_close_rate']=None; s['active_list_only']=True; return s
def public_dashboard_table(frame,limit:int=200): return client_view(latest_active_list(frame),public_only=True).head(limit)
def report_card_markdown(frame,**kw):
 m=dashboard_metrics(frame); return f"Record: {m['wins']}-{m['losses']}\nLocked: {m['locked_picks']}"
def report_card_html(frame,**kw): return '<pre>'+report_card_markdown(frame)+'</pre>'
def daily_locked_report(frame,language='English',public_only=True): return daily_report(latest_active_list(frame),language=language,public_only=public_only)
def demo_ledger(): return pd.DataFrame()
