import streamlit as st
import pandas as pd

def chart_dataframe(df: pd.DataFrame):
    """A simple fallback chart generator so the UI works."""
    if df is None or df.empty:
        return
    try:
        # Try to render a bar chart
        st.bar_chart(df.head(20))
    except Exception:
        # If it fails (e.g., text data), just show the table
        st.dataframe(df)