from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

import pandas as pd

from .report_product_layer import MagazineBrand, event_text, grouped_report, pct, pick_text, safe_text, value_text


def _escape_pdf_text(value: Any) -> str:
    text = safe_text(value)
    text = text.replace('–', '-').replace('—', '-').replace('“', '"').replace('”', '"').replace('’', "'")
    text = text.encode('latin-1', errors='replace').decode('latin-1')
    return text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def _wrap(text: str, width: int = 96) -> list[str]:
    words = safe_text(text).split()
    if not words:
        return ['']
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = ' '.join(current + [word])
        if len(candidate) > width and current:
            lines.append(' '.join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(' '.join(current))
    return lines


def _brand_dict(brand: MagazineBrand | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(brand, Mapping):
        return dict(brand)
    if is_dataclass(brand):
        return asdict(brand)
    return {}


def _summary_pdf_lines(summary_markdown: str | None) -> list[str]:
    text = safe_text(summary_markdown)
    if not text:
        return []
    lines = ['', 'Report Summary / Explanations', '-----------------------------']
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            lines.append('')
            continue
        if line.startswith('## '):
            lines.append(line[3:].strip())
            lines.append('-' * min(len(line[3:].strip()), 72))
            continue
        if line.startswith('- '):
            line = '* ' + line[2:].strip()
        for wrapped in _wrap(line, 92):
            lines.append(wrapped)
    return lines


def _pdf_lines(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any], *, mode: str = 'consumer', summary_markdown: str | None = None) -> list[str]:
    brand_data = _brand_dict(brand)
    language = safe_text(brand_data.get('language')) or 'en'
    es = language.lower().startswith('es') or 'español' in language.lower()
    title_default = 'Reporte de Análisis Deportivo' if es else 'Sports Analysis Report'
    title = value_text(safe_text(brand_data.get('report_title')) or title_default, language)
    brand_name = safe_text(brand_data.get('brand_name')) or 'ABA Signal Pro'
    tagline = value_text(safe_text(brand_data.get('tagline')) or 'Powered by Reparodynamics', language)
    workspace = safe_text(brand_data.get('workspace_id')) or 'workspace'
    generated = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    technical = mode in {'analyst', 'proof'} or 'analyst' in safe_text(mode).lower()

    section_names = (
        {'best_plays': 'Mejores jugadas', 'watchlist': 'Seguimiento de precio', 'no_play': 'Investigación / aprendizaje'}
        if es else {'best_plays': "Today's Official +EV", 'watchlist': 'Price Watch', 'no_play': 'Research / Learning'}
    )
    labels = {'pick': 'Selección', 'action': 'Acción', 'confidence': 'Confianza', 'risk': 'Riesgo', 'market': 'Mercado'} if es else {'pick': 'Pick', 'action': 'Action', 'confidence': 'Confidence', 'risk': 'Risk', 'market': 'Market'}
    lines = [title, f'{brand_name} - {tagline}', f"{'Workspace' if not es else 'Workspace'}: {workspace}", f"{'Generated' if not es else 'Generado'}: {generated}", '']
    groups = grouped_report(cards)
    for key in ('best_plays', 'watchlist', 'no_play'):
        section = groups.get(key, pd.DataFrame())
        lines += [section_names[key], '-' * len(section_names[key])]
        if section.empty:
            lines.append('No cards in this section.' if not es else 'Sin tarjetas en esta sección.')
        for _, row in section.iterrows():
            rowd = row.to_dict()
            header = event_text(rowd.get('public_event') or rowd.get('event') or 'Matchup', language)
            lines.append(header)
            details = [
                f"{labels['pick']}: {pick_text(rowd.get('public_pick') or rowd.get('prediction'), language)}",
                f"{labels['action']}: {value_text(rowd.get('consumer_action') or rowd.get('recommended_action'), language)}",
                f"{labels['confidence']}: {value_text(rowd.get('confidence_tier'), language)} | {labels['risk']}: {value_text(rowd.get('risk_tier'), language)}",
                f"{labels['market']}: {value_text(rowd.get('market_read'), language)}",
                value_text(rowd.get('why_it_matters'), language),
                value_text(rowd.get('game_preview'), language),
            ]
            if technical:
                details.append(
                    ('Modelo: ' if es else 'Model: ') + pct(rowd.get('model_probability'))
                    + (' | Mercado: ' if es else ' | Market: ') + pct(rowd.get('market_probability'))
                    + ' | Edge: ' + pct(rowd.get('model_market_edge'), signed=True)
                    + ' | EV: ' + pct(rowd.get('expected_value_per_unit'), signed=True)
                    + (' | Momio: ' if es else ' | Odds: ') + safe_text(rowd.get('decimal_price'))
                    + (' | Prueba: ' if es else ' | Proof: ') + (safe_text(rowd.get('proof_id')) or 'N/A')
                )
            for detail in details:
                for wrapped in _wrap(detail, 96):
                    lines.append('  ' + wrapped)
            lines.append('')
    summary_lines = _summary_pdf_lines(summary_markdown)
    if summary_lines:
        lines += summary_lines
    disclaimer = value_text(brand_data.get('disclaimer'), language)
    if disclaimer:
        lines += ['', disclaimer]
    return lines


def _content_stream(page_lines: Iterable[str]) -> str:
    commands = ['BT', '/F1 11 Tf', '50 800 Td']
    first = True
    for line in page_lines:
        if not first:
            commands.append('0 -14 Td')
        first = False
        commands.append(f'({_escape_pdf_text(line)}) Tj')
    commands.append('ET')
    return '\n'.join(commands)


def render_report_pdf(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any], *, mode: str = 'consumer', summary_markdown: str | None = None) -> bytes:
    """Create a dependency-free, valid text PDF for report downloads.

    This intentionally uses a simple built-in PDF writer instead of optional browser or OS tools,
    so Streamlit can offer a one-click PDF download without weakening fail-closed report logic.
    """
    all_lines = _pdf_lines(cards, brand, mode=mode, summary_markdown=summary_markdown)
    pages = [all_lines[i:i + 52] for i in range(0, len(all_lines), 52)] or [['Sin filas de reporte.' if safe_text(_brand_dict(brand).get('language')).lower().startswith('es') else 'No report rows.']]
    objects: list[str] = []
    objects.append('<< /Type /Catalog /Pages 2 0 R >>')
    kids = ' '.join(f'{3 + i * 2} 0 R' for i in range(len(pages)))
    objects.append(f'<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>')
    for i, lines in enumerate(pages):
        page_obj = 3 + i * 2
        content_obj = page_obj + 1
        objects.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> /Contents {content_obj} 0 R >>')
        stream = _content_stream(lines)
        objects.append(f'<< /Length {len(stream.encode("latin-1", errors="replace"))} >>\nstream\n{stream}\nendstream')
    pdf = ['%PDF-1.4']
    offsets = [0]
    current = len(pdf[0]) + 1
    for number, obj in enumerate(objects, start=1):
        offsets.append(current)
        text = f'{number} 0 obj\n{obj}\nendobj'
        pdf.append(text)
        current += len(text.encode('latin-1', errors='replace')) + 1
    xref_offset = current
    xref = ['xref', f'0 {len(objects) + 1}', '0000000000 65535 f ']
    xref.extend(f'{offset:010d} 00000 n ' for offset in offsets[1:])
    trailer = ['trailer', f'<< /Size {len(objects) + 1} /Root 1 0 R >>', 'startxref', str(xref_offset), '%%EOF']
    return ('\n'.join(pdf + xref + trailer)).encode('latin-1', errors='replace')
