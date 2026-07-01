# Page 2 Dynamic Market Intelligence Manifest

Status: implementation target for ABA Signal Pro Report Studio.

This update keeps Page 1 as the straight-pick report and makes Page 2 a source-gated market intelligence page. Page 2 should never mark a market as verified unless the active provider row includes the exact event ID, market, line, selection, price, source/book, and timestamp.

Required gates:

- event matched
- market matched
- line matched
- selection matched
- price present and current
- provider/source present
- timestamp present
- positive edge and positive EV
- no stale cached or saved-handoff control
- Reparodynamics status is not blocked or drift detected

Expected labels:

- VERIFIED
- WATCHLIST
- MENU ONLY
- LIVE TRIGGER
- AVOID
- BLOCKED
- PRICE EXPIRED

Next implementation file: `autonomous_betting_agent/magazine_second_page_patch.py`.

The current repo already forces Page 2 through `magazine_sale_ready_patch.py`, which calls `magazine_second_page_patch._draw_second_page(...)`. That is the correct integration point for the dynamic Page 2 renderer.
