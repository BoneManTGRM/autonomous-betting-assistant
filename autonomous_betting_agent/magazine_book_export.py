from __future__ import annotations
from dataclasses import asdict, is_dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import random, re
from typing import Any, Iterable, Mapping
from zipfile import ZIP_DEFLATED, ZipFile
from PIL import Image, ImageDraw, ImageFont

PAGE_WIDTH=1080
PAGE_HEIGHT=1620
MAGAZINE_STYLE_VERSION='premium_v3_legal_cover'
SAFETY_FOOTER='Analytics only. Results are not guaranteed. Use responsible sizing.'
ASSET_DIRS=(Path('assets/team_logos'),Path('assets/report_logos'),Path('assets/licensed_logos'))
PALETTE=((170,31,27),(17,58,102),(14,92,82),(92,45,128),(182,84,30),(41,78,138),(120,31,84),(37,101,61))
NO_VERIFIED='No verified data available'
NOT_PROVIDED='Not provided by agent row'


def _row(v:Any)->Mapping[str,Any]:
    if isinstance(v,Mapping): return v
    if is_dataclass(v): return asdict(v)
    if hasattr(v,'to_dict'):
        d=v.to_dict(); return d if isinstance(d,Mapping) else {}
    return getattr(v,'__dict__',{}) or {}

def _text(r,*keys,default=''):
    d=_row(r)
    for k in keys:
        v=d.get(k)
        if v is not None and str(v).strip(): return str(v).strip()
    return default

def _num(r,*keys):
    for k in keys:
        v=_row(r).get(k)
        if v not in (None,''):
            try: return float(str(v).replace('%','').replace(',',''))
            except Exception: pass
    return None

def _font(n,b=False):
    names=('DejaVuSansCondensed-Bold.ttf','DejaVuSans-Bold.ttf') if b else ('DejaVuSansCondensed.ttf','DejaVuSans.ttf')
    for name in names:
        try: return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/'+name,n)
        except Exception: pass
    return ImageFont.load_default()

def _pct(v): return NO_VERIFIED if v is None else f'{(v/100 if abs(v)>1 else v):.0%}'
def _edge(v): return NO_VERIFIED if v is None else f'{(v/100 if abs(v)>1 else v):+.1%}'
def _game(r): return _text(r,'event','game','event_name','matchup',default='Unknown Game')
def _pick(r): return _text(r,'prediction','exact_bet','pick','selection','recommended_action',default=NOT_PROVIDED)

def _teams(r):
    home=_text(r,'home_team','team_a','team1'); away=_text(r,'away_team','team_b','team2')
    if home and away: return away,home
    g=_game(r)
    for sep in (' at ',' vs ',' v ',' VS ',' @ '):
        if sep in g:
            a,b=g.split(sep,1); return a.strip(),b.strip()
    return _text(r,'team',default='Team A'),_text(r,'opponent',default='Team B')

def _seed(r):
    d=_row(r); s='|'.join(str(d.get(k,'')) for k in ('sport','home_team','away_team','prediction','event_start_utc','event'))
    return int(sha256(s.encode()).hexdigest()[:16],16)

def _safe(s): return re.sub(r'[^a-z0-9]+','_',str(s or '').lower()).strip('_')
def _color(s,n=0): return PALETTE[int(sha256(f'{s}|{n}'.encode()).hexdigest()[:8],16)%len(PALETTE)]
def _parse(c,f): return tuple(int(c[i:i+2],16) for i in (1,3,5)) if re.fullmatch(r'#[0-9A-Fa-f]{6}',str(c or '')) else f

def _colors(r,a,b):
    d=_row(r)
    return _parse(d.get('team_a_color') or d.get('away_team_color') or d.get('primary_color'),_color(a,1)),_parse(d.get('team_b_color') or d.get('home_team_color') or d.get('secondary_color'),_color(b,2))

def sanitize_image_filename(value:str,suffix:str='',extension:str='png')->str:
    c=re.sub(r'[^A-Za-z0-9]+','_',str(value or 'magazine').lower()).strip('_') or 'magazine'
    s=re.sub(r'[^A-Za-z0-9]+','_',str(suffix or '').lower()).strip('_')
    ext=(extension or 'png').lstrip('.')
    return f'{c+"_"+s if s else c}.{ext}'

def pick_full_page_filename(pick:Any,index:int,extension:str='png')->str:
    return sanitize_image_filename(f'pick_{index+1:02d}_{_game(pick)}','full_page',extension)

def _wrap(d,t,f,w,m=2):
    out=[]; cur=''
    for word in str(t or '').replace(chr(10),' ').split():
        trial=word if not cur else cur+' '+word
        if d.textbbox((0,0),trial,font=f)[2]<=w: cur=trial
        else:
            if cur: out.append(cur)
            cur=word
            if len(out)>=m: break
    if cur and len(out)<m: out.append(cur)
    if len(out)==m: out[-1]=out[-1].rstrip('.,;')+('...' if len(' '.join(out).split())<len(str(t).split()) else '')
    return out

def _txt(d,x,y,t,f,fill,w,m=2):
    for line in _wrap(d,t,f,w,m):
        d.text((x,y),line,font=f,fill=fill); y+=f.size+7
    return y

def _split(v):
    nl=chr(10)
    return [p.strip(' -•') for p in str(v or '').replace('•',nl).replace(';',nl).replace('|',nl).split(nl) if p.strip(' -•')]
def _src(s,t): return f'{t} · Source: {s}'

def _items(r,specs,fb,limit):
    out=[]
    for keys,label,source in specs:
        v=_text(r,*keys)
        if v: out += [_src(source,f'{label}: {p}') for p in (_split(v) or [v])]
    return (out or [fb])[:limit]

def _why(r):
    out=[_src('Agent Model',p) for p in _split(_text(r,'why_bullets','why_pick','analysis_summary','reason','explanation'))[:2]]
    vals=(('Model probability',_pct(_num(r,'learned_model_probability','model_probability_clean','model_probability','final_probability')),'Agent Model'),('Market probability',_pct(_num(r,'market_probability','market_implied_probability')),'Odds API'),('Measured edge',_edge(_num(r,'model_market_edge','edge')),'Agent Model'),('Expected value',_text(r,'expected_value_per_unit','profit_expected_value','expected_value','ev'),'Agent Model'),('Available odds',_text(r,'decimal_price','odds_at_pick','best_price','odds'),'Odds API'))
    for lab,val,src in vals:
        if val and val!=NO_VERIFIED: out.append(_src(src,f'{lab}: {val}'))
    return out[:5] or [_src('Agent Model',NOT_PROVIDED)]

def _evidence(r): return _items(r,((('odds_source','data_source'),'Odds source','Odds API'),(('bookmaker','sportsbook'),'Sportsbook','Odds API'),(('configured_api_sources',),'Configured APIs','Agent Model'),(('api_sources_used',),'APIs used','Agent Model'),(('api_coverage_percent',),'API coverage','Agent Model')),_src('Agent Model','Evidence not provided'),5)
def _team(r): return _items(r,((('home_team_snapshot','team_a_snapshot','sports_context_summary'),'Team snapshot','SportsDataIO'),(('away_team_snapshot','team_b_snapshot'),'Team snapshot','SportsDataIO'),(('api_football_context_status',),'Football context','API-Football'),(('newsapi_context_summary',),'News context','NewsAPI')),_src('Agent Model','Data not available from uploaded row'),6)
def _players(r): return _items(r,((('injury_report','injuries','lineup_status','injury_source_reason'),'Roster note','SportsDataIO'),(('sportsdataio_injuries_status',),'Roster status','SportsDataIO'),(('key_players','players','participant_notes'),'Participants','Agent Model')),_src('SportsDataIO','Player data not available in uploaded row'),5)
def _risk(r): return _items(r,((('why_lose','risk_reason','hidden_risk'),'Risk note','Agent Model'),(('risk','risk_level','risk_label','profit_guard_status'),'Risk status','Agent Model'),(('weather_flag','weather_reason','weather_bet_adjustment'),'Weather context','WeatherAPI'),(('injury_risk_score','injury_source_reason'),'Roster context','SportsDataIO')),_src('Agent Model','Use conservative sizing.'),4)
def _match(r): return _items(r,((('matchup_note','matchup_notes','head_to_head','h2h'),'Matchup','Agent Model'),(('venue_note','weather_location','venue_source'),'Venue','WeatherAPI'),(('sports_context_summary',),'Sports context','SportsDataIO')),_src('Agent Model','Context unavailable from current feed'),4)
def _chain(r): return [_src('Agent Model',p) for p in _split(_text(r,'chain_notes','main_read','add_on_legs','parlay_notes'))[:4]] or [_src('Agent Model','Better as individual straight analysis unless another verified edge exists.')]
def _rec(r): return _text(r,'final_decision','agent_decision','recommendation','consumer_action','recommended_action',default='research_only'),_text(r,'final_explanation','action_reason','recommendation_reason','decision_reasons',default='Use only if the line remains playable and key news does not change.')

def _bg(size,seed,a,b,bg=None):
    try:
        img=Image.open(BytesIO(bg)).convert('RGB') if isinstance(bg,(bytes,bytearray)) else (bg.convert('RGB') if isinstance(bg,Image.Image) else Image.new('RGB',size,(241,228,190)))
        img=img.resize(size) if img.size!=size else img
    except Exception: img=Image.new('RGB',size,(241,228,190))
    d=ImageDraw.Draw(img,'RGBA'); rng=random.Random(seed)
    for x in range(-260,size[0],54): d.line((x,0,x+340,size[1]),fill=(95,62,40,rng.randint(5,16)),width=rng.randint(7,17))
    for _ in range(340):
        x,y,s=rng.randint(0,size[0]-1),rng.randint(0,size[1]-1),rng.randint(1,4); q=rng.randint(20,150)
        d.rectangle((x,y,x+s,y+s),fill=(q,q,q,rng.randint(10,40)))
    for _ in range(18):
        c=a if rng.random()<.5 else b; x,y=rng.randint(-120,size[0]-120),rng.randint(85,size[1]-230)
        d.ellipse((x,y,x+rng.randint(180,520),y+rng.randint(22,82)),fill=(*c,rng.randint(25,65)))
    return img

def _logo(team):
    stem=_safe(team)
    for folder in ASSET_DIRS:
        for name in (stem,stem.replace('_','-')):
            for ext in ('.png','.jpg','.jpeg','.webp'):
                p=folder/f'{name}{ext}'
                if p.exists(): return p
    return None

def _crest(img,d,x,y,s,team,c,accent):
    p=_logo(team)
    if p:
        try:
            lg=Image.open(p).convert('RGBA'); lg.thumbnail((s,s),Image.Resampling.LANCZOS); img.alpha_composite(lg,(x+(s-lg.width)//2,y+(s-lg.height)//2)); return
        except Exception: pass
    pts=[(x+s//2,y),(x+s-4,y+s//5),(x+s-18,y+int(s*.78)),(x+s//2,y+s-2),(x+18,y+int(s*.78)),(x+4,y+s//5)]
    d.polygon(pts,fill=c,outline=(255,246,220)); d.line((x+20,y+s//2,x+s-20,y+s//2),fill=accent,width=max(5,s//14))
    initials=''.join(w[0] for w in re.findall(r'[A-Za-z0-9]+',team.upper())[:3]) or 'TM'; f=_font(max(22,s//3),True); box=d.textbbox((0,0),initials,font=f)
    d.text((x+(s-box[2])//2,y+int(s*.34)),initials,font=f,fill=(255,255,255))

def _ball(d,cx,cy,r,sport):
    d.ellipse((cx-r,cy-r,cx+r,cy+r),fill=(255,246,220),outline=(14,18,28),width=4)
    if 'baseball' in sport.lower() or 'mlb' in sport.lower(): d.arc((cx-r+10,cy-r,cx+r-10,cy+r),70,290,fill=(14,18,28),width=4); d.arc((cx-r+10,cy-r,cx+r-10,cy+r),-110,110,fill=(14,18,28),width=4)
    elif 'basket' in sport.lower(): d.line((cx,cy-r,cx,cy+r),fill=(14,18,28),width=4); d.line((cx-r,cy,cx+r,cy),fill=(14,18,28),width=4)
    else: d.polygon([(cx,cy-r+10),(cx+r-8,cy-r//4),(cx+r//2,cy+r-6),(cx-r//2,cy+r-6),(cx-r+8,cy-r//4)],fill=(14,18,28))

def _panel(d,xy,title,color):
    d.rounded_rectangle(xy,radius=13,fill=(250,242,216,238),outline=(13,18,28),width=3); x1,y1,x2,y2=xy
    d.rounded_rectangle((x1,y1,x2,y1+50),radius=8,fill=color); d.text((x1+16,y1+8),title.upper(),font=_font(24,True),fill=(255,246,220))

def _bul(d,x,y,items,w,n,size,color):
    f=_font(size)
    for it in items[:n]:
        d.ellipse((x,y+8,x+10,y+18),fill=color)
        for line in _wrap(d,it,f,w-30,2): d.text((x+24,y),line,font=f,fill=(17,20,28)); y+=size+5
        y+=7

def _section(d,x,y,w,h,title,items,color,n=5,size=18): _panel(d,(x,y,x+w,y+h),title,color); _bul(d,x+22,y+70,items,w-44,n,size,color)
def _metric(d,x,y,w,lab,val,col): d.rectangle((x,y,x+w,y+94),fill=(16,18,22),outline=(223,214,190)); d.text((x+10,y+10),lab.upper(),font=_font(17,True),fill=(239,231,209)); _txt(d,x+10,y+38,val,_font(24,True),col,w-18,1)

def render_full_pick_magazine_page(pick:Any,background_image:Any=None,report_name:str|None=None,page_number:int=1,total_pages:int=1)->Image.Image:
    seed=_seed(pick); ta,tb=_teams(pick); ca,cb=_colors(pick,ta,tb); img=_bg((PAGE_WIDTH,PAGE_HEIGHT),seed,ca,cb,background_image).convert('RGBA'); d=ImageDraw.Draw(img,'RGBA')
    black,cream,green=(14,17,20),(247,238,211),(42,188,72); sport=_text(pick,'sport','league',default='Sport N/A'); source=_text(pick,'odds_source','bookmaker','sportsbook',default='Agent row'); report=report_name or 'Full Pick Magazine'; date=_text(pick,'report_date','event_date',default=NOT_PROVIDED)
    d.rectangle((0,0,PAGE_WIDTH,70),fill=black); d.rectangle((18,10,260,58),fill=ca); d.text((32,17),'ABA SIGNAL PRO',font=_font(31,True),fill='white'); d.text((290,17),'DAILY SPORTS ANALYSIS',font=_font(33,True),fill=cream); d.rounded_rectangle((838,10,PAGE_WIDTH-18,58),radius=5,fill=cream); d.text((872,19),f'PAGE {page_number} OF {total_pages}',font=_font(25,True),fill=black)
    d.rectangle((0,70,PAGE_WIDTH,115),fill=(248,239,214,248)); _txt(d,28,80,f'REPORT: {report}   ★   SOURCE: {source}   |   DATE: {date}',_font(21,True),black,790,1); d.rounded_rectangle((888,72,PAGE_WIDTH-22,144),radius=9,fill=cb); d.text((913,92),sport.upper()[:12],font=_font(26,True),fill='white')
    for i in range(6): d.ellipse((390-i*12,122+i*47+(seed+i*13)%18,1040,170+i*47+(seed+i*13)%18),fill=(*(ca if i%2==0 else cb),50))
    d.text((34,120),ta.upper(),font=_font(108,True),fill=ca); d.text((38,256),'VS',font=_font(48,True),fill=black); d.line((35,315,112,315),fill=black,width=5); d.text((126,238),tb.upper(),font=_font(78,True),fill=cb); d.rectangle((34,360,472,412),fill=black); d.text((50,370),f'{sport} ANALYSIS'.upper()[:31],font=_font(27,True),fill=cream); _txt(d,36,429,_src('Agent Model',_text(pick,'game_summary','preview_summary','short_reason','decision_reasons',default=NOT_PROVIDED)),_font(22),black,610,2)
    d.rounded_rectangle((666,118,1036,478),radius=24,fill=(14,25,44,238),outline=cream,width=5); rng=random.Random(seed+911)
    for i in range(10):
        c=ca if i%2==0 else cb; yy=135+rng.randint(0,300); d.ellipse((620+rng.randint(-20,80),yy,1060+rng.randint(-90,45),yy+rng.randint(24,76)),fill=(*c,rng.randint(48,90)))
    _crest(img,d,694,160,132,ta,ca,cb); _crest(img,d,872,288,136,tb,cb,ca); _ball(d,851,286,62,sport); d.text((696,420),sport.upper()[:18],font=_font(29,True),fill=cream)
    sy=520; d.rounded_rectangle((18,sy,PAGE_WIDTH-18,sy+118),radius=14,fill=black,outline=cream,width=3); d.text((42,sy+16),'TENDENCIA',font=_font(25,True),fill=ca); _txt(d,42,sy+52,_pick(pick).upper(),_font(32,True),'white',260,1)
    metrics=(('Odds',_text(pick,'decimal_price','odds_at_pick','best_price','odds',default=NO_VERIFIED),'white'),('Conf',_pct(_num(pick,'learned_model_probability','model_probability_clean','model_probability','final_probability')),green),('Edge',_edge(_num(pick,'model_market_edge','edge')),green),('EV',_text(pick,'expected_value_per_unit','profit_expected_value','expected_value','ev',default=NO_VERIFIED),green),('Units',_text(pick,'recommended_stake_units','suggested_stake_units',default=NOT_PROVIDED),'white'),('Risk',_text(pick,'risk','risk_level','risk_label','profit_guard_status','weather_flag','injury_risk_score',default=NO_VERIFIED),green),('Market',_text(pick,'market_type','market','bet_type',default=NO_VERIFIED),'white'))
    x=324
    for lab,val,col in metrics: _metric(d,x,sy+5,106,lab,val,col); x+=106
    _section(d,18,660,338,286,'WHY WE PICKED IT',_why(pick),ca,5,18); _section(d,18,970,338,248,'PRO BETTOR EVIDENCE',_evidence(pick),cb,5,17); _section(d,382,660,680,372,'TEAM SNAPSHOTS',_team(pick),cb,6,18); _section(d,382,1048,680,170,'PLAYER / INJURY NOTES',_players(pick),cb,5,17); _section(d,18,1238,338,170,'RISK DESK',_risk(pick),ca,4,16); _section(d,372,1238,338,170,'MATCHUP NOTES',_match(pick),cb,4,16); _section(d,726,1238,336,170,'CHAIN BETTING NOTES',_chain(pick),cb,4,16)
    action,exp=_rec(pick); fy=1420; d.rounded_rectangle((18,fy,PAGE_WIDTH-18,PAGE_HEIGHT-48),radius=12,fill=black,outline=ca,width=4); d.rectangle((18,fy,242,PAGE_HEIGHT-48),fill=ca); d.text((34,fy+24),'FINAL',font=_font(28,True),fill='white'); d.text((34,fy+62),'RECOMMENDATION',font=_font(22,True),fill='white'); _txt(d,272,fy+18,action.upper(),_font(54,True),green,350,1); _txt(d,272,fy+82,_pick(pick).upper(),_font(31,True),'white',350,1); _txt(d,646,fy+28,_src('Agent Model',exp),_font(22),'white',380,3); d.text((122,PAGE_HEIGHT-34),SAFETY_FOOTER,font=_font(18),fill=cream)
    return img.convert('RGB')

def _png_bytes(image:Image.Image)->bytes:
    b=BytesIO(); image.save(b,format='PNG',optimize=True); return b.getvalue()

def render_full_pick_magazine_page_png(pick:Any,background_image:Any=None,report_name:str|None=None,page_number:int=1,total_pages:int=1)->bytes: return _png_bytes(render_full_pick_magazine_page(pick,background_image,report_name,page_number,total_pages))
def render_full_magazine_book_pages(picks:Iterable[Any],background_image:Any=None,report_name:str|None=None)->list[Image.Image]:
    rows=list(picks) or [{'event':'No Picks','prediction':'NO PICK'}]; return [render_full_pick_magazine_page(p,background_image,report_name,i+1,len(rows)) for i,p in enumerate(rows)]
def render_full_magazine_book_png(picks:Iterable[Any],background_image:Any=None,report_name:str|None=None)->bytes:
    pages=render_full_magazine_book_pages(picks,background_image,report_name); img=Image.new('RGB',(PAGE_WIDTH,PAGE_HEIGHT*len(pages)),(232,214,169))
    for i,p in enumerate(pages): img.paste(p,(0,PAGE_HEIGHT*i))
    return _png_bytes(img)
def render_full_magazine_book_pdf(picks:Iterable[Any],background_image:Any=None,report_name:str|None=None)->bytes:
    pages=[p.convert('RGB') for p in render_full_magazine_book_pages(picks,background_image,report_name)]; b=BytesIO(); pages[0].save(b,format='PDF',save_all=True,append_images=pages[1:],resolution=100.0); return b.getvalue()
def render_full_magazine_zip(picks:Iterable[Any],background_image:Any=None,report_name:str|None=None)->bytes:
    rows=list(picks); pages=render_full_magazine_book_pages(rows,background_image,report_name); b=BytesIO()
    with ZipFile(b,'w',compression=ZIP_DEFLATED) as z:
        z.writestr('full_magazine_book.png',render_full_magazine_book_png(rows,background_image,report_name)); z.writestr('full_magazine_book.pdf',render_full_magazine_book_pdf(rows,background_image,report_name))
        for i,p in enumerate(pages): z.writestr(pick_full_page_filename(rows[i] if i<len(rows) else {'event':'No Picks'},i),_png_bytes(p))
    return b.getvalue()
