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
          }
          table.custom th { background: #f3f2f1; font-weight: bold; }
          table.custom td.neg { color: #d4351c; }
          table.custom tr.grand td { font-weight: bold; }
          table.custom.highlight { background-color: #fff8dc; }

          /* Make sidebar collapsible properly on small screens */
          [data-testid="stSidebar"] { min-width: 360px; max-width: 360px; }
          @media (max-width: 900px) {
            [data-testid="stSidebar"] { min-width: 320px; max-width: 320px; }
          }
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

# -------------------------------
# Export helpers
# -------------------------------
def export_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

def export_csv_rows(rows: list[dict]) -> bytes:
    """Flat CSV for Power BI: list of dicts -> CSV bytes."""
    if not rows:
        return b""
    # Ensure stable column order: collect union then sort, but keep 'communal' first if present
    # We'll just use the order of the first row's keys; subsequent rows can add extra keys, append them at end.
    columns = list(rows[0].keys())
    for r in rows[1:]:
        for k in r.keys():
            if k not in columns:
                columns.append(k)
    buf = io.StringIO()
    pd.DataFrame(rows, columns=columns).to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

def export_html(df_host: pd.DataFrame, df_prod: pd.DataFrame,
                title: str, extra_note: str = None, adjusted_df: pd.DataFrame = None,
                header_block: str | None = None,
                prod_segregated_tables: list[str] | None = None) -> str:
    styles = """
    <style>
        body { font-family: Arial, sans-serif; }
        h1,h2,h3{ margin: 0.2rem 0; }
        table.custom { width: 100%; border-collapse: collapse; margin: 12px 0; }
        table.custom th, table.custom td { border: 1px solid #b1b4b6; padding: 6px 10px; text-align: left; }
        table.custom th { background: #f3f2f1; font-weight: bold; }
        table.custom td.neg { color: #d4351c; }
        table.custom tr.grand td { font-weight: 700; }
        table.custom.highlight { background-color: #fff8dc; }
        .fineprint { font-size: 0.92rem; }
        .quote-preamble { margin: 0.5rem 0 1rem 0; }
    </style>
    """
    html = f"<html><head><meta charset='utf-8' />{styles}</head><body>"
    html += f"<h1>{title}</h1>"
    if header_block:
        html += header_block

    # Standard quote preamble
    html += (
        "<div class='quote-preamble'>"
        "<p>We are pleased to set out below the terms of our Quotation for the Goods and/or Services you are currently seeking. "
        "We confirm that this Quotation and any subsequent contract entered into as a result is, and will be, subject exclusively "
        "to our Standard Conditions of Sale of Goods and/or Services a copy of which is available on request. "
        "Please note that all prices are exclusive of VAT and carriage costs at time of order of which the customer shall be "
        "additionally liable to pay.</p>"
        "</div>"
    )

    if df_host is not None:
        html += "<h3>Host Costs</h3>"
        html += render_table_html(df_host)

    if df_prod is not None:
        html += "<h3>Production Items</h3>"
        html += render_table_html(df_prod)

    if prod_segregated_tables:
        html += "<h3>Production – Segregated Costs (review)</h3>"
        for tbl in prod_segregated_tables:
            html += tbl

    if adjusted_df is not None:
        html += "<h3>Adjusted Costs (for review only)</h3>"
        html += render_table_html(adjusted_df, highlight=True)

    if extra_note:
        html += f"<div style='margin-top:1em' class='fineprint'>{extra_note}</div>"

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
        if any(key in col for key in ["£", "Cost", "Total", "Price", "Grand"]):
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
# Adjust table for productivity (still used for "review only" blocks if needed)
# -------------------------------
def adjust_table(df: pd.DataFrame, factor: float) -> pd.DataFrame:
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