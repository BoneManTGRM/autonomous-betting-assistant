from __future__ import annotations

from dataclasses import asdict, is_dataclass
from hashlib import sha256
from io import BytesIO
import random
import re
from typing import Any, Iterable, Mapping
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image, ImageDraw, ImageFont

PAGE_WIDTH = 1080
PAGE_HEIGHT = 1620
MAGAZINE_STYLE_VERSION = "premium_v2"
SAFETY_FOOTER = "Analytics only. Results are not guaranteed. Use responsible sizing."
MISSING = "Context unavailable from current feed"
NOT_PROVIDED = "Not provided by agent row"
NO_VERIFIED = "No verified data available"
API_UNAVAILABLE = "API context not available"
PALETTE = ((156,34,31),(20,62,110),(14,88,82),(99,48,126),(180,83,27),(42,77,133),(124,32,82),(39,99,56))


def _row(v: Any) -> Mapping[str, Any]:
    if isinstance(v, Mapping): return v
    if is_dataclass(v): return asdict(v)
    if hasattr(v, "to_dict"):
        d = v.to_dict(); return d if isinstance(d, Mapping) else {}
    return getattr(v, "__dict__", {}) or {}


def _text(r: Any, *keys: str, default: str = "") -> str:
    d = _row(r)
    for k in keys:
        v = d.get(k)
        if v is not None and str(v).strip(): return str(v).strip()
    return default


def _num(r: Any, *keys: str) -> float | None:
    d = _row(r)
    for k in keys:
        v = d.get(k)
        if v in (None, ""): continue
        try: return float(str(v).replace("%", "").replace(",", "").strip())
        except Exception: pass
    return None


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    names = ("DejaVuSansCondensed-Bold.ttf","DejaVuSans-Bold.ttf") if bold else ("DejaVuSansCondensed.ttf","DejaVuSans.ttf")
    for n in names:
        try: return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{n}", size=size)
        except Exception: pass
    return ImageFont.load_default()


def _pct(v: float | None) -> str:
    if v is None: return NO_VERIFIED
    return f"{(v/100 if abs(v)>1 else v):.0%}"


def _edge(v: float | None) -> str:
    if v is None: return NO_VERIFIED
    return f"{(v/100 if abs(v)>1 else v):+.1%}"


def _game(r: Any) -> str: return _text(r, "event","game","event_name","matchup", default="Unknown Game")


def _teams(r: Any) -> tuple[str, str]:
    home = _text(r, "home_team","team_a","team1")
    away = _text(r, "away_team","team_b","team2")
    if home and away: return away, home
    ev = _game(r)
    for sep in (" at "," vs "," v "," VS "," @ "):
        if sep in ev:
            a,b = ev.split(sep,1); return a.strip(), b.strip()
    return _text(r, "team", default="Team A"), _text(r, "opponent", default="Team B")


def _pick(r: Any) -> str: return _text(r, "prediction","exact_bet","pick","selection","recommended_action", default=NOT_PROVIDED)


def _seed(r: Any) -> int:
    d = _row(r)
    s = "|".join(str(d.get(k,"")) for k in ("sport","home_team","away_team","prediction","event_start_utc","event"))
    return int(sha256(s.encode()).hexdigest()[:16],16)


def _color(name: str, n: int = 0) -> tuple[int,int,int]:
    return PALETTE[int(sha256(f"{name}|{n}".encode()).hexdigest()[:8],16)%len(PALETTE)]


def sanitize_image_filename(value: str, suffix: str = "", extension: str = "png") -> str:
    c = re.sub(r"[^A-Za-z0-9]+","_",str(value or "magazine").lower()).strip("_") or "magazine"
    s = re.sub(r"[^A-Za-z0-9]+","_",str(suffix or "").lower()).strip("_")
    return f"{c+'_'+s if s else c}.{(extension or 'png').lstrip('.')}"


def pick_full_page_filename(pick: Any, index: int, extension: str = "png") -> str:
    return sanitize_image_filename(f"pick_{index+1:02d}_{_game(pick)}", "full_page", extension)


def _wrap(draw: ImageDraw.ImageDraw, txt: str, font: ImageFont.ImageFont, w: int, max_lines: int = 2) -> list[str]:
    words = str(txt or "").replace("\n"," ").split(); lines=[]; cur=""
    for word in words:
        t = word if not cur else f"{cur} {word}"
        if draw.textbbox((0,0), t, font=font)[2] <= w: cur=t
        else:
            if cur: lines.append(cur)
            cur=word
            if len(lines)>=max_lines: break
    if cur and len(lines)<max_lines: lines.append(cur)
    if len(lines)==max_lines and len(words)>len(" ".join(lines).split()): lines[-1]=lines[-1].rstrip(".,;")+"..."
    return lines


def _text_box(draw: ImageDraw.ImageDraw, x:int, y:int, txt:str, font:ImageFont.ImageFont, fill, w:int, max_lines:int=2) -> int:
    for line in _wrap(draw, txt, font, w, max_lines):
        draw.text((x,y), line, font=font, fill=fill); y += font.size + 7
    return y


def _split(v: str) -> list[str]:
    return [p.strip(" -•\t") for p in str(v or "").replace("•","\n").replace(";","\n").replace("|","\n").split("\n") if p.strip(" -•\t")]


def _src(src: str, txt: str) -> str: return f"{txt} · Source: {src}"


def _items(r: Any, specs, fallback: str, limit: int) -> list[str]:
    out=[]
    for keys,label,src in specs:
        v = _text(r, *keys)
        if v:
            for p in _split(v) or [v]: out.append(_src(src, f"{label}: {p}"))
    return (out or [fallback])[:limit]


def _why(r: Any) -> list[str]:
    out=[_src("Agent Model", p) for p in _split(_text(r,"why_bullets","why_pick","analysis_summary","reason","explanation"))[:2]]
    vals=(("Model probability",_pct(_num(r,"learned_model_probability","model_probability_clean","model_probability","final_probability")),"Agent Model"),("Market probability",_pct(_num(r,"market_probability","market_implied_probability")),"Odds API"),("Measured edge",_edge(_num(r,"model_market_edge","edge")),"Agent Model"),("Expected value",_text(r,"expected_value_per_unit","profit_expected_value","expected_value","ev"),"Agent Model"),("Available odds",_text(r,"decimal_price","odds_at_pick","best_price","odds"),"Odds API"))
    for label,val,src in vals:
        if val and val != NO_VERIFIED: out.append(_src(src, f"{label}: {val}"))
    return out[:5] or [_src("Agent Model", NOT_PROVIDED)]


def _evidence(r: Any) -> list[str]:
    return _items(r, ((("odds_source","data_source"),"Odds source","Odds API"),(("bookmaker","sportsbook"),"Sportsbook","Odds API"),(("configured_api_sources",),"Configured APIs","Agent Model"),(("api_sources_used",),"APIs used","Agent Model"),(("api_coverage_percent",),"API coverage","Agent Model")), _src("Agent Model","Evidence not provided by agent row"), 5)


def _team_notes(r: Any) -> list[str]:
    return _items(r, ((("home_team_snapshot","team_a_snapshot","sports_context_summary"),"Team snapshot","SportsDataIO"),(("away_team_snapshot","team_b_snapshot"),"Team snapshot","SportsDataIO"),(("api_football_context_status",),"Football context","API-Football"),(("newsapi_context_summary",),"News context","NewsAPI"),(("perplexity_context_summary",),"Research context","Perplexity Context")), _src("Agent Model", MISSING), 6)


def _player_notes(r: Any) -> list[str]:
    return _items(r, ((("injury_report","injuries","lineup_status","injury_source_reason"),"Roster note","SportsDataIO"),(("sportsdataio_injuries_status",),"Roster status","SportsDataIO"),(("sportsdataio_picked_team_injury_count",),"Roster count","SportsDataIO"),(("key_players","players","participant_notes"),"Participants","Agent Model")), _src("SportsDataIO", API_UNAVAILABLE), 5)


def _risk(r: Any) -> list[str]:
    return _items(r, ((("why_lose","risk_reason","hidden_risk"),"Risk note","Agent Model"),(("risk","risk_level","risk_label","profit_guard_status"),"Risk status","Agent Model"),(("weather_flag","weather_reason","weather_bet_adjustment"),"Weather context","WeatherAPI"),(("injury_risk_score","injury_source_reason"),"Roster context","SportsDataIO")), _src("Agent Model","Use conservative sizing."), 5)


def _matchup(r: Any) -> list[str]:
    return _items(r, ((("matchup_note","matchup_notes","head_to_head","h2h"),"Matchup","Agent Model"),(("venue_note","weather_location","venue_source"),"Venue","WeatherAPI"),(("sports_context_summary",),"Sports context","SportsDataIO"),(("api_football_team_lookup_count",),"Team lookup","API-Football")), _src("Agent Model", MISSING), 4)


def _chain(r: Any) -> list[str]:
    supplied = [_src("Agent Model",p) for p in _split(_text(r,"chain_notes","main_read","add_on_legs","parlay_notes"))[:5]]
    return supplied or [_src("Agent Model","Better as individual straight analysis unless another verified edge exists.")]


def _recommend(r: Any) -> tuple[str,str]:
    return _text(r,"final_decision","agent_decision","recommendation","consumer_action","recommended_action", default="research_only"), _text(r,"final_explanation","action_reason","recommendation_reason","decision_reasons", default="Use only if the line remains playable and key news does not change.")


def _bg(size: tuple[int,int], seed:int, a, b, bg:Any=None) -> Image.Image:
    rng=random.Random(seed); img=Image.new("RGB",size,(240,227,190)); d=ImageDraw.Draw(img,"RGBA")
    for x in range(-260,size[0],54): d.line((x,0,x+320,size[1]), fill=(110,70,45,rng.randint(5,14)), width=rng.randint(8,17))
    for _ in range(330):
        x=rng.randint(0,size[0]); y=rng.randint(0,size[1]); s=rng.randint(18,115)
        d.rectangle((x,y,x+rng.randint(1,3),y+rng.randint(1,3)), fill=(s,s,s,rng.randint(14,42)))
    for _ in range(15):
        c=a if rng.random()<.5 else b; x=rng.randint(-100,size[0]-120); y=rng.randint(80,size[1]-240)
        d.ellipse((x,y,x+rng.randint(170,360),y+rng.randint(22,72)), fill=(*c,rng.randint(22,46)))
    return img


def _panel(draw: ImageDraw.ImageDraw, xy, fill=(250,241,213,240), outline=(16,22,31)) -> None:
    draw.rounded_rectangle(xy, radius=14, fill=fill, outline=outline, width=3)


def _bar(draw: ImageDraw.ImageDraw, xy, title: str, color) -> None:
    x1,y1,x2,y2=xy; draw.rounded_rectangle(xy, radius=8, fill=color)
    draw.text((x1+16,y1+8), title.upper(), font=_font(25, True), fill=(255,246,220))


def _bullets(draw: ImageDraw.ImageDraw, x:int, y:int, items:list[str], w:int, max_items:int, size:int, color) -> None:
    font=_font(size)
    for item in items[:max_items]:
        lines=_wrap(draw,item,font,w-28,2); draw.ellipse((x,y+8,x+10,y+18), fill=color)
        for line in lines: draw.text((x+24,y), line, font=font, fill=(18,21,26)); y += size+5
        y += 7


def _section(draw: ImageDraw.ImageDraw, x:int, y:int, w:int, h:int, title:str, items:list[str], color, max_items:int=5) -> None:
    _panel(draw,(x,y,x+w,y+h)); _bar(draw,(x,y,x+w,y+50),title,color); _bullets(draw,x+22,y+70,items,w-44,max_items,18,color)


def _metric(draw: ImageDraw.ImageDraw, x:int, y:int, w:int, label:str, value:str, color) -> None:
    draw.rectangle((x,y,x+w,y+94), fill=(17,19,22), outline=(223,214,190), width=1)
    draw.text((x+10,y+10), label.upper(), font=_font(17,True), fill=(239,231,209))
    _text_box(draw,x+10,y+38,value,_font(25,True),color,w-18,1)


def _art(draw: ImageDraw.ImageDraw, x:int, y:int, w:int, h:int, sport:str, seed:int, a, b) -> None:
    rng=random.Random(seed+911); dark=(15,25,41)
    draw.rounded_rectangle((x,y,x+w,y+h), radius=24, fill=(*dark,238), outline=(255,246,220), width=5)
    for _ in range(8):
        c=a if rng.random()<.5 else b; yy=y+rng.randint(10,h-40)
        draw.ellipse((x+rng.randint(-40,80),yy,x+w+rng.randint(-80,40),yy+rng.randint(20,70)), fill=(*c,rng.randint(45,75)))
    draw.rectangle((x+22,y+22,x+w-22,y+h-22), outline=(*a,255), width=6)
    cx=x+w//2+rng.randint(-18,18); draw.ellipse((cx-54,y+48,cx+54,y+156), fill=(237,222,187))
    draw.rounded_rectangle((cx-95,y+148,cx+95,y+318), radius=38, fill=(*b,255))
    draw.polygon([(cx-90,y+170),(x+44,y+250),(x+66,y+282),(cx-60,y+240)], fill=(237,222,187))
    draw.polygon([(cx+90,y+170),(x+w-48,y+246),(x+w-70,y+278),(cx+60,y+240)], fill=(237,222,187))
    lower=sport.lower()
    if "basket" in lower: draw.ellipse((x+w-116,y+54,x+w-34,y+136), fill=(201,96,31), outline=(245,235,210), width=3)
    elif "soccer" in lower or "football" in lower or "fifa" in lower:
        draw.ellipse((x+w-112,y+56,x+w-36,y+132), fill=(245,235,210), outline=dark, width=3)
        draw.polygon([(x+w-74,y+76),(x+w-52,y+92),(x+w-61,y+118),(x+w-88,y+118),(x+w-96,y+92)], fill=dark)
    else: draw.ellipse((x+w-104,y+58,x+w-34,y+128), fill=(245,235,210), outline=a, width=4)
    draw.text((x+28,y+h-62), sport.upper()[:16], font=_font(30,True), fill=(255,246,220))


def render_full_pick_magazine_page(pick: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1) -> Image.Image:
    seed=_seed(pick); team_a,team_b=_teams(pick); a,b=_color(team_a,1),_color(team_b,2)
    img=_bg((PAGE_WIDTH,PAGE_HEIGHT),seed,a,b,background_image).convert("RGBA"); draw=ImageDraw.Draw(img,"RGBA")
    black=(14,17,20); cream=(247,238,211); green=(42,178,72); sport=_text(pick,"sport","league",default="Sport N/A")
    source=_text(pick,"odds_source","bookmaker","sportsbook",default="Agent row"); report=report_name or "Full Pick Magazine"; date=_text(pick,"report_date","event_date",default=NOT_PROVIDED)

    draw.rectangle((0,0,PAGE_WIDTH,58), fill=black); draw.rectangle((16,9,236,51), fill=a)
    draw.text((30,15),"ABA SIGNAL PRO",font=_font(27,True),fill=(255,255,255)); draw.text((266,14),"DAILY SPORTS ANALYSIS",font=_font(29,True),fill=cream)
    draw.rounded_rectangle((838,8,PAGE_WIDTH-18,50), radius=5, fill=cream); draw.text((862,15),f"PAGE {page_number} OF {total_pages}",font=_font(24,True),fill=black)
    draw.rectangle((0,58,PAGE_WIDTH,104), fill=(248,239,214,245)); _text_box(draw,28,69,f"REPORT: {report}   ★   SOURCE: {source}   |   DATE: {date}",_font(21,True),black,800,1)
    draw.rounded_rectangle((888,68,PAGE_WIDTH-22,138), radius=10, fill=b); draw.text((910,88),sport.upper()[:12],font=_font(26,True),fill=(255,255,255))

    draw.text((34,128),team_a.upper(),font=_font(74,True),fill=a); draw.text((38,238),"VS",font=_font(41,True),fill=black); draw.line((35,287,105,287),fill=black,width=4)
    draw.text((120,230),team_b.upper(),font=_font(62,True),fill=b); draw.rectangle((34,348,462,394),fill=black); draw.text((50,356),f"{sport} ANALYSIS".upper()[:31],font=_font(24,True),fill=cream)
    _text_box(draw,36,414,_src("Agent Model",_text(pick,"game_summary","preview_summary","short_reason","decision_reasons",default=NOT_PROVIDED)),_font(21),black,610,3)
    _art(draw,668,112,370,320,sport,seed,a,b)

    sy=474; draw.rounded_rectangle((18,sy,PAGE_WIDTH-18,sy+98),radius=16,fill=black,outline=cream,width=3); draw.text((42,sy+14),"TENDENCIA",font=_font(24,True),fill=a)
    _text_box(draw,42,sy+45,_pick(pick),_font(31,True),(255,255,255),260,1); mx=324; mw=106
    for label,value,c in (("Odds",_text(pick,"decimal_price","odds_at_pick","best_price","odds",default=NO_VERIFIED),(255,255,255)),("Conf",_pct(_num(pick,"learned_model_probability","model_probability_clean","model_probability","final_probability")),green),("Edge",_edge(_num(pick,"model_market_edge","edge")),green),("EV",_text(pick,"expected_value_per_unit","profit_expected_value","expected_value","ev",default=NO_VERIFIED),green),("Units",_text(pick,"recommended_stake_units","suggested_stake_units",default=NOT_PROVIDED),(255,255,255)),("Risk",_text(pick,"risk","risk_level","risk_label","profit_guard_status","weather_flag","injury_risk_score",default=NO_VERIFIED),green),("Market",_text(pick,"market_type","market","bet_type",default=NO_VERIFIED),(255,255,255))):
        _metric(draw,mx,sy+2,mw,label,value,c); mx += mw

    _section(draw,18,598,338,304,"WHY WE PICKED IT",_why(pick),a,5); _section(draw,18,918,338,250,"PRO EVIDENCE",_evidence(pick),b,5)
    _panel(draw,(382,598,PAGE_WIDTH-18,964)); _bar(draw,(382,598,PAGE_WIDTH-18,648),"TEAM SNAPSHOTS",b); _bullets(draw,406,670,_team_notes(pick),628,6,18,b)
    _panel(draw,(382,982,PAGE_WIDTH-18,1168)); _bar(draw,(382,982,PAGE_WIDTH-18,1032),"PLAYER / ROSTER NOTES",b); _bullets(draw,406,1052,_player_notes(pick),628,5,18,b)
    _section(draw,18,1186,338,230,"RISK DESK",_risk(pick),a,5); _section(draw,372,1186,338,230,"MATCHUP NOTES",_matchup(pick),b,4); _section(draw,726,1186,336,230,"CHAIN NOTES",_chain(pick),b,4)

    action,explanation=_recommend(pick); fy=1438; draw.rounded_rectangle((18,fy,PAGE_WIDTH-18,PAGE_HEIGHT-48),radius=12,fill=black,outline=a,width=4); draw.rectangle((18,fy,238,PAGE_HEIGHT-48),fill=a)
    draw.text((34,fy+22),"FINAL",font=_font(26,True),fill=(255,255,255)); draw.text((34,fy+58),"RECOMMENDATION",font=_font(21,True),fill=(255,255,255))
    _text_box(draw,268,fy+16,action.upper(),_font(50,True),green,350,1); _text_box(draw,268,fy+76,_pick(pick),_font(29,True),(255,255,255),350,1); _text_box(draw,640,fy+26,_src("Agent Model",explanation),_font(21),(255,255,255),382,3)
    draw.text((118,PAGE_HEIGHT-34),SAFETY_FOOTER,font=_font(18),fill=cream)
    return img.convert("RGB")


def _png_bytes(image: Image.Image) -> bytes:
    buf=BytesIO(); image.save(buf,format="PNG",optimize=True); return buf.getvalue()


def render_full_pick_magazine_page_png(pick: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1) -> bytes:
    return _png_bytes(render_full_pick_magazine_page(pick, background_image, report_name, page_number, total_pages))


def render_full_magazine_book_pages(picks: Iterable[Any], background_image: Any = None, report_name: str | None = None) -> list[Image.Image]:
    pick_list=list(picks); total=len(pick_list) or 1
    return [render_full_pick_magazine_page(pick,background_image,report_name,i+1,total) for i,pick in enumerate(pick_list)]


def render_full_magazine_book_png(picks: Iterable[Any], background_image: Any = None, report_name: str | None = None) -> bytes:
    pages=render_full_magazine_book_pages(picks,background_image,report_name) or [render_full_pick_magazine_page({"event":"No Picks","prediction":"NO PICK"},background_image,report_name,1,1)]
    combined=Image.new("RGB",(PAGE_WIDTH,PAGE_HEIGHT*len(pages)),(232,214,169))
    for i,page in enumerate(pages): combined.paste(page.convert("RGB"),(0,PAGE_HEIGHT*i))
    return _png_bytes(combined)


def render_full_magazine_book_pdf(picks: Iterable[Any], background_image: Any = None, report_name: str | None = None) -> bytes:
    pages=[p.convert("RGB") for p in render_full_magazine_book_pages(picks,background_image,report_name)] or [render_full_pick_magazine_page({"event":"No Picks","prediction":"NO PICK"},background_image,report_name,1,1)]
    buf=BytesIO(); pages[0].save(buf,format="PDF",save_all=True,append_images=pages[1:],resolution=100.0); return buf.getvalue()


def render_full_magazine_zip(picks: Iterable[Any], background_image: Any = None, report_name: str | None = None) -> bytes:
    pick_list=list(picks); pages=render_full_magazine_book_pages(pick_list,background_image,report_name); buf=BytesIO()
    with ZipFile(buf,"w",compression=ZIP_DEFLATED) as archive:
        archive.writestr("full_magazine_book.png",render_full_magazine_book_png(pick_list,background_image,report_name))
        archive.writestr("full_magazine_book.pdf",render_full_magazine_book_pdf(pick_list,background_image,report_name))
        for i,page in enumerate(pages): archive.writestr(pick_full_page_filename(pick_list[i],i),_png_bytes(page))
    return buf.getvalue()
