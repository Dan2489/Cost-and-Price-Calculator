# utils61.py
# Small, shared helpers for styling, formatting, sidebar controls and HTML tables.

from __future__ import annotations
import streamlit as st
import pandas as pd
from typing import Tuple

# ──────────────────────────────────────────────────────────────────────────────
# Styling (kept minimal; doesn’t change your app’s look and feel)
# ──────────────────────────────────────────────────────────────────────────────

def inject_govuk_css() -> None:
    """Inject compact GOV.UK-ish styling and make the sidebar behave on mobile."""
    st.markdown(
        """
        <style>
          :root{
            --govuk-green:#00703c;
            --govuk-yellow:#ffdd00;
          }

          /* Sidebar: compact and actually closes on mobile */
          [data-testid="stSidebar"]{
            min-width:300px !important;
            max-width:300px !important;
          }
          @media (max-width: 800px){
            [data-testid="stSidebar"]{
              min-width: 0 !important;
              max-width: 0 !important;
              width: 0 !important;
              overflow: hidden !important;
              padding: 0 !important;
              border: 0 !important;
            }
          }

          /* Primary buttons (keep your green) */
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
            box-shadow: none !important;
          }

          /* Data tables (app + HTML export share this class) */
          table.custom{
            width:100%;
            border-collapse:collapse;
            margin:12px 0;
          }
          table.custom th, table.custom td{
            border:1px solid #b1b4b6;
            padding:6px 10px;
            text-align:left;
            vertical-align:top;
          }
          table.custom th{
            background:#f3f2f1;
            font-weight:700;
          }
          table.custom.highlight td{
            background:#fff7e6;
          }

          /* Headline (leave the one you already use) */
          .govuk-heading-l{ font-weight:700; font-size:1.75rem; line-height:1.2; }

          /* Minor: stop wide tables from stretching oddly inside containers */
          .block-container{ padding-top: 1rem; }
        </style>
        """,
        unsafe_allow_html=True
    )

# ──────────────────────────────────────────────────────────────────────────────
# Formatting helpers
# ──────────────────────────────────────────────────────────────────────────────

def fmt_currency(val) -> str:
    """Format a value as £ with commas and 2dp. Returns original text if not numeric."""
    try:
        return f"£{float(str(val).replace('£','').replace(',','')):,.2f}"
    except Exception:
        return str(val)

# ──────────────────────────────────────────────────────────────────────────────
# Sidebar controls (exact names expected by newapp61.py)
# ──────────────────────────────────────────────────────────────────────────────

def sidebar_controls(default_output: int = 100) -> Tuple[bool, int, int]:
    """
    Returns: (lock_overheads, instructor_pct, prisoner_output)
    Only UI – no business logic here.
    """
    with st.sidebar:
        st.header("Controls")
        lock_overheads = st.checkbox(
            "Lock overheads to highest instructor salary?",
            value=st.session_state.get("lock_overheads", False),
            key="lock_overheads",
        )
        instructor_pct = st.slider(
            "Instructor allocation (%)",
            0, 100,
            int(st.session_state.get("instructor_pct", 100)),
            key="instructor_pct",
        )
        prisoner_output = st.slider(
            "Prisoner labour output (%)",
            0, 100,
            int(st.session_state.get("prisoner_output", default_output)),
            key="prisoner_output",
        )
    return lock_overheads, instructor_pct, prisoner_output

# ──────────────────────────────────────────────────────────────────────────────
# Table adjustment + HTML helpers (used by productivity slider + downloads)
# ──────────────────────────────────────────────────────────────────────────────

_NUMERIC_COL_HINTS = ("£", "Cost", "Total", "Price", "VAT", "Grand")

def _try_to_number(x):
    try:
        return float(str(x).replace("£","").replace(",",""))
    except Exception:
        return None

def adjust_table(df: pd.DataFrame, factor: float) -> pd.DataFrame:
    """
    Return a copy of df where numeric-looking values in money/total columns are
    multiplied by `factor` and re-formatted as currency.

    We do not remove any columns or rows; this keeps alignment intact.
    """
    if df is None or df.empty:
        return df

    out = df.copy()

    def should_scale_col(col_name: str) -> bool:
        name = str(col_name)
        return any(key in name for key in _NUMERIC_COL_HINTS)

    for col in out.columns:
        if should_scale_col(col):
            def scale_cell(v):
                num = _try_to_number(v)
                return fmt_currency(num * factor) if num is not None else v
            out[col] = out[col].map(scale_cell)

    return out

def render_table_html(df: pd.DataFrame, highlight: bool = False) -> str:
    """Render a DataFrame to HTML with our class and left alignment + no escaping of £."""
    if df is None or df.empty:
        return "<p><em>No data</em></p>"

    # Format money-ish columns for safety
    df_fmt = df.copy()
    for col in df_fmt.columns:
        if any(key in str(col) for key in _NUMERIC_COL_HINTS):
            df_fmt[col] = df_fmt[col].map(lambda v: fmt_currency(v))

    cls = "custom highlight" if highlight else "custom"
    return df_fmt.to_html(index=False, classes=cls, border=0, justify="left", escape=False)

def build_html_page(title: str, body_html: str) -> str:
    """
    Wrap provided body HTML in a minimal, UTF-8 page with the same table CSS.
    Fixes 'Â£' issue by forcing UTF-8.
    """
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    body{{font-family:Arial,Helvetica,sans-serif; font-size:14px; color:#0b0c0c;}}
    h1,h2{{margin:0 0 8px 0}}
    table.custom{{width:100%; border-collapse:collapse; margin:12px 0}}
    table.custom th, table.custom td{{border:1px solid #b1b4b6; padding:6px 10px; text-align:left; vertical-align:top}}
    table.custom th{{background:#f3f2f1; font-weight:700}}
    table.custom.highlight td{{background:#fff7e6}}
    .caption{{margin:8px 0 16px 0; color:#505a5f}}
  </style>
</head>
<body>
{body_html}
</body>
</html>"""