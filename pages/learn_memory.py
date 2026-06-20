from __future__ import annotations

from pathlib import Path

safe_page = Path(__file__).with_name('learn_memory_safe.py')
exec(compile(safe_page.read_text(encoding='utf-8'), str(safe_page), 'exec'))
