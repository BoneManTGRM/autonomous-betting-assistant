from __future__ import annotations

LABELS = {
    "PAGE": "PÁGINA",
    "OF": "DE",
    "DAILY SPORTS ANALYSIS": "ANÁLISIS DEPORTIVO DIARIO",
    "WHY WE PICKED IT": "POR QUÉ LO ELEGIMOS",
    "TEAM SNAPSHOTS": "RESUMEN DE EQUIPOS",
    "PLAYER / INJURY NOTES": "JUGADORES / LESIONES",
    "RISK DESK": "MESA DE RIESGO",
    "FINAL": "FINAL",
    "RECOMMENDATION": "RECOMENDACIÓN",
    "PARLAY RECOMMENDATION BOARD": "TABLERO DE RECOMENDACIONES PARLAY",
}

def install() -> None:
    try:
        from autonomous_betting_agent import magazine_book_export as book
        book.ES.update(LABELS)
    except Exception:
        pass
    try:
        from autonomous_betting_agent import magazine_second_page_patch as second
        second.ES.update(LABELS)
    except Exception:
        pass

install()
