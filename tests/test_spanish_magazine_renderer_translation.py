import importlib

import autonomous_betting_agent.magazine_book_export as magazine_book_export
from autonomous_betting_agent import magazine_live_api_enrichment  # noqa: F401


def test_spanish_renderer_translates_dynamic_report_text_after_reload():
    module = importlib.reload(magazine_book_export)

    assert module._tr("PAGE 1 OF 75", "es") == "PÁGINA 1 DE 75"
    assert module._tr("WATCHLIST", "es") == "LISTA DE SEGUIMIENTO"
    assert "El modelo proyecta" in module._tr("Model projects 71% probability for TOTAL DEL PARTIDO: MÁS DE 2.5.", "es")
    assert "probabilidad implícita" in module._tr("Market-implied probability checks at 73%.", "es")
    assert module._tr("No SDIO event ID.", "es") == "Sin ID de evento SDIO."
    assert module._tr("API-FB: no fixture match.", "es") == "API-FB: sin coincidencia de partido."
    assert "No encadenar" in module._tr("Do not chain negative-EV picks.", "es")
    assert "No jugar con la cuota listada" in module._tr("Do not play at the listed price.", "es")
