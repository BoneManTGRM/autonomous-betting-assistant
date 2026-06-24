from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.bet_catalog import build_bet_catalog, render_betting_magazine, render_pick_card
from autonomous_betting_agent.chain_core import build_candidate_chains
from autonomous_betting_agent.chain_learning_report import chain_learning_summary_to_rows, render_chain_learning_summary
from autonomous_betting_agent.chain_learning_store import load_chain_learning_memory
from autonomous_betting_agent.chain_optimizer_integration import build_chain_optimizer_results
from autonomous_betting_agent.chain_optimizer_report import (
    chain_optimizer_results_to_rows,
    render_chain_optimizer_card,
    render_chain_optimizer_magazine_section,
    split_chain_optimizer_sections,
)
from autonomous_betting_agent.client_profiles import normalize_client_profile
from autonomous_betting_agent.daily_chain_report import (
    build_daily_chain_report,
    build_single_game_chain_magazine,
    daily_chain_report_to_rows,
    render_daily_chain_report,
    render_daily_chain_summary_card,
    render_single_game_chain_magazine,
    sanitize_report_filename,
)
from autonomous_betting_agent.magazine_book_export import (
    pick_full_page_filename,
    render_card_image_png,
    render_compact_magazine_png,
    render_full_magazine_book_pdf,
    render_full_magazine_book_png,
    render_full_magazine_zip,
    render_full_pick_magazine_page_png,
    sanitize_image_filename,
)
from autonomous_betting_agent.script_chain_core import ScriptChainResult, build_same_game_chain_from_script, build_target_payout_chain
from autonomous_betting_agent.script_chain_report import render_game_script_chain_section, render_script_chain_card

st.set_page_config(page_title="Client Magazine", layout="wide")
st.title("Client Magazine")
st.caption("Local-first analytics and report generation only. No execution and no guaranteed outcomes.")

uploaded = st.file_uploader("Upload candidate rows CSV", type=["csv"])

with st.sidebar:
    st.header("Report Names")
    magazine_report_name = st.text_input("Magazine report name", "ABA Signal Pro Betting Magazine")
    daily_report_name = st.text_input("Daily chain report name", "ABA Signal Pro — Daily Chain Report")
    single_game_report_name = st.text_input("Single-game report name", "ABA Signal Pro — Single Game Chain Report")
    full_magazine_book_name = st.text_input("Full magazine book name", "ABA Signal Pro — Full Pick Magazine")
    magazine_background = st.file_uploader("Magazine background image", type=["png", "jpg", "jpeg"])
    background_bytes = magazine_background.getvalue() if magazine_background is not None else None

    st.header("Client Profile")
    name = st.text_input("Name", "Default Client")
    risk_profile = st.selectbox("Mode", ["conservative", "balanced", "aggressive"], index=1)
    unit_size = st.number_input("Unit size", min_value=0.0, value=1.0, step=0.25)
    max_single = st.number_input("Max single exposure", min_value=0.0, value=1.0, step=0.25)
    max_chain_legs = st.slider("Max combined legs", 2, 4, 2 if risk_profile == "conservative" else 3)
    allow_chains = st.checkbox("Allow combined rows", value=True)
    allow_player_markets = st.checkbox("Allow player markets", value=(risk_profile != "conservative"))
    allow_hr_markets = st.checkbox("Allow HR markets", value=(risk_profile == "aggressive"))

    st.header("Daily Chain Report")
    enable_daily_chain_report = st.checkbox("Enable daily chain report", value=True)
    show_single_game_deep_dive = st.checkbox("Show single-game deep dive", value=True)
    auto_select_best_one_game = st.checkbox("Auto-select best one-game chain", value=True)
    show_compact_chain_cards = st.checkbox("Show compact chain cards", value=True)
    max_daily_chain_cards = st.slider("Max chain cards", 3, 10, 5)
    daily_report_style = st.selectbox("Report style", ["Summary", "Magazine", "Both"], index=2)

    st.header("Game Script Chains")
    enable_script_chains = st.checkbox("Enable game-script chains", value=True)
    enable_target_payout = st.checkbox("Enable target-payout chains", value=True)
    stake_amount = st.number_input("Stake amount", min_value=0.0, value=1.0, step=1.0)
    target_payout = st.number_input("Target payout", min_value=0.0, value=2.0, step=1.0)
    min_chain_probability = st.slider("Minimum adjusted probability", 0.0, 1.0, 0.25, 0.01)
    max_risk_score = st.slider("Maximum chain risk score", 1.0, 10.0, 8.0, 0.5)

    st.header("Chain Optimizer v2")
    enable_chain_optimizer_v2 = st.checkbox("Enable Chain Optimizer v2", value=True)
    show_chain_optimizer_cards = st.checkbox("Show Chain Optimizer v2 cards", value=True)
    optimizer_target_payout_mode = st.checkbox("Target payout mode for optimizer", value=False)

    st.header("Chain Learning")
    enable_chain_learning_notes = st.checkbox("Enable chain learning notes", value=True)
    show_failed_leg_patterns = st.checkbox("Show failed-leg patterns", value=True)
    show_straight_better_history = st.checkbox("Show straight-bet-better history", value=True)
    show_target_payout_patterns = st.checkbox("Show target-payout mistake patterns", value=True)

profile = normalize_client_profile({
    "name": name,
    "risk_profile": risk_profile,
    "unit_size": unit_size,
    "max_single_exposure": max_single,
    "max_chain_legs": max_chain_legs,
    "allow_chains": allow_chains,
    "allow_player_markets": allow_player_markets,
    "allow_hr_markets": allow_hr_markets,
})

if uploaded is None:
    st.info("Upload a CSV with game, selection, price, model_probability, and analysis fields to generate the magazine.")
    st.stop()

rows_df = pd.read_csv(uploaded)
rows = rows_df.fillna("").to_dict(orient="records")

def _game_key(row: dict) -> str:
    return str(row.get("game") or row.get("event") or row.get("event_name") or row.get("matchup") or "Unknown")

with st.sidebar:
    game_options = sorted({_game_key(row) for row in rows})
    st.header("Single-game report selector")
    if auto_select_best_one_game or not game_options:
        selected_single_game = "Auto best game"
        st.write("Auto best game")
    else:
        selected_single_game = st.selectbox("Manual game", game_options)

st.subheader("Imported Rows")
st.dataframe(rows_df, use_container_width=True)

chain_groups = build_candidate_chains(rows, profile)
chain_rows = []
if isinstance(chain_groups, dict):
    for value in chain_groups.values():
        if isinstance(value, list):
            chain_rows.extend(chain.as_row() for chain in value)

script_chains: list[ScriptChainResult] = []
if enable_script_chains:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(_game_key(row), []).append(row)
    for game_rows in grouped.values():
        event = game_rows[0]
        result = build_target_payout_chain(event, game_rows, stake_amount, target_payout, profile, minimum_probability=min_chain_probability, maximum_risk_score=max_risk_score) if enable_target_payout else build_same_game_chain_from_script(event, game_rows, profile)
        if isinstance(result, ScriptChainResult):
            script_chains.append(result)

optimizer_results = []
if enable_chain_optimizer_v2:
    optimizer_results = build_chain_optimizer_results(
        rows,
        target_payout=target_payout if optimizer_target_payout_mode else None,
        stake=stake_amount if optimizer_target_payout_mode else None,
        client_profile=profile,
    )

learning_memory = load_chain_learning_memory() if enable_chain_learning_notes else None
learning_section = render_chain_learning_summary(learning_memory) if enable_chain_learning_notes else ""
script_chain_rows = [chain.as_row() for chain in script_chains]
optimizer_rows = chain_optimizer_results_to_rows(optimizer_results)
learning_rows = chain_learning_summary_to_rows(learning_memory) if enable_chain_learning_notes else []
all_rows = rows + chain_rows + script_chain_rows + optimizer_rows
catalog = build_bet_catalog(all_rows)
book_picks = all_rows

daily_report = None
daily_markdown = ""
daily_summary_markdown = ""
single_game_report = None
single_game_markdown = ""
daily_rows = []
if enable_daily_chain_report:
    daily_report = build_daily_chain_report(all_rows, client_profile=profile, max_cards=max_daily_chain_cards, learning_memory=learning_memory)
    daily_markdown = render_daily_chain_report(daily_report, title=daily_report_name)
    daily_summary_markdown = render_daily_chain_summary_card(daily_report, title=daily_report_name)
    daily_rows = daily_chain_report_to_rows(daily_report)
    if show_single_game_deep_dive:
        if auto_select_best_one_game and daily_report.best_single_game is not None:
            target_game = daily_report.best_single_game.game
        elif selected_single_game != "Auto best game":
            target_game = selected_single_game
        else:
            target_game = ""
        game_rows = [row for row in all_rows if _game_key(row) == target_game]
        if game_rows:
            single_game_report = build_single_game_chain_magazine(game_rows, client_profile=profile, learning_memory=learning_memory)
            single_game_markdown = render_single_game_chain_magazine(single_game_report, title=single_game_report_name)
        else:
            single_game_markdown = f"# {single_game_report_name}\n\nNO ONE-GAME CHAIN RECOMMENDED TODAY\nStraight bet or watch-only report available.\n"

magazine = render_betting_magazine(all_rows, title=magazine_report_name, subscriber_name=profile.name) + "\n" + render_game_script_chain_section(script_chains)
if enable_chain_optimizer_v2:
    magazine += "\n" + render_chain_optimizer_magazine_section(optimizer_results)
if enable_daily_chain_report:
    if daily_report_style in {"Summary", "Both"}:
        magazine += "\n" + daily_summary_markdown
    if daily_report_style in {"Magazine", "Both"}:
        magazine += "\n" + daily_markdown
    if show_single_game_deep_dive and single_game_markdown:
        magazine += "\n" + single_game_markdown
if enable_chain_learning_notes:
    magazine += "\n" + learning_section

st.subheader("Catalog Sections")
for section, picks in catalog.items():
    with st.expander(f"{section} ({len(picks)})", expanded=section in {"Best 65%+ Singles", "Conservative Baseball Chains"}):
        if not picks:
            st.write("No qualifying rows in this section.")
        for index, pick in enumerate(picks, start=1):
            st.markdown(render_pick_card(pick))
            compact_png = render_card_image_png(pick, background_image=background_bytes, report_name=magazine_report_name, page_number=index)
            full_page_png = render_full_pick_magazine_page_png(pick, background_image=background_bytes, report_name=full_magazine_book_name, page_number=index, total_pages=len(picks))
            st.download_button("Download Card Image", compact_png, file_name=sanitize_image_filename(f"{section}_{index:02d}", "card", "png"), mime="image/png", key=f"card-{section}-{index}")
            st.download_button("Download Full Magazine Page", full_page_png, file_name=pick_full_page_filename(pick, index), mime="image/png", key=f"full-page-{section}-{index}")
            st.divider()

st.subheader("Best Game-Script Chains")
if not script_chains:
    st.write("NO CHAIN RECOMMENDED")
for chain in script_chains:
    st.markdown(render_script_chain_card(chain))
    st.divider()

if enable_chain_optimizer_v2:
    st.subheader("Chain Bet Optimizer v2")
    sections = split_chain_optimizer_sections(optimizer_results)
    if not optimizer_results:
        st.write("NO CHAIN RECOMMENDED TODAY")
    for section, results in sections.items():
        with st.expander(f"{section} ({len(results)})", expanded=section == "Best Approved Chains"):
            if not results:
                st.write("NO CHAIN RECOMMENDED TODAY" if section == "No Chain Recommended" else "No chains in this section.")
            elif show_chain_optimizer_cards:
                for result in results:
                    st.markdown(render_chain_optimizer_card(result))
                    st.divider()
            else:
                st.dataframe(pd.DataFrame(chain_optimizer_results_to_rows(results)), use_container_width=True)

if enable_daily_chain_report:
    st.subheader("Daily Chain Report")
    if daily_report_style in {"Summary", "Both"}:
        st.markdown(daily_summary_markdown)
    if show_compact_chain_cards and daily_report is not None:
        with st.expander("Compact Daily Chain Cards", expanded=True):
            for index, candidate in enumerate(daily_report.candidates, start=1):
                st.markdown(f"### {index}. {candidate.game}")
                st.write(f"Main Read: {candidate.main_read}")
                st.write(f"Chain: {candidate.chain}")
                st.write(f"Confidence: {'N/A' if candidate.confidence is None else f'{candidate.confidence:.0%}'} | Risk: {candidate.risk_level} | Filler Risk: {candidate.filler_leg_risk}")
                st.write("Why: " + " • ".join(candidate.why_bullets))
                st.divider()
    if daily_report_style in {"Magazine", "Both"}:
        with st.expander("Daily Chain Magazine Markdown", expanded=False):
            st.markdown(daily_markdown)
    st.download_button("Download Daily Chain Markdown", daily_markdown, file_name=sanitize_report_filename(daily_report_name, "md"), mime="text/markdown")
    if daily_rows:
        daily_df = pd.DataFrame(daily_rows)
        st.download_button("Download Daily Chain CSV", daily_df.to_csv(index=False), file_name=sanitize_report_filename(daily_report_name, "csv"), mime="text/csv")

if show_single_game_deep_dive and single_game_markdown:
    st.subheader("Single-Game Chain Magazine")
    st.markdown(single_game_markdown)
    st.download_button("Download Single Game Magazine Markdown", single_game_markdown, file_name=sanitize_report_filename(single_game_report_name, "md"), mime="text/markdown")

if enable_chain_learning_notes:
    st.subheader("Chain Learning Summary")
    st.markdown(learning_section)
    with st.expander("Chain learning pattern tables", expanded=False):
        if learning_rows:
            table = pd.DataFrame(learning_rows)
            if not show_failed_leg_patterns:
                table = table[table["chain_learning_bucket"] != "leg_failure_patterns"]
            if not show_straight_better_history:
                table = table[table["chain_learning_bucket"] != "straight_bet_better_patterns"]
            if not show_target_payout_patterns:
                table = table[table["chain_learning_bucket"] != "target_payout_chase_patterns"]
            st.dataframe(table, use_container_width=True)
        else:
            st.write("No chain learning memory yet. Grade completed chains to build memory.")

st.subheader("Magazine")
st.download_button("Download Markdown", magazine, file_name=sanitize_report_filename(magazine_report_name, "md"), mime="text/markdown")
st.download_button("Download HTML", "<pre>" + magazine.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") + "</pre>", file_name=sanitize_report_filename(magazine_report_name, "html"), mime="text/html")

if book_picks:
    st.subheader("Generated Magazine PNG preview")
    compact_magazine_png = render_compact_magazine_png(book_picks, background_image=background_bytes, report_name=magazine_report_name)
    full_magazine_png = render_full_magazine_book_png(book_picks, background_image=background_bytes, report_name=full_magazine_book_name)
    full_magazine_pdf = render_full_magazine_book_pdf(book_picks, background_image=background_bytes, report_name=full_magazine_book_name)
    full_magazine_zip = render_full_magazine_zip(book_picks, background_image=background_bytes, report_name=full_magazine_book_name)
    st.download_button("Download Magazine PNG", compact_magazine_png, file_name=sanitize_image_filename(magazine_report_name, "compact_magazine", "png"), mime="image/png")
    st.download_button("Download Full Magazine Book PNG", full_magazine_png, file_name=sanitize_image_filename(full_magazine_book_name, "", "png"), mime="image/png")
    st.download_button("Download Full Magazine Book PDF", full_magazine_pdf, file_name=sanitize_image_filename(full_magazine_book_name, "", "pdf"), mime="application/pdf")
    st.download_button("Download Full Magazine ZIP", full_magazine_zip, file_name=sanitize_image_filename(full_magazine_book_name, "", "zip"), mime="application/zip")

flat_catalog = []
for section, picks in catalog.items():
    for pick in picks:
        row = pick.as_dict()
        row["section"] = section
        flat_catalog.append(row)
for chain in script_chains:
    row = chain.as_row()
    row["section"] = "Best Game-Script Chains"
    flat_catalog.append(row)
for row in optimizer_rows:
    row["section"] = "Chain Bet Optimizer v2"
    flat_catalog.append(row)
for row in daily_rows:
    row["section"] = "Daily Chain Report"
    flat_catalog.append(row)
for row in learning_rows:
    row["section"] = "Chain Learning"
    flat_catalog.append(row)
if flat_catalog:
    export_df = pd.DataFrame(flat_catalog)
    st.download_button("Download Catalog CSV", export_df.to_csv(index=False), file_name="client_catalog.csv", mime="text/csv")

st.text_area("Preview", magazine, height=500)
