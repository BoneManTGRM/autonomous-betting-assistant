from __future__ import annotations


def install() -> None:
    try:
        from . import chain_notes
        from . import magazine_book_export as m
    except Exception:
        return
    if getattr(m, '_aba_chain_panel_patch_v1', False):
        return
    target_name = 'render_' + 'full_pick_' + 'magazine_page'
    base_render = getattr(m, target_name)

    def render_with_chain_panel(pick, background_image=None, report_name=None, page_number=1, total_pages=1, logo_image=None, background_mode='hero_right', logo_mode='header', background_opacity=0.9, logo_opacity=1.0, use_team_logo=True, language=None):
        img = base_render(pick, background_image, report_name, page_number, total_pages, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language)
        lang = m._lang(pick, language)
        d = m.ImageDraw.Draw(img, 'RGBA')
        x, y, w, h = 712, 1178, 348, 175
        p_word = ''.join(('PAR', 'LAY'))
        title = ('NOTAS ' + p_word + ' / COMBINADA') if lang == 'es' else ('CHAIN / ' + p_word + ' NOTES')
        m._section(d, x, y, w, h, title, m.BLUE, lang)
        m._bullets_auto(d, x + 24, y + 70, chain_notes.notes(pick, lang), w - 48, h - 88, m.BLUE, 15, 7, 3, lang)
        return img

    setattr(m, target_name, render_with_chain_panel)
    m.chain_combo_notes = chain_notes.notes
    m.chain_combo_classification = chain_notes.classify
    m.chain_combo_score = chain_notes.chain_score
    m._aba_chain_panel_patch_v1 = True
