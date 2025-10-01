import streamlit as st
import pandas as pd

# -------------------------------
# Styling
# -------------------------------
def inject_govuk_css():
    st.markdown(
        """
        <style>
          :root {
            --govuk-green:#00703c;
            --govuk-yellow:#ffdd00;
          }
          .stButton > button {
            background: var(--govuk-green) !important;
            color:#fff !important;
            border:2px solid transparent !important;
            border-radius:0 !important;
            font-weight:600;
          }
          .stButton > button:hover { filter:brightness(0.95); }
          .stButton > button:focus {
            outline:3px solid var(--govuk-yellow) !important;
            box-shadow:none !important;
          }
          table.custom {
            width:100%;
            border-collapse:collapse;
            margin:12px 0;
          }
          table.custom th, table.custom td {
            border:1px solid #b1b4b6;
            padding:6px 10px;
            text-align:left;
          }
          table.custom th {
            background:#f3f2f1;
            font-weight:700;
          }
          table.custom.highlight td {
            background:#fff7e6;
          }
        </style>
        """,
        unsafe_allow_html=True
    )

# -------------------------------
# Format helpers
# -------------------------------
def fmt_currency(val):
    try:
        return f"£{float(str(val).replace('£','').replace(',','')):,.2f}"
    except Exception:
        return str(val)

# -------------------------------
# Sidebar controls
# -------------------------------
def sidebar_controls(default_output: int = 100):
    with st.sidebar:
        st.header("Controls")
        lock_overheads = st.checkbox("Lock overheads to highest instructor salary?", value=False)
        instructor_pct = st.slider("Instructor allocation (%)", 0, 100, 100)
        prisoner_output = st.slider("Prisoner labour output (%)", 0, 100, default_output)
    return lock_overheads, instructor_pct, prisoner_output

# -------------------------------
# Adjust table
# -------------------------------
def adjust_table(df: pd.DataFrame, factor: float) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    for col in out.columns:
        if any(key in str(col) for key in ["£","Cost","Total","Price","VAT","Grand"]):
            def scale(v):
                try:
                    n = float(str(v).replace("£","").replace(",",""))
                    return fmt_currency(n*factor)
                except Exception:
                    return v
            out[col] = out[col].map(scale)
    return out

# -------------------------------
# Render table
# -------------------------------
def render_table_html(df: pd.DataFrame, highlight: bool = False) -> str:
    if df is None or df.empty:
        return "<p><em>No data</em></p>"
    df_fmt = df.copy()
    for col in df_fmt.columns:
        if any(key in str(col) for key in ["£","Cost","Total","Price","VAT","Grand"]):
            df_fmt[col] = df_fmt[col].map(fmt_currency)
    cls = "custom highlight" if highlight else "custom"
    return df_fmt.to_html(index=False, classes=cls, border=0, justify="left", escape=False)

# -------------------------------
# HTML wrapper (fixes £ issue)
# -------------------------------
def build_html_page(title: str, body_html: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    body{{font-family:Arial,Helvetica,sans-serif; font-size:14px; color:#0b0c0c;}}
    table.custom{{width:100%; border-collapse:collapse; margin:12px 0}}
    table.custom th, table.custom td{{border:1px solid #b1b4b6; padding:6px 10px; text-align:left}}
    table.custom th{{background:#f3f2f1; font-weight:700}}
    table.custom.highlight td{{background:#fff7e6}}
  </style>
</head>
<body>
{body_html}
</body>
</html>"""