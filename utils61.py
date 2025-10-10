import io
import re
import pandas as pd

# -------------------------------
# Inject GOV.UK styling
# -------------------------------
def inject_govuk_css():
    import streamlit as st
    st.markdown(
        """
        <style>
          :root {
            --govuk-green: #00703c;
            --govuk-yellow: #ffdd00;
          }
          .stButton > button {
            background: var(--govuk-green) !important;
            color: #fff !important;
            border: 2px solid transparent !important;
            border-radius: 0 !important;
            font-weight: 600;
          }
          .stButton > button:hover { filter: brightness(0.95); }
          .stButton > button:focus {
            outline: 3px solid var(--govuk-yellow) !important;
            box-shadow: 0 0 0 1px #000 inset !important;
          }
          table.custom { width: 100%; border-collapse: collapse; margin: 12px 0; }
          table.custom th, table.custom td {
            border: 1px solid #b1b4b6;
            padding: 6px 10px;
            text-align: left;
            vertical-align: top;
          }
          table.custom th { background: #f3f2f1; font-weight: bold; }
          table.custom td.neg { color: #d4351c; }
          table.custom tr.grand td { font-weight: bold; }
          table.custom.highlight { background-color: #fff8dc; }
          .muted { color:#505a5f; font-size: 0.95rem; }
          .small-note { color:#505a5f; font-size: 0.9rem; }
          .red { color:#d4351c; }
        </style>
        """,
        unsafe_allow_html=True
    )

# -------------------------------
# Sidebar controls
# -------------------------------
def sidebar_controls(default_output: int):
    import streamlit as st
    with st.sidebar:
        st.header("Controls")
        lock_overheads = st.checkbox("Lock overheads to highest instructor", value=False)
        instructor_pct = st.slider("Instructor allocation (%)", 0, 100, 100, step=5, key="ctl_instructor_pct")
        prisoner_output = st.slider("Prisoner labour output (%)", 0, 100, default_output, step=5, key="ctl_prisoner_output")
    return lock_overheads, instructor_pct, prisoner_output

# -------------------------------
# Formatters
# -------------------------------
def fmt_currency(val) -> str:
    try:
        return f"£{float(val):,.2f}"
    except Exception:
        return str(val)

def parse_money_to_float(s: str) -> float:
    """
    Accepts: '£0.05', '0.05', '5p', '5 p', '5 Pence', '5pence', '5 pence', '5P'
    Returns float pounds (e.g., 0.05)
    """
    if s is None:
        return 0.0
    text = str(s).strip()
    if text == "":
        return 0.0
    # Try pence patterns
    if re.fullmatch(r"(?i)\s*\d+(\.\d+)?\s*p(ence)?\s*", text):
        # extract number before p
        num = re.sub(r"(?i)p(ence)?", "", text).strip()
        try:
            return float(num) / 100.0
        except Exception:
            return 0.0
    # remove pound sign and commas
    text = text.replace("£", "").replace(",", "").strip()
    try:
        return float(text)
    except Exception:
        return 0.0

# -------------------------------
# Export functions
# -------------------------------
def export_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

def export_html(df_host: pd.DataFrame, df_prod: pd.DataFrame,
                title: str, extra_note: str = None, adjusted_df: pd.DataFrame = None) -> str:
    styles = """
    <style>
        body { font-family: Arial, sans-serif; }
        table.custom { width: 100%; border-collapse: collapse; margin: 12px 0; }
        table.custom th, table.custom td { border: 1px solid #b1b4b6; padding: 6px 10px; text-align: left; vertical-align: top; }
        table.custom th { background: #f3f2f1; font-weight: bold; }
        table.custom.highlight { background-color: #fff8dc; }
        .muted { color:#505a5f; font-size: 0.95rem; }
        .small-note { color:#505a5f; font-size: 0.9rem; }
        .red { color:#d4351c; }
    </style>
    """
    html = f"<html><head><meta charset='utf-8' />{styles}</head><body>"
    html += f"<h1>{title}</h1>"

    if df_host is not None:
        html += render_table_html(df_host)
    if df_prod is not None:
        html += render_table_html(df_prod)
    if adjusted_df is not None and not adjusted_df.empty:
        html += "<h3>Adjusted Costs (for review only)</h3>"
        html += render_table_html(adjusted_df, highlight=True)

    if extra_note:
        html += f"<div style='margin-top:1em'>{extra_note}</div>"

    html += "</body></html>"
    return html

# -------------------------------
# Table rendering
# -------------------------------
def render_table_html(df: pd.DataFrame, highlight: bool = False) -> str:
    if df is None or df.empty:
        return "<p><em>No data</em></p>"

    df_fmt = df.copy()
    for col in df_fmt.columns:
        if any(key in col for key in ["£", "Cost", "Total", "Price", "Grand", "Monthly"]):
            df_fmt[col] = df_fmt[col].apply(lambda x: _fmt_cell(x))
    cls = "custom highlight" if highlight else "custom"
    return df_fmt.to_html(index=False, classes=cls, border=0, justify="left", escape=False)

def _fmt_cell(x):
    import pandas as pd
    if pd.isna(x):
        return ""
    s = str(x)
    if s.strip() == "":
        return ""
    try:
        if "£" in s:
            s_num = s.replace("£", "").replace(",", "").strip()
            return fmt_currency(float(s_num))
        return fmt_currency(float(s))
    except Exception:
        return s

# -------------------------------
# Adjust table for productivity (kept for any internal use)
# -------------------------------
def adjust_table(df: pd.DataFrame, factor: float) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    df_adj = df.copy()
    for col in df_adj.columns:
        if any(key in col for key in ["£", "Cost", "Total", "Price", "Grand", "Monthly"]):
            def try_scale(val):
                try:
                    v = float(str(val).replace("£", "").replace(",", ""))
                    return fmt_currency(v * factor)
                except Exception:
                    return val
            df_adj[col] = df_adj[col].map(try_scale)
    return df_adj