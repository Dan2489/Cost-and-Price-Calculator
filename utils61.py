import io
import pandas as pd

# -------------------------------
# GOV.UK styling + responsive sidebar
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

          /* Sidebar width + ensure it can close on mobile */
          [data-testid="stSidebar"] {
            min-width: 320px !important;
            max-width: 320px !important;
          }
          @media (max-width: 768px) {
            [data-testid="stSidebar"] {
              min-width: 280px !important;
              max-width: 280px !important;
            }
          }
        </style>
        """,
        unsafe_allow_html=True
    )

# -------------------------------
# Sidebar controls (kept as your app expects)
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
# Formatting helpers
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
    # If already looks like currency, normalise it
    try:
        if "£" in s:
            s_num = s.replace("£", "").replace(",", "")
            return fmt_currency(float(s_num))
        return fmt_currency(float(s))
    except Exception:
        return s

# -------------------------------
# CSV export helpers
# -------------------------------
def export_csv_bytes(df: pd.DataFrame) -> bytes:
    """Legacy export: write the provided DataFrame as-is."""
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

def export_csv_bytes_rows(rows: list[dict], columns_order: list[str] | None = None) -> bytes:
    """Export a list of dict rows (flat, Power BI–friendly)."""
    if not rows:
        rows = [{}]
    df = pd.DataFrame(rows)
    if columns_order:
        # add any missing columns so order stays stable
        for col in columns_order:
            if col not in df.columns:
                df[col] = ""
        df = df[columns_order]
    return export_csv_bytes(df)

# -------------------------------
# HTML export (PDF-ready)
# -------------------------------
def export_html(
    df_host: pd.DataFrame,
    df_prod: pd.DataFrame,
    *,
    title: str,
    header_block: str = None,   # << optional header with date, customer, prison + standard text
    extra_note: str = None,
    adjusted_df: pd.DataFrame = None
) -> str:
    """Render simple, printable HTML with UTF-8 so £ renders correctly."""
    styles = """
    <style>
        body { font-family: Arial, sans-serif; }
        h1, h2, h3 { margin-bottom: 0.35rem; }
        .meta { margin-bottom: 0.8rem; }
        table.custom { width: 100%; border-collapse: collapse; margin: 12px 0; }
        table.custom th, table.custom td { border: 1px solid #b1b4b6; padding: 6px 10px; text-align: left; }
        table.custom th { background: #f3f2f1; font-weight: bold; }
        table.custom.highlight { background-color: #fff8dc; }
        .neg { color:#d4351c; }
    </style>
    """
    html = f"<html><head><meta charset='utf-8' />{styles}</head><body>"
    html += f"<h1>{title}</h1>"

    if header_block:
        html += f"<div class='meta'>{header_block}</div>"

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

def build_header_block(
    *,
    uk_date: str,
    customer_name: str,
    prison_name: str,
    region: str
) -> str:
    """Standard header block with basic details and quotation text."""
    # Standard quotation text (kept verbatim as requested)
    p = (
        "We are pleased to set out below the terms of our Quotation for the Goods and/or Services you are "
        "currently seeking. We confirm that this Quotation and any subsequent contract entered into as a result "
        "is, and will be, subject exclusively to our Standard Conditions of Sale of Goods and/or Services a copy "
        "of which is available on request. Please note that all prices are exclusive of VAT and carriage costs at "
        "time of order of which the customer shall be additionally liable to pay."
    )
    parts = [
        f"<p><strong>Date:</strong> {uk_date}<br/>"
        f"<strong>Customer:</strong> {customer_name}<br/>"
        f"<strong>Prison:</strong> {prison_name}<br/>"
        f"<strong>Region:</strong> {region}</p>",
        f"<p>{p}</p>"
    ]
    return "".join(parts)

# -------------------------------
# Table rendering for app/html
# -------------------------------
def render_table_html(df: pd.DataFrame, highlight: bool = False) -> str:
    if df is None or df.empty:
        return "<p><em>No data</em></p>"

    df_fmt = df.copy()

    # Format currency-like columns
    for col in df_fmt.columns:
        if any(key in col for key in ["£", "Cost", "Total", "Price", "Grand", "Amount"]):
            df_fmt[col] = df_fmt[col].apply(_fmt_cell)

    cls = "custom highlight" if highlight else "custom"
    # escape=False so red reductions or bold markup from caller render properly
    return df_fmt.to_html(index=False, classes=cls, border=0, justify="left", escape=False)

# -------------------------------
# Adjust table (kept for backwards compat)
# -------------------------------
def adjust_table(df: pd.DataFrame, factor: float) -> pd.DataFrame:
    """Scale numeric/currency values by factor and return formatted copy."""
    if df is None or df.empty:
        return df
    df_adj = df.copy()
    for col in df_adj.columns:
        if any(key in col for key in ["£", "Cost", "Total", "Price", "Grand", "Amount"]):
            def try_scale(val):
                try:
                    v = float(str(val).replace("£", "").replace(",", ""))
                    return fmt_currency(v * factor)
                except Exception:
                    return val
            df_adj[col] = df_adj[col].map(try_scale)
    return df_adj