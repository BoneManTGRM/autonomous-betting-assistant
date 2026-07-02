from __future__ import annotations

import importlib


def install() -> None:
    try:
        renderer = importlib.import_module('autonomous_betting_agent.' + 'magazine_book_export')
        guard = importlib.import_module('autonomous_betting_agent.' + 'active_magazine_export_guard')
        guard.install(renderer)
    except Exception:
        pass
    try:
        sale_module = importlib.import_module('autonomous_betting_agent.' + 'magazine_sale_ready_patch')
        guard = importlib.import_module('autonomous_betting_agent.' + 'active_magazine_export_guard')
        setattr(sale_module, '_force_truthful_gate', guard.normalize_row)
        setattr(sale_module, '_truth_pairs', guard.public_truth_pairs)
    except Exception:
        pass
