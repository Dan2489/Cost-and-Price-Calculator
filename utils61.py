import io
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

          /* Buttons */
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

          /* Tables */
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
        instructor_pct = st.slider("Instructor allocation (%)", 0, 100, 100, step=5)
        prisoner_output = st.slider("Prisoner labour output (%)", 0, 100, default_output, step=5)
    return lock_overheads, instructor_pct, prisoner_output

# -------------------------------
# Formatters
# -------------------------------
def fmt_currency(val) -> str:
    try:
        return f"£{float(val):,.2f}"
    except Exception:
        return str(val)

def _fmt_cell(x):
    if pd.isna(x):
        return ""
    s = str(x).strip()
    if s == "":
        return ""
    try:
        # Already-currency strings
        if "£" in s:
            s_num = s.replace("£", "").replace(",", "")
            return fmt_currency(float(s_num))
        return fmt_currency(float(s))
    except Exception:
        return s

# -------------------------------
# Export functions
# -------------------------------
def export_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

def export_html(
    df_host: pd.DataFrame | None,
    df_prod: pd.DataFrame | None,
    title: str,
    extra_note: str | None = None,
    adjusted_df: pd.DataFrame | None = None,
) -> str:
    styles = """
    <style>
        body { font-family: Arial, sans-serif; color: #0b0c0c; }
        h1, h2, h3 { margin: 0.25rem 0 0.5rem 0; }
        table.custom { width: 100%; border-collapse: collapse; margin: 12px 0; }
        table.custom th, table.custom td { border: 1px solid #b1b4b6; padding: 6px 10px; text-align: left; }
        table.custom th { background: #f3f2f1; font-weight: bold; }
        table.custom.highlight { background-color: #fff8dc; }
        .neg { color: #d4351c; }
        .meta { margin: 0.25rem 0 0.75rem 0; }
        .preamble { margin: 0.75rem 0; }
    </style>
    """
    # Ensure UTF-8 so £ renders correctly and no odd leading characters
    html = f"<html><head><meta charset='utf-8' />{styles}</head><body>"
    html += f"<h1>{title}</h1>"

    # Optional preamble/caption block can be injected by caller into extra_note if desired

    if df_host is not None:
        html += render_table_html(df_host)
    if df_prod is not None:
        html += render_table_html(df_prod)
    if adjusted_df is not None:
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

    # Currency-like columns get formatted; rows with "Reduction" in Item get red in "Item" column
    if "Item" in df_fmt.columns:
        df_fmt["Item"] = df_fmt["Item"].apply(
            lambda x: f"<span style='color:red'>{x}</span>" if isinstance(x, str) and "Reduction" in x else x
        )

    for col in df_fmt.columns:
        if any(key in col for key in ["£", "Cost", "Total", "Price", "Grand"]):
            df_fmt[col] = df_fmt[col].apply(_fmt_cell)

    cls = "custom highlight" if highlight else "custom"
    return df_fmt.to_html(index=False, classes=cls, border=0, justify="left", escape=False)

# -------------------------------
# Adjust table for productivity
# -------------------------------
def adjust_table(df: pd.DataFrame, factor: float) -> pd.DataFrame:
    """Scale numeric/currency values by factor and return formatted copy."""
    if df is None or df.empty:
        return df

    df_adj = df.copy()
    for col in df_adj.columns:
        if any(key in col for key in ["£", "Cost", "Total", "Price", "Grand"]):
            def try_scale(val):
                try:
                    v = float(str(val).replace("£", "").replace(",", ""))
                    return fmt_currency(v * factor)
                except Exception:
                    return val
            df_adj[col] = df_adj[col].map(try_scale)
    return df_adj