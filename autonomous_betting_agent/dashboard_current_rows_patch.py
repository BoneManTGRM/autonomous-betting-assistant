from __future__ import annotations

from typing import Any

import pandas as pd


def install(module: Any) -> Any:
    original = getattr(module, "_read_sources", None)
    if not callable(original) or getattr(module, "_ABA_CURRENT_ROWS_PATCH", False):
        return module

    def patched_read_sources(workspace_id: str, **kwargs: Any):
        new_kwargs = dict(kwargs)
        uploads = new_kwargs.get("uploads")
        use_session = bool(new_kwargs.get("use_session"))
        if uploads or use_session:
            first = original(workspace_id, **{**new_kwargs, "use_db": False})
            try:
                if first[1] is not None and not first[1].empty:
                    return first
            except Exception:
                pass
        return original(workspace_id, **kwargs)

    module._read_sources = patched_read_sources
    module._ABA_CURRENT_ROWS_PATCH = True
    return module
