from __future__ import annotations
from dataclasses import asdict,is_dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import math,re
from typing import Any,Iterable,Mapping
from zipfile import ZipFile,ZIP_DEFLATED
from PIL import Image,ImageDraw,ImageEnhance,ImageFilter,ImageFont

PAGE_WIDTH=1080; PAGE_HEIGHT=1620; MAGAZINE_STYLE_VERSION='premium_v3_brand_layer'
SAFETY_FOOTER='Analytics only. Results are not guaranteed. Use responsible sizing.'
ASSET_DIRS=(Path('assets/team_logos'),Path('assets/report_logos'),Path('assets/licensed_logos'))
PALETTE=((184,83,28),(20,72,132),(18,112,94),(104,57,142),(140,42,91),(48,99,70))
NO_VERIFIED='No verified data available'; NOT_PROVIDED='Not provided'

def _row(v:Any)->Mapping[str,Any]:
    if isinstance(v,Mapping): return v
    if is_dataclass(v): return asdict(v)
    if hasattr(v,'to_dict'):
        d=v.to_dict(); return d if isinstance(d,Mapping) else {}
    return getattr(v,'__dict__',{}) or {}
def _bad(v:Any)->bool:
    if v is None: return True
    if isinstance(v,float) and math.isnan(v): return True
    return str(v).strip().lower() in {'','nan','none','null','n/a','na','nat'}
def _text(r,*keys,default=''):
    d=_row(r)
    for k in keys:
        v=d.get(k)
        if not _bad(v): return str(v).strip()
    return default
def _num(r,*keys):
    for k in keys:
        v=_row(r).get(k)
        if _bad(v): continue
        try: return float(str(v).replace('%','').replace(',',''))
        except Exception: pass
    return None
def _font(n,b=False):
    names=('DejaVuSansCondensed-Bold.ttf','DejaVuSans-Bold.ttf') if b else ('DejaVuSansCondensed.ttf','DejaVuSans.ttf')
    for name in names:
        try: return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/'+name,n)
        except Exception: pass
    return ImageFont.load_default()
def _seed(r):
    d=_row(r); return int(sha256('|'.join(str(d.get(k,'')) for k in ('sport','home_team','away_team','prediction','event_start_utc','event')).encode()).hexdigest()[:16],16)
def _color(s,n=0): return PALETTE[int(sha256(f'{s}|{n}'.encode()).hexdigest()[:8],16)%len(PALETTE)]
def _parse(c,f): return tuple(int(str(c)[i:i+2],16) for i in (1,3,5)) if re.fullmatch(r'#[0-9A-Fa-f]{6}',str(c or '')) else f
def _colors(r,a,b):
    d=_row(r); return _parse(d.get('team_a_color') or d.get('away_team_color') or d.get('primary_color'),_color(a,1)),_parse(d.get('team_b_color') or d.get('home_team_color') or d.get('secondary_color'),_color(b,2))
def _game(r): return _text(r,'event','game','event_name','matchup',default='Unknown Game')
def _teams(r):
    home=_text(r,'home_team','team_a','team1'); away=_text(r,'away_team','team_b','team2')
    if home and away: return away,home
    g=_game(r)
    for sep in (' at ',' vs ',' v ',' VS ',' @ '):
        if sep in g:
            a,b=g.split(sep,1); return a.strip(),b.strip()
    return _text(r,'team',default='Team A'),_text(r,'opponent',default='Team B')
def _pick(r): return _text(r,'prediction','exact_bet','pick','selection','recommended_action','consumer_action',default=NOT_PROVIDED)
def _pct(v):
    if v is None: return NO_VERIFIED
    v=v/100 if abs(v)>1 else v; return f'{v:.0%}'
def _edge(v):
    if v is None: return NO_VERIFIED
    v=v/100 if abs(v)>1 else v; return f'{v:+.1%}'
def _fmt(v,kind='text'):
    if _bad(v): return NO_VERIFIED
    try:
        n=float(str(v).replace('%','').replace(',',''))
        if kind=='odds': return f'{n:.3g}'
        if kind=='ev': return f'{n:+.3f}' if abs(n)<1 else f'{n:+.2f}'
    except Exception: pass
    return str(v).strip()
def sanitize_image_filename(value:str,suffix:str='',extension:str='png')->str:
    c=re.sub(r'[^A-Za-z0-9]+','_',str(value or 'magazine').lower()).strip('_') or 'magazine'; s=re.sub(r'[^A-Za-z0-9]+','_',str(suffix or '').lower()).strip('_'); ext=(extension or 'png').lstrip('.')
    return f'{c+"_"+s if s else c}.{ext}'
def pick_full_page_filename(pick:Any,index:int,extension:str='png')->str: return sanitize_image_filename(f'pick_{index+1:02d}_{_game(pick)}','full_page',extension)
def _wrap(d,t,f,w,m=2):
    words=str(t or '').replace(chr(10),' ').split(); out=[]; cur=''
    for word in words:
        trial=word if not cur else cur+' '+word
        if d.textbbox((0,0),trial,font=f)[2]<=w: cur=trial
        else:
            if cur: out.append(cur)
            cur=word
            if len(out)>=m: break
    if cur and len(out)<m: out.append(cur)
    if len(out)==m and len(' '.join(out).split())<len(words): out[-1]=out[-1].rstrip('.,;:')+'...'
    return out
def _txt(d,x,y,t,f,fill,w,m=2,gap=6):
    for line in _wrap(d,t,f,w,m): d.text((x,y),line,font=f,fill=fill); y+=f.size+gap
    return y
def _split(v):
    if _bad(v): return []
    nl=chr(10); return [p.strip(' -•') for p in str(v).replace('•',nl).replace(';',nl).replace('|',nl).split(nl) if p.strip(' -•')]
def _src(s,t): return f'{t} · Source: {s}'
def _items(r,specs,fb,lim):
    out=[]
    for keys,label,src in specs:
        v=_text(r,*keys)
        if v: out += [_src(src,f'{label}: {p}') for p in (_split(v) or [v])]
    return (out or [fb])[:lim]
def _why(r):
    out=[_src('Agent Model',p) for p in _split(_text(r,'why_bullets','why_pick','analysis_summary','reason','explanation'))[:2]]
    vals=(('Model probability',_pct(_num(r,'learned_model_probability','model_probability_clean','model_probability','final_probability')),'Agent Model'),('Market probability',_pct(_num(r,'market_probability','market_implied_probability')),'Odds API'),('Measured edge',_edge(_num(r,'model_market_edge','edge')),'Agent Model'),('Expected value',_fmt(_text(r,'expected_value_per_unit','profit_expected_value','expected_value','ev'),'ev'),'Agent Model'),('Available odds',_fmt(_text(r,'decimal_price','odds_at_pick','best_price','odds'),'odds'),'Odds API'))
    for lab,val,src in vals:
        if val and val!=NO_VERIFIED: out.append(_src(src,f'{lab}: {val}'))
    return out[:4] or [_src('Agent Model',NOT_PROVIDED)]
def _evidence(r): return _items(r,(((('odds_source','data_source'),'Odds source','Odds API')),((('bookmaker','sportsbook'),'Sportsbook','Odds API')),((('configured_api_sources',),'Configured APIs','Agent Model')),((('api_sources_used',),'APIs used','Agent Model')),((('api_coverage_percent',),'API coverage','Agent Model'))),_src('Agent Model','Evidence not provided'),3)
def _team(r): return _items(r,(((('home_team_snapshot','team_a_snapshot','sports_context_summary'),'Team snapshot','SportsDataIO')),((('away_team_snapshot','team_b_snapshot'),'Team snapshot','SportsDataIO')),((('api_football_context_status',),'Football context','API-Football')),((('newsapi_context_summary',),'News context','NewsAPI'))),_src('Agent Model','Data not available from uploaded row'),3)
def _players(r): return _items(r,(((('injury_report','injuries','lineup_status','injury_source_reason'),'Roster note','SportsDataIO')),((('sportsdataio_injuries_status',),'Roster status','SportsDataIO')),((('key_players','players','participant_notes'),'Participants','Agent Model'))),_src('SportsDataIO','Player data not available in uploaded row'),2)
def _risk(r): return _items(r,(((('why_lose','risk_reason','hidden_risk'),'Risk note','Agent Model')),((('risk','risk_level','risk_label','profit_guard_status'),'Risk status','Agent Model')),((('weather_flag','weather_reason','weather_bet_adjustment'),'Weather context','WeatherAPI')),((('injury_risk_score','injury_source_reason'),'Roster context','SportsDataIO'))),_src('Agent Model','Use conservative sizing.'),2)
def _match(r): return _items(r,(((('matchup_note','matchup_notes','head_to_head','h2h'),'Matchup','Agent Model')),((('venue_note','weather_location','venue_source'),'Venue','WeatherAPI')),((('sports_context_summary',),'Sports context','SportsDataIO'))),_src('Agent Model','Context unavailable from current feed'),2)
def _chain(r): return [_src('Agent Model',p) for p in _split(_text(r,'chain_notes','main_read','add_on_legs','parlay_notes'))[:2]] or [_src('Agent Model','Better as individual straight analysis unless another verified edge exists.')]
def _rec(r): return _text(r,'final_decision','agent_decision','recommendation','consumer_action','recommended_action',default='research_only'),_text(r,'final_explanation','action_reason','recommendation_reason','decision_reasons',default='Use only if the line remains playable and key news does not change.')
def _resample(): return getattr(getattr(Image,'Resampling',Image),'LANCZOS')
def _load(v):
    try:
        if isinstance(v,(bytes,bytearray)): return Image.open(BytesIO(v)).convert('RGBA')
        if isinstance(v,Image.Image): return v.convert('RGBA')
    except Exception: return None
    return None
def _cover(im,size):
    w,h=size; sc=max(w/max(1,im.width),h/max(1,im.height)); r=im.resize((max(1,int(im.width*sc)),max(1,int(im.height*sc))),_resample()); x=max(0,(r.width-w)//2); y=max(0,(r.height-h)//2); return r.crop((x,y,x+w,y+h))
def _contain(im,size):
    r=im.copy(); r.thumbnail(size,_resample()); return r
def _base(a,b):
    img=Image.new('RGBA',(PAGE_WIDTH,PAGE_HEIGHT),(244,236,211,255)); d=ImageDraw.Draw(img,'RGBA')
    d.rectangle((0,0,PAGE_WIDTH,92),fill=(13,17,22)); d.rectangle((0,92,PAGE_WIDTH,138),fill=(255,250,233,240)); d.ellipse((-240,60,420,520),fill=(*a,18)); d.ellipse((720,70,1280,560),fill=(*b,18)); return img
def _apply_bg(base,bg=None,mode='watermark',opacity=.12):
    im=_load(bg); mode=str(mode or 'watermark').lower()
    if im is None or mode=='none': return base
    out=base.convert('RGBA'); op=max(0,min(1,float(opacity if opacity is not None else .12)))
    if mode=='header_only':
        crop=_cover(im,(PAGE_WIDTH,315)).filter(ImageFilter.GaussianBlur(.8)); crop=ImageEnhance.Brightness(crop).enhance(.68); crop.putalpha(int(255*max(op,.25))); layer=Image.new('RGBA',out.size,(0,0,0,0)); layer.alpha_composite(crop,(0,92)); out.alpha_composite(layer)
    elif mode=='full_page':
        full=_cover(im,out.size).filter(ImageFilter.GaussianBlur(1.1)); full=ImageEnhance.Color(full).enhance(.45); full.putalpha(int(255*min(op,.22))); out.alpha_composite(full); ImageDraw.Draw(out,'RGBA').rectangle((0,0,PAGE_WIDTH,PAGE_HEIGHT),fill=(244,236,211,115))
    else:
        wm=_contain(im,(760,760)).filter(ImageFilter.GaussianBlur(.4)); wm=ImageEnhance.Color(wm).enhance(.55); wm.putalpha(int(255*min(op,.20))); out.alpha_composite(wm,((PAGE_WIDTH-wm.width)//2,165))
    return out
def _apply_logo(img,logo=None,mode='header',opacity=1.0):
    lg=_load(logo); mode=str(mode or 'header').lower()
    if lg is None or mode=='none': return
    op=max(0,min(1,float(opacity if opacity is not None else 1.0)))
    if op<=0: return
    if mode=='watermark': mark=_contain(lg,(430,260)); mark.putalpha(int(255*min(op,.18))); img.alpha_composite(mark,(PAGE_WIDTH-mark.width-54,170))
    else: mark=_contain(lg,(170,58)); mark.putalpha(int(255*op)); img.alpha_composite(mark,(670,17))
def _initials(s):
    p=re.findall(r'[A-Za-z0-9]+',str(s or '').upper()); return ''.join(x[0] for x in p[:3]) or 'TM'
def _badge(d,x,y,w,team,c):
    d.rounded_rectangle((x,y,x+w,y+72),radius=12,fill=(15,19,26,245),outline=c,width=3); d.ellipse((x+16,y+14,x+60,y+58),fill=c,outline=(255,248,230),width=2); d.text((x+30,y+22),_initials(team)[:2],font=_font(19,True),fill='white'); _txt(d,x+78,y+20,team.upper(),_font(25,True),(255,248,230),w-92,1)
def _panel(d,x,y,w,h,title,c):
    d.rounded_rectangle((x,y,x+w,y+h),radius=12,fill=(255,248,229,244),outline=(15,19,26),width=3); d.rounded_rectangle((x,y,x+w,y+44),radius=10,fill=c); d.text((x+16,y+11),title.upper(),font=_font(21,True),fill=(255,249,232))
def _bul(d,x,y,items,w,n,c,fs=18):
    f=_font(fs)
    for item in items[:n]:
        d.ellipse((x,y+8,x+10,y+18),fill=c)
        for line in _wrap(d,item,f,w-28,2): d.text((x+24,y),line,font=f,fill=(19,23,29)); y+=fs+5
        y+=7
def _section(d,x,y,w,h,title,items,c,n=3,fs=18): _panel(d,x,y,w,h,title,c); _bul(d,x+22,y+62,items,w-44,n,c,fs)
def _metric(d,x,y,w,label,val,c):
    d.rectangle((x,y,x+w,y+82),fill=(13,17,22),outline=(225,216,192)); d.text((x+10,y+9),label.upper(),font=_font(15,True),fill=(230,222,202)); fill=(56,205,92) if label.lower() in {'conf','edge','ev'} else (255,248,232); _txt(d,x+10,y+35,val,_font(22,True),fill,w-18,1)

def render_full_pick_magazine_page(pick:Any,background_image:Any=None,report_name:str|None=None,page_number:int=1,total_pages:int=1,logo_image:Any=None,background_mode:str='watermark',logo_mode:str='header',background_opacity:float=.12,logo_opacity:float=1.0)->Image.Image:
    away,home=_teams(pick); ca,cb=_colors(pick,away,home); img=_apply_bg(_base(ca,cb),background_image,background_mode,background_opacity).convert('RGBA'); d=ImageDraw.Draw(img,'RGBA')
    black=(13,17,22); cream=(255,248,230); green=(56,205,92); sport=_text(pick,'sport','league',default='Sport N/A'); source=_text(pick,'odds_source','bookmaker','sportsbook',default='Agent row'); report=report_name or 'Full Pick Magazine'; date=_text(pick,'report_date','event_date',default=NOT_PROVIDED)
    d.rectangle((18,14,268,72),fill=ca); d.text((34,30),'ABA SIGNAL PRO',font=_font(28,True),fill='white'); d.text((300,31),'DAILY SPORTS ANALYSIS',font=_font(27,True),fill=cream); _apply_logo(img,logo_image,logo_mode,logo_opacity); d.rounded_rectangle((846,14,PAGE_WIDTH-18,72),radius=6,fill=cream); d.text((892,31),f'PAGE {page_number} OF {total_pages}',font=_font(22,True),fill=black)
    d.text((28,106),f'REPORT: {report} | SOURCE: {source} | DATE: {date}',font=_font(18,True),fill=black); d.rounded_rectangle((872,94,PAGE_WIDTH-24,144),radius=8,fill=cb); d.text((898,108),sport.upper()[:15],font=_font(21,True),fill='white')
    d.rounded_rectangle((24,162,PAGE_WIDTH-24,424),radius=18,fill=(255,248,229,242),outline=black,width=3); d.text((48,184),away.upper(),font=_font(58,True),fill=ca); d.text((48,258),'AT',font=_font(34,True),fill=black); d.text((128,252),home.upper(),font=_font(58,True),fill=cb); _badge(d,48,332,462,away,ca); _badge(d,552,332,462,home,cb)
    d.rectangle((48,438,446,488),fill=black); d.text((64,450),f'{sport} ANALYSIS'.upper()[:30],font=_font(23,True),fill=cream); _txt(d,472,443,_src('Agent Model',_text(pick,'game_summary','preview_summary','short_reason','decision_reasons',default=NOT_PROVIDED)),_font(19),black,550,2)
    metrics=(('Pick',_pick(pick),ca),('Odds',_fmt(_text(pick,'decimal_price','odds_at_pick','best_price','odds'),'odds'),cb),('Conf',_pct(_num(pick,'learned_model_probability','model_probability_clean','model_probability','final_probability')),green),('Edge',_edge(_num(pick,'model_market_edge','edge')),green),('EV',_fmt(_text(pick,'expected_value_per_unit','profit_expected_value','expected_value','ev'),'ev'),green),('Units',_text(pick,'recommended_stake_units','suggested_stake_units',default=NOT_PROVIDED),cb),('Risk',_text(pick,'risk','risk_level','risk_label','profit_guard_status','weather_flag','injury_risk_score',default=NO_VERIFIED),cb))
    x=24
    for (lab,val,c),w in zip(metrics,[246,118,118,118,118,118,218]): _metric(d,x,516,w,lab,val,c); x+=w
    _section(d,24,634,340,274,'WHY WE PICKED IT',_why(pick),ca,4,18); _section(d,24,926,340,216,'PRO BETTOR EVIDENCE',_evidence(pick),cb,3,17); _section(d,388,634,668,274,'TEAM SNAPSHOTS',_team(pick),cb,3,18); _section(d,388,926,668,216,'PLAYER / INJURY NOTES',_players(pick),cb,2,17); _section(d,24,1166,330,166,'RISK DESK',_risk(pick),ca,2,16); _section(d,376,1166,330,166,'MATCHUP NOTES',_match(pick),cb,2,16); _section(d,728,1166,328,166,'CHAIN BETTING NOTES',_chain(pick),cb,2,16)
    action,explain=_rec(pick); fy=1360; d.rounded_rectangle((24,fy,PAGE_WIDTH-24,PAGE_HEIGHT-58),radius=14,fill=black,outline=ca,width=4); d.rectangle((24,fy,260,PAGE_HEIGHT-58),fill=ca); d.text((42,fy+28),'FINAL',font=_font(27,True),fill='white'); d.text((42,fy+66),'RECOMMENDATION',font=_font(22,True),fill='white'); _txt(d,294,fy+24,action.upper(),_font(42,True),green,350,1); _txt(d,294,fy+86,_pick(pick).upper(),_font(27,True),cream,350,2); _txt(d,664,fy+36,_src('Agent Model',explain),_font(20),cream,350,3); d.text((154,PAGE_HEIGHT-38),SAFETY_FOOTER,font=_font(17),fill=(210,204,190))
    return img.convert('RGB')
def _png(im):
    b=BytesIO(); im.save(b,format='PNG',optimize=True); return b.getvalue()
def render_full_pick_magazine_page_png(pick:Any,background_image:Any=None,report_name:str|None=None,page_number:int=1,total_pages:int=1,logo_image:Any=None,background_mode:str='watermark',logo_mode:str='header',background_opacity:float=.12,logo_opacity:float=1.0)->bytes: return _png(render_full_pick_magazine_page(pick,background_image,report_name,page_number,total_pages,logo_image,background_mode,logo_mode,background_opacity,logo_opacity))
def render_full_magazine_book_pages(picks:Iterable[Any],background_image:Any=None,report_name:str|None=None,logo_image:Any=None,background_mode:str='watermark',logo_mode:str='header',background_opacity:float=.12,logo_opacity:float=1.0)->list[Image.Image]:
    rows=list(picks) or [{'event':'No Picks','prediction':'NO PICK'}]; return [render_full_pick_magazine_page(r,background_image,report_name,i+1,len(rows),logo_image,background_mode,logo_mode,background_opacity,logo_opacity) for i,r in enumerate(rows)]
def render_full_magazine_book_png(picks:Iterable[Any],background_image:Any=None,report_name:str|None=None,logo_image:Any=None,background_mode:str='watermark',logo_mode:str='header',background_opacity:float=.12,logo_opacity:float=1.0)->bytes:
    pages=render_full_magazine_book_pages(picks,background_image,report_name,logo_image,background_mode,logo_mode,background_opacity,logo_opacity); im=Image.new('RGB',(PAGE_WIDTH,PAGE_HEIGHT*len(pages)),(244,236,211))
    for i,p in enumerate(pages): im.paste(p,(0,PAGE_HEIGHT*i))
    return _png(im)
def render_full_magazine_book_pdf(picks:Iterable[Any],background_image:Any=None,report_name:str|None=None,logo_image:Any=None,background_mode:str='watermark',logo_mode:str='header',background_opacity:float=.12,logo_opacity:float=1.0)->bytes:
    pages=[p.convert('RGB') for p in render_full_magazine_book_pages(picks,background_image,report_name,logo_image,background_mode,logo_mode,background_opacity,logo_opacity)]; b=BytesIO(); pages[0].save(b,format='PDF',save_all=True,append_images=pages[1:],resolution=100.0); return b.getvalue()
def render_full_magazine_zip(picks:Iterable[Any],background_image:Any=None,report_name:str|None=None,logo_image:Any=None,background_mode:str='watermark',logo_mode:str='header',background_opacity:float=.12,logo_opacity:float=1.0)->bytes:
    rows=list(picks); pages=render_full_magazine_book_pages(rows,background_image,report_name,logo_image,background_mode,logo_mode,background_opacity,logo_opacity); b=BytesIO()
    with ZipFile(b,'w',compression=ZIP_DEFLATED) as z:
        z.writestr('full_magazine_book.png',render_full_magazine_book_png(rows,background_image,report_name,logo_image,background_mode,logo_mode,background_opacity,logo_opacity)); z.writestr('full_magazine_book.pdf',render_full_magazine_book_pdf(rows,background_image,report_name,logo_image,background_mode,logo_mode,background_opacity,logo_opacity))
        for i,p in enumerate(pages): z.writestr(pick_full_page_filename(rows[i] if i<len(rows) else {'event':'No Picks'},i),_png(p))
    return b.getvalue()
