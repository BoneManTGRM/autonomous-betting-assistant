from __future__ import annotations

from io import BytesIO
from typing import Any, Iterable
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image, ImageDraw, ImageFont

from autonomous_betting_agent.report_export_verification import manifest_json, verify_rows_for_export

RUNTIME_GATE_VERSION = "report_export_runtime_gate_v1"


def _blocked_png_bytes(manifest: str, width: int = 1080, height: int = 1620) -> bytes:
    img = Image.new("RGB", (width, height), (244, 235, 211))
    draw = ImageDraw.Draw(img)
    try:
        title_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 54)
        body_font = ImageFont.truetype("DejaVuSans.ttf", 26)
    except Exception:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
    draw.rectangle((32, 32, width - 32, 132), fill=(13, 14, 16))
    draw.text((60, 58), "EXPORT BLOCKED", fill=(255, 255, 255), font=title_font)
    y = 180
    lines = [
        "Normal magazine export was blocked by the live verification gate.",
        "Rows must pass fresh provider timestamp, odds, event, market, line, and snapshot checks.",
        "This page is a diagnostic notice, not a verified betting report.",
        "",
    ]
    lines.extend(str(manifest).splitlines()[:28])
    for line in lines:
        draw.text((60, y), line[:110], fill=(14, 17, 21), font=body_font)
        y += 34
        if y > height - 80:
            break
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _blocked_pdf_bytes(manifest: str) -> bytes:
    png = _blocked_png_bytes(manifest)
    img = Image.open(BytesIO(png)).convert("RGB")
    out = BytesIO()
    img.save(out, format="PDF", resolution=100.0)
    return out.getvalue()


def _blocked_zip_bytes(manifest: str) -> bytes:
    out = BytesIO()
    with ZipFile(out, "w", ZIP_DEFLATED) as zf:
        zf.writestr("EXPORT_BLOCKED_manifest.json", manifest)
        zf.writestr("EXPORT_BLOCKED.png", _blocked_png_bytes(manifest))
    return out.getvalue()


def _verify(picks: Iterable[Any]) -> tuple[list[dict[str, Any]], str, bool]:
    result = verify_rows_for_export(list(picks or []), source_mode="runtime_export", run_capture=True)
    manifest = manifest_json(result)
    return result.rows, manifest, result.export_allowed


def install(module: Any) -> Any:
    if getattr(module, "_ABA_REPORT_EXPORT_RUNTIME_GATE", "") == RUNTIME_GATE_VERSION:
        return module
    original_pdf = getattr(module, "render_full_magazine_book_pdf", None)
    original_png = getattr(module, "render_full_magazine_book_png", None)
    original_zip = getattr(module, "render_full_magazine_zip", None)
    original_pages = getattr(module, "render_full_magazine_book_pages", None)

    if callable(original_pages):
        def guarded_pages(picks: Iterable[Any], *args: Any, **kwargs: Any):
            rows, manifest, allowed = _verify(picks)
            if not allowed:
                module._ABA_LAST_EXPORT_BLOCK_MANIFEST = manifest
                return []
            return original_pages(rows, *args, **kwargs)
        module.render_full_magazine_book_pages = guarded_pages

    if callable(original_pdf):
        def guarded_pdf(picks: Iterable[Any], *args: Any, **kwargs: Any) -> bytes:
            rows, manifest, allowed = _verify(picks)
            if not allowed:
                module._ABA_LAST_EXPORT_BLOCK_MANIFEST = manifest
                return _blocked_pdf_bytes(manifest)
            return original_pdf(rows, *args, **kwargs)
        module.render_full_magazine_book_pdf = guarded_pdf

    if callable(original_png):
        def guarded_png(picks: Iterable[Any], *args: Any, **kwargs: Any) -> bytes:
            rows, manifest, allowed = _verify(picks)
            if not allowed:
                module._ABA_LAST_EXPORT_BLOCK_MANIFEST = manifest
                return _blocked_png_bytes(manifest)
            return original_png(rows, *args, **kwargs)
        module.render_full_magazine_book_png = guarded_png

    if callable(original_zip):
        def guarded_zip(picks: Iterable[Any], *args: Any, **kwargs: Any) -> bytes:
            rows, manifest, allowed = _verify(picks)
            if not allowed:
                module._ABA_LAST_EXPORT_BLOCK_MANIFEST = manifest
                return _blocked_zip_bytes(manifest)
            return original_zip(rows, *args, **kwargs)
        module.render_full_magazine_zip = guarded_zip

    module._ABA_REPORT_EXPORT_RUNTIME_GATE = RUNTIME_GATE_VERSION
    return module
