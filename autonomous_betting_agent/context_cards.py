"""Card wrappers that append optional external context to existing cards."""

from __future__ import annotations

from typing import Any, Mapping

from .bet_catalog import CatalogPick, render_pick_card
from .external_context import format_external_context_for_card
from .script_chain_core import ScriptChainResult
from .script_chain_report import render_script_chain_card


def render_pick_card_with_context(pick: CatalogPick) -> str:
    base = render_pick_card(pick)
    context = getattr(pick, "external_context", None)
    if context is None and isinstance(getattr(pick, "as_dict", None), object):
        context = pick.as_dict().get("external_context")
    context_text = format_external_context_for_card(context)
    return base if not context_text else base + "\n\n" + context_text


def render_row_context(row: Mapping[str, Any]) -> str:
    return format_external_context_for_card(row.get("external_context"))


def render_script_chain_card_with_context(chain: ScriptChainResult) -> str:
    base = render_script_chain_card(chain)
    context = None
    for leg in chain.legs:
        if isinstance(leg, Mapping) and leg.get("external_context"):
            context = leg.get("external_context")
            break
    context_text = format_external_context_for_card(context)
    return base if not context_text else base + "\n\n" + context_text
