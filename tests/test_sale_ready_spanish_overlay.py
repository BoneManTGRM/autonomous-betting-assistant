import inspect

from autonomous_betting_agent import magazine_book_export as renderer
from autonomous_betting_agent import magazine_sale_ready_patch as sale_ready


def test_sale_ready_items_accept_language_argument():
    items = sale_ready._items_from_context(
        {"report_language": "es", "edge": -0.02, "ev": -0.01},
        ("why_lose", "risk_notes"),
        [],
        3,
        "es",
    )
    assert items[0] == "Ventaja negativa con la cuota actual."


def test_visible_spanish_provider_translations():
    assert sale_ready._es("No recent matching Noticias returned.", "es") == "Sin noticias recientes relacionadas."
    assert sale_ready._es("No recent matching news returned.", "es") == "Sin noticias recientes relacionadas."
    assert sale_ready._es("ACTIVE:", "es") == "ACTIVO:"
    assert sale_ready._es("NO LIVE:", "es") == "SIN EN VIVO:"
    assert sale_ready._es("Odds", "es") == "Cuotas"
    assert sale_ready._es("Price check required before entry.", "es") == "Revisar cuota antes de entrar."
    assert sale_ready._es("Do not chain negative-EV picks.", "es") == "No encadenar señales con VE negativo."


def test_sale_ready_patch_source_has_overlay_polish_plumbing():
    source = inspect.getsource(sale_ready)
    assert "repaint_vs_badge" in source
    assert 'draw.text((x, y), "VS"' in source
    assert "repaint_evidence_body" in source
    assert "repaint_masthead" in source
    assert "report_brand_name" in source
    assert "ACTIVO" in source
    assert "SIN EN VIVO" in source
    assert "Cuotas" in source
    assert "draw_guidance_body" in source
    assert "_es(module._tr(item, lang), lang)" in source
    assert "_sale_ready_risk_chain_v4" in source


def test_sale_ready_patch_preserves_v10_footer_marker():
    patched = sale_ready.apply_magazine_sale_ready_patch(renderer)
    assert patched.NO_MARKET_EXPORT_VERSION == "no_market_metric_v10"
    assert patched.MAGAZINE_STYLE_VERSION.endswith("_sale_ready_risk_chain_v4")
