"""Screen-only ABA styling shared with the forest/mint website.

Native Streamlit theme settings in .streamlit/config.toml own widget colors,
including portals, disabled controls, and semantic alerts. These selectors only
style app chrome and the named HTML cards; exported reports are not touched.
"""

APP_THEME_CSS = '''<style>
[data-testid="stMain"] .block-container { max-width: 1180px; padding-left: 28px; padding-right: 28px; }
[data-testid="stMain"], [data-testid="stSidebar"], [data-testid="stMain"] [data-testid="stMarkdownContainer"], [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] { font-family: Inter, ui-sans-serif, system-ui, sans-serif; }
[data-testid="stMain"] h1, [data-testid="stMain"] h2 { font-family: "Iowan Old Style", "Palatino Linotype", Baskerville, Georgia, serif; letter-spacing: -.035em; line-height: 1.15; }
[data-testid="stButton"] button, [data-testid="stDownloadButton"] button, [data-testid="stLinkButton"] a, [data-testid="stPageLink"] a { border-radius: 7px; font-weight: 650; }
[data-testid="stMain"] [data-testid="stBaseButton-primary"]:not(:disabled), [data-testid="stSidebar"] [data-testid="stBaseButton-primary"]:not(:disabled) { background: #b9efc9; color: #082017; border-color: #b9efc9; }
[data-testid="stMain"] [data-testid="stBaseButton-primary"]:not(:disabled):hover, [data-testid="stSidebar"] [data-testid="stBaseButton-primary"]:not(:disabled):hover { background: #ddffe5; color: #082017; border-color: #ddffe5; }
[data-testid="stButton"] button:focus-visible, [data-testid="stDownloadButton"] button:focus-visible, [data-testid="stLinkButton"] a:focus-visible, [data-testid="stPageLink"] a:focus-visible { outline: 3px solid currentColor; outline-offset: 3px; }
[data-testid="stMain"] [data-testid="stBaseButton-primary"]:not(:disabled):focus-visible, [data-testid="stSidebar"] [data-testid="stBaseButton-primary"]:not(:disabled):focus-visible { outline: 2px solid #082017; outline-offset: 2px; box-shadow: 0 0 0 6px #b9efc9; }
[data-testid="stMain"] a[download][href^="data:text/csv"], .aba-safe-download { display: inline-block; padding: .75rem 1rem; border: 1px solid #b9efc9; border-radius: 7px !important; background: #b9efc9 !important; color: #082017 !important; text-decoration: none !important; font-weight: 650; }
[data-testid="stMain"] a[download][href^="data:text/csv"]:hover, .aba-safe-download:hover { background: #ddffe5 !important; }
[data-testid="stMain"] a[download][href^="data:text/csv"]:focus-visible, .aba-safe-download:focus-visible { outline: 2px solid #082017; outline-offset: 2px; box-shadow: 0 0 0 6px #b9efc9; }
[data-testid="stMain"] .aba-summary-hero, [data-testid="stMain"] .aba-mini-card { color: #eef7f4; background: linear-gradient(155deg, #142c23, #102018); border: 1px solid #557b6e; border-radius: 12px; }
[data-testid="stMain"] .aba-metric-card, [data-testid="stMain"] .aba-mini-box { color: #eef7f4; background: #102018; border: 1px solid #557b6e; border-radius: 12px; }
[data-testid="stMain"] .aba-summary-body, [data-testid="stMain"] .aba-metric-label, [data-testid="stMain"] .aba-mini-k, [data-testid="stMain"] .aba-market-note { color: #bad1c6; opacity: 1; }
[data-testid="stMain"] .aba-metric-sub { color: #91aaa0; opacity: 1; }
[data-testid="stMain"] .aba-card-grid { grid-template-columns: repeat(auto-fit, minmax(min(295px, 100%), 1fr)); }
[data-testid="stMain"] .aba-mini-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
[data-testid="stMain"] .aba-mini-card { overflow-wrap: anywhere; }
@media (max-width: 760px) {
  [data-testid="stMain"] .block-container { padding-left: 20px; padding-right: 20px; }
  [data-testid="stMain"] .aba-mini-row { grid-template-columns: 1fr; }
}
</style>'''
