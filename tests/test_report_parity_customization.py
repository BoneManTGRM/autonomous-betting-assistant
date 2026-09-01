from __future__ import annotations

from copy import deepcopy

from PIL import Image, ImageChops, ImageDraw

import autonomous_betting_agent.magazine_book_export as magazine
from autonomous_betting_agent import magazine_second_page_patch as page2
from autonomous_betting_agent.active_magazine_export_guard import normalize_row
from autonomous_betting_agent.magazine_sale_ready_patch import _force_truthful_gate, apply_magazine_sale_ready_patch


def _manual_leg(event: str, event_id: str, selection: str, odds: float, probability: float) -> dict:
    return {
        "event": event,
        "manual_event_id": event_id,
        "sport": "Soccer",
        "market_type": "moneyline",
        "selection": selection,
        "prediction": selection,
        "decimal_odds": odds,
        "model_probability": probability,
        "model_market_edge": probability - (1.0 / odds),
        "expected_value_per_unit": probability * odds - 1.0,
        "source_mode": "manual_verified",
        "manual_attestation": True,
        "verification_method": "manual",
        "sportsbook": "Demo Book",
        "captured_at_utc": "now",
        "event_start_utc": "2026-09-01T20:00:00Z",
    }


def _report_row() -> dict:
    row = _manual_leg("North Stars vs Harbor City", "north-harbor", "North Stars", 2.0, 0.60)
    row.update({
        "away_team": "North Stars",
        "home_team": "Harbor City",
        "report_title": "Daily Sports Analysis",
        "advanced_market_rows": [
            _manual_leg("River Athletic vs Mountain FC", "river-mountain", "River Athletic", 1.9, 0.58),
            _manual_leg("Capital United vs Coastal Town", "capital-coastal", "Capital United", 1.85, 0.59),
        ],
        "parlay_price_quotes": [
            {
                "leg_event_ids": ["north-harbor", "river-mountain"],
                "decimal_odds": 3.72,
                "sportsbook": "Demo Book",
                "captured_at_utc": "now",
                "source_mode": "manual_verified",
                "manual_attestation": True,
                "verification_method": "manual",
            },
            {
                "leg_event_ids": ["north-harbor", "river-mountain", "capital-coastal"],
                "decimal_odds": 6.85,
                "sportsbook": "Demo Book",
                "captured_at_utc": "now",
                "source_mode": "manual_verified",
                "manual_attestation": True,
                "verification_method": "manual",
            },
        ],
    })
    return row


def test_page_two_uses_one_parlay_snapshot_per_render(monkeypatch) -> None:
    original = page2.generate_parlay_candidates
    calls = 0

    def counted(pick):
        nonlocal calls
        calls += 1
        return original(pick)

    monkeypatch.setattr(page2, "generate_parlay_candidates", counted)
    page2._draw_second_page(magazine, _report_row(), report_name="ABA Signal PRO")

    assert calls == 1


def test_brand_and_language_do_not_change_page_two_facts() -> None:
    english = _report_row()
    english.update({"report_brand_name": "ABA Signal PRO", "report_language": "en"})
    spanish = deepcopy(english)
    spanish.update({"report_brand_name": "LOS REYES", "report_language": "es"})

    assert page2.build_parlay_report_payload(english) == page2.build_parlay_report_payload(spanish)
    payload = page2.build_parlay_report_payload(english)
    best = payload["recommendations"][0]
    required = {
        "legs",
        "combined_decimal_odds",
        "combined_probability",
        "parlay_implied_probability",
        "combined_ev",
        "minimum_acceptable_odds",
        "suggested_stake_units",
        "profit_at_suggested_stake",
        "pricing_source",
        "correlation_risk",
        "status",
        "cancel_trigger",
        "quoted_book",
        "quoted_timestamp",
    }
    assert required <= set(best)


def test_page_two_brand_customization_changes_header_only() -> None:
    row = _report_row()
    aba = page2._draw_second_page(magazine, row, report_name="ABA Signal PRO")
    custom = page2._draw_second_page(magazine, row, report_name="LOS REYES")

    header_difference = ImageChops.difference(aba.crop((18, 18, 309, 83)), custom.crop((18, 18, 309, 83)))
    factual_body_difference = ImageChops.difference(aba.crop((0, 83, aba.width, aba.height)), custom.crop((0, 83, custom.width, custom.height)))

    assert header_difference.getbbox() is not None
    assert factual_body_difference.getbbox() is None


def test_two_page_renderer_keeps_custom_logo_on_both_pages() -> None:
    renderer = apply_magazine_sale_ready_patch(magazine)
    logo = Image.new("RGBA", (220, 40), (255, 255, 255, 0))
    draw = ImageDraw.Draw(logo)
    draw.rectangle((0, 0, 219, 39), fill=(20, 210, 120, 255))
    draw.rectangle((8, 8, 32, 32), fill=(255, 255, 255, 255))

    plain = renderer.render_full_magazine_book_pages([_report_row()], report_name="ABA Signal PRO")
    branded = renderer.render_full_magazine_book_pages(
        [_report_row()],
        report_name="ABA Signal PRO",
        logo_image=logo,
        logo_mode="header",
    )

    assert len(plain) == len(branded) == 2
    for plain_page, branded_page in zip(plain, branded):
        header_difference = ImageChops.difference(
            plain_page.crop((18, 18, 309, 83)),
            branded_page.crop((18, 18, 309, 83)),
        )
        assert header_difference.getbbox() is not None


def test_demonstration_fixture_never_renders_as_current_play() -> None:
    row = _report_row()
    row.update({
        "demonstration_mode": True,
        "report_data_scope": "Demonstration only - not current betting advice",
        "report_truth_warning": "DEMONSTRATION DATA",
    })

    gated = _force_truthful_gate(row)
    normalized = normalize_row(row)
    parlays, diagnostics = page2.generate_parlay_candidates(row)
    title, _detail, color = page2._final_status(
        row,
        "en",
        parlays=parlays,
        diagnostics=diagnostics,
    )

    assert gated["final_decision"] == "DEMONSTRATION ONLY"
    assert gated["target_stake_units"] == "0.0"
    assert normalized["final_decision"] == "DEMONSTRATION ONLY"
    assert normalized["report_truth_severity"] == "DEMONSTRATION ONLY"
    assert title == "DEMONSTRATION PARLAY CALCULATION"
    assert color == page2.GOLD
    renderer = apply_magazine_sale_ready_patch(magazine)
    assert renderer.normalize_public_risk_label(row, "en") == "DEMO"
    assert renderer.risk_desk_bullets(row, "en") == [
        "Demonstration only",
        "Not current betting advice",
        "Replace all prices first",
    ]


def test_spanish_page_labels_and_demonstration_statuses_are_localized() -> None:
    assert magazine._page_label(1, 2, "es") == "PÁGINA 1 DE 2"
    assert magazine._tr("MONEYLINE: NORTH STARS", "es") == "GANADOR: NORTH STARS"
    assert magazine._tr("DEMONSTRATION DATA", "es") == "DATOS DE DEMOSTRACIÓN"
    assert magazine._tr("DEMONSTRATION ONLY", "es") == "SOLO DEMOSTRACIÓN"
    assert magazine._tr("DEMO PRICE - NOT LIVE API", "es") == "MOMIO DE DEMOSTRACIÓN - NO ES API EN VIVO"


def test_spanish_page_two_generated_copy_has_no_mixed_english_phrases() -> None:
    row = _report_row()
    row.update({"demonstration_mode": True, "report_language": "es-MX"})
    parlays, diagnostics = page2.generate_parlay_candidates(row)
    sections = page2._page_two_sections(row, "es", parlays=parlays, diagnostics=diagnostics)
    title, detail, _color = page2._final_status(row, "es", parlays=parlays, diagnostics=diagnostics)
    rendered = "\n".join(
        [page2._tr(section_title, "es") for section_title, _rows, _section_color in sections]
        + [item for _section_title, rows, _section_color in sections for item in rows]
        + [title, detail]
    )

    for phrase in (
        "DEMONSTRATION PARLAY CALCULATION",
        "Primary anchor",
        "Model P",
        "implied",
        "Page 1 remains",
        "PLAYABLE",
        "Best 3-Leg Parlays",
        "Leg 1",
        "Combined",
        "bankroll",
        "profit",
        "Correlation",
        "Cross-game chains",
        "Same-game parlays",
        "Avoid any market",
        "Markets discovered",
        "eligible legs",
        "Cancel if",
    ):
        assert phrase not in rendered
    assert "Mercados descubiertos" in rendered
    assert "discMás" not in rendered
    assert "3-Selección" not in rendered
    assert "3 selecciones" in rendered
    assert "CÁLCULO DE PARLAY DE DEMOSTRACIÓN" in rendered
    assert "Selección 1" in rendered


def test_synthetic_demo_fixture_is_truthfully_labeled_without_operator_attestation() -> None:
    row = _report_row()
    fixture_fields = {
        "demonstration_mode": True,
        "source_mode": "synthetic_test_fixture",
        "verification_method": "test_fixture",
        "manual_attestation": False,
        "provider": "Synthetic validation fixture",
        "sportsbook": "TEST FIXTURE - NOT A SPORTSBOOK",
    }
    row.update(fixture_fields)
    for market in row["advanced_market_rows"]:
        market.update(fixture_fields)
    for quote in row["parlay_price_quotes"]:
        quote.update(fixture_fields)

    parlays, diagnostics = page2.generate_parlay_candidates(row)
    playable = [candidate for candidate in parlays if candidate.status == page2.PARLAY_PLAYABLE]
    assert diagnostics["eligible_legs"] == 3
    assert playable
    assert all(leg.verification_method == "synthetic_fixture" for leg in playable[0].legs)
    assert playable[0].quote_verification_method == "synthetic_fixture"

    sections = page2._page_two_sections(row, "en", parlays=parlays, diagnostics=diagnostics)
    rendered = "\n".join(item for _title, rows, _color in sections for item in rows)
    assert "DEMONSTRATION CALCULATION" in rendered
    assert " PLAYABLE " not in rendered
    assert "operator" not in rendered.lower()
    assert "manual" not in rendered.lower()
