"""Streamlit rendering helpers specific to the rarity analysis pack."""
from typing import List

import pandas as pd
import streamlit as st

from src.shared.constants import COLOR_ACTIVE, COLOR_GROUP
from src.analysis.rarity.events import NPEvent
from src.analysis.rarity.tables import build_np_event_tree


def render_np_stats_table(stats_df: pd.DataFrame) -> None:
    st.subheader("📊 Thống kê các sự kiện NP")
    if stats_df.empty:
        return

    highlight_mask = stats_df["_highlight"].tolist()
    display_df = stats_df.drop(columns=["_highlight"])

    def _row_style(row: pd.Series):
        if highlight_mask[row.name]:
            return [COLOR_ACTIVE] * len(row)
        return [""] * len(row)

    styled = display_df.style.apply(_row_style, axis=1)
    height = 38 + len(display_df) * 35
    st.dataframe(styled, hide_index=True, use_container_width=True, height=height)


def render_event_tree(np_events: List[NPEvent], qr_threshold: int) -> None:
    df = build_np_event_tree(np_events, qr_threshold)
    if df.empty:
        st.info("No significant events (all classified as Quick Recoveries).")
        return

    unrecovered_mask = df["_unrecovered"].tolist()
    level_zero_mask = (df["Lv"] == 0).tolist()
    display_df = df.drop(columns=["_unrecovered"])

    def _row_style(row: pd.Series):
        i = row.name
        if unrecovered_mask[i]:
            return [COLOR_ACTIVE] * len(row)
        if level_zero_mask[i]:
            return [COLOR_GROUP] * len(row)
        return [""] * len(row)

    styled = display_df.style.apply(_row_style, axis=1)
    height = 38 + min(len(display_df), 20) * 35

    st.dataframe(
        styled,
        hide_index=True,
        use_container_width=True,
        height=height,
        column_config={
            "Lv":       st.column_config.NumberColumn("Lv"),
            "Start":    st.column_config.TextColumn("Start Date"),
            "Zone":     st.column_config.TextColumn("Zone"),
            "Entry":    st.column_config.TextColumn("Entry"),
            "Low":      st.column_config.TextColumn("Low"),
            "Low Date": st.column_config.TextColumn("Low Date"),
            "MAE %":    st.column_config.TextColumn("MAE %"),
            "→ Low":    st.column_config.NumberColumn("→ Low"),
            "Recovery": st.column_config.TextColumn("Recovery"),
            "→ Rec":    st.column_config.TextColumn("→ Rec"),
            "Children": st.column_config.NumberColumn("Children"),
        },
    )

    n_active = sum(unrecovered_mask)
    n_total = len(display_df)
    n_lv0 = sum(level_zero_mask)
    st.caption(
        f"{n_total} events shown  •  "
        f"🟡 {n_active} active (unrecovered)  •  "
        f"🔵 {n_lv0} top-level (Lv 0)  •  "
        f"QR threshold: ≤ {qr_threshold} days (hidden)"
    )
