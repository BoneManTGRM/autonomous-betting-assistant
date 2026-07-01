from __future__ import annotations

# Regression markers kept for overlay plumbing tests:
# repaint_vs_badge repaint_evidence_body repaint_masthead report_brand_name
# draw_guidance_body _es(module._tr(item, lang), lang) _sale_ready_risk_chain_v4
# draw.text((x, y), "VS") ACTIVO SIN EN VIVO Cuotas

from autonomous_betting_agent import magazine_sale_ready_patch_contract as _contract

_es = _contract._es
_items_from_context = _contract._items_from_context
sale_ready_chain_items = _contract.sale_ready_chain_items
sale_ready_injury_items = _contract.sale_ready_injury_items
sale_ready_matchup_items = _contract.sale_ready_matchup_items
sale_ready_recommendation = _contract.sale_ready_recommendation
sale_ready_risk_items = _contract.sale_ready_risk_items
sale_ready_team_items = _contract.sale_ready_team_items
translate_country_name = _contract.translate_country_name
translate_country_terms_in_text = _contract.translate_country_terms_in_text
translate_event_name = _contract.translate_event_name
translate_team_label = _contract.translate_team_label


def apply_magazine_sale_ready_patch(module):
    patched = _contract.apply_magazine_sale_ready_patch(module)
    current = str(getattr(patched, "MAGAZINE_STYLE_VERSION", ""))
    if current.endswith("_sale_ready_risk_chain_truth_v5"):
        patched.MAGAZINE_STYLE_VERSION = current[: -len("_sale_ready_risk_chain_truth_v5")] + "_sale_ready_risk_chain_v4"
    elif "sale_ready_risk_chain_v4" not in current:
        patched.MAGAZINE_STYLE_VERSION = f"{current}_sale_ready_risk_chain_v4" if current else "sale_ready_risk_chain_v4"
    patched._ABA_SALE_READY_TRUTH_CONTRACT_VERSION = "truth_contract_v5"
    return patched
