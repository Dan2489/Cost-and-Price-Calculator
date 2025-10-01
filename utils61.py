# utils61.py
# Utilities: styling, formatting, sidebar controls, adjusted tables, HTML export

from __future__ import annotations
import streamlit as st
import pandas as pd
from typing import Tuple

# ──────────────────────────────────────────────────────────────────────────────
# Styling
# ──────────────────────────────────────────────────────────────────────────────

def inject_govuk_css() -> None:
    st.markdown(
        """
        <style>
          :root{
            --govuk-green:#00703c;
            --govuk-yellow:#ffdd00;
          }

          /* Sidebar sizing & close on mobile */
          [data-testid="stSidebar"]{
            min-width:300px !important;
            max-width:300px !important;
          }
          @media (max-width: 800px){
            [data-testid="stSidebar"]{
              min-width:0 !important;
              max-width:0 !important;
              width:0 !important;
              overflow:hidden !important;
              padding:0 !important;
              border:0 !important;
            }
          }

          /* Buttons */
          .stButton > button{
            background: var(--govuk-green) !important;
            color:#fff !important;
            border:2px solid transparent !important;
            border-radius:0 !important;
            font-weight:600;
          }
          .stButton > button:hover{ filter:brightness(0.95); }
          .stButton > button:focus{
            outline:3px solid var(--govuk-yellow) !important;
            box-shadow:none !important;
          }

          /* Tables */
          table.custom{
            width:100%;
            border-collapse:collapse;
            margin:12px 0;
          }
          table.custom th, table.custom td{
            border:1px solid #b1b4b6;
            padding:6px 10px;
            text-align:left;
          }
          table.custom th{ background:#f3f2f1; font-weight:700; }
          table.custom.highlight td{ background:#fff7e6; }
        </style>
        """,
        unsafe_allow_html=True
    )

# ──────────────────────────────────────────────────────────────────────────────
# Formatting helpers
# ──────────────────────────────────────────────────────────────────────────────

def fmt_currency(val) -> str:
    try:
        return f"£{float(str(val).replace('£','').replace(',','')):,.2f}"
    except Exception:
        return str(val)

# ──────────────────────────────────────────────────────────────────────────────
# Sidebar controls
# ──────────────────────────────────────────────────────────────────────────────

def sidebar_controls(default_output: int = 100) -> Tuple[bool, int, int]:
    with st.sidebar:
        st.header("Controls")
        lock_overheads = st.checkbox(
            "Lock overheads to highest instructor salary?",
            value=st.session_state.get("lock_overheads", False),
            key="lock_overheads",
        )
        instructor_pct = st.slider(
            "Instructor allocation (%)", 0, 100,
            int(st.session_state.get("instructor_pct", 100)),
            key="instructor_pct",
        )
        prisoner_output = st.slider(
            "Prisoner labour output (%)", 0, 100,
            int(st.session_state.get("prisoner_output", default_output)),
            key="prisoner_output",
        )
    return lock_overheads, instructor_pct, prisoner_output

# ──────────────────────────────────────────────────────────────────────────────
# Table adjustment + HTML helpers
# ──────────────────────────────────────────────────────────────────────────────

_NUMERIC_HINTS = ("£", "Cost", "Total", "Price", "VAT", "Grand")

def _try_number(x):
    try:
        return float(str(x).replace("£","").replace(",",""))
    except Exception:
        return None

def adjust_table(df: pd.DataFrame, factor: float) -> pd.DataFrame:
    if df is None or df.empty: return df
    out = df.copy()
    for col in out.columns:
        if any(key in str(col) for key in _NUMERIC_HINTS):
            out[col] = out[col].map(lambda v: fmt_currency(_try_number(v)*factor) if _try_number(v) is not None else v)
    return out

def render_table_html(df: pd.DataFrame, highlight: bool = False) -> str:
    if df is None or df.empty:
        return "<p><em>No data</em></p>"
    df_fmt = df.copy()
    for col in df_fmt.columns:
        if any(key in str(col) for key in _NUMERIC_HINTS):
            df_fmt[col] = df_fmt[col].map(fmt_currency)
    cls = "custom highlight" if highlight else "custom"
    return df_fmt.to_html(index=False, classes=cls, border=0, justify="left", escape=False)

def build_html_page(title: str, body_html: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    body{{font-family:Arial,Helvetica,sans-serif; font-size:14px; color:#0b0c0c;}}
    h1,h2{{margin:0 0 8px 0}}
    table.custom{{width:100%; border-collapse:collapse; margin:12px 0}}
    table.custom th, table.custom td{{border:1px solid #b1b4b6; padding:6px 10px; text-align:left}}
    table.custom th{{background:#f3f2f1; font-weight:700}}
    table.custom.highlight td{{background:#fff7e6}}
    .caption{{margin:8px 0 16px 0; color:#505a5f}}
  </style>
</head>
<body>
{body_html}
</body>
</html>"""