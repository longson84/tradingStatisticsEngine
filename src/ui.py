"""Shared Streamlit UI utilities."""
import streamlit as st
import plotly.graph_objects as go


def plot_chart(fig: go.Figure) -> None:
    """Render a Plotly figure, compatible with both old and new Streamlit versions."""
    try:
        st.plotly_chart(fig, width="stretch")
    except TypeError:
        st.plotly_chart(fig, use_container_width=True)
