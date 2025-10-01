import streamlit as st
import pandas as pd

# ---------- GOV.UK CSS ----------
def inject_govuk_css() -> None:
    st.markdown(
        """
        <style>
          [data-testid="stSidebar"] {
            min-width: 320px !important;
            max-width: 320px !important;
          }
          @media (max-width: 800px) {
            [data-testid="stSidebar"] {
              display: none !important;
            }
          }

          .stButton > button {
            background: #00703c !important;
            color: #fff !important;
            border: 2px solid transparent !important;
            border-radius: 0 !important;
            font-weight: 600;
          }
          .stButton > button:hover { filter: brightness(0.95); }
          .stButton > button:focus {
            outline: 3px solid #ffdd00 !important;
            box-shadow: none !important;
          }

          table.custom {
            width: 100%;
            border-collapse: collapse;
            margin: 12px 0;
          }
          table.custom th, table.custom td {
            border: 1px solid #b1b4b6;
            padding: 6px 10px;
            text-align: left;
          }
          table.custom th {
            background: #f3f2f1;
            font-weight: bold;
          }
          table.custom.highlight td {
            background: #fff7e6;
          }
        </style>
        """,
        unsafe_allow_html=True
    )

# ---------- FORMAT HELPERS ----------
def fmt_currency(val) -> str:
    """Format numeric as £ with commas and 2dp"""
    try:
        return f"£{float(val):,.2f}"
    except Exception:
        return str(val)

# ---------- ADJUSTMENT ----------
def adjust_table(df: pd.DataFrame, factor: float) -> pd.DataFrame:
    """Scale numeric/currency values by factor and return formatted copy with all columns."""
    if df is None or df.empty:
        return df

    df_adj = df.copy()

    for col in df_adj.columns:
        if any(key in col for key in ["£", "Cost", "Total", "Price", "Grand", "VAT"]):
            def try_scale(val):
                try:
                    v = float(str(val).replace("£", "").replace(",", ""))
                    return fmt_currency(v * factor)
                except Exception:
                    return val
            df_adj[col] = df_adj[col].map(try_scale)

    return df_adj

# ---------- HTML RENDER ----------
def render_table_html(df: pd.DataFrame, highlight: bool = False) -> str:
    if df is None or df.empty:
        return "<p><em>No data</em></p>"

    df_fmt = df.copy()
    for col in df_fmt.columns:
        if any(key in col for key in ["£", "Cost", "Total", "Price", "Grand", "VAT"]):
            def try_format(x):
                try:
                    return fmt_currency(str(x).replace("£", "").replace(",", ""))
                except Exception:
                    return x
            df_fmt[col] = df_fmt[col].apply(lambda x: try_format(x) if pd.notnull(x) else "")

    cls = "custom highlight" if highlight else "custom"
    return df_fmt.to_html(index=False, classes=cls, border=0, justify="left", escape=False)