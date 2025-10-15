# utils61.py
from __future__ import annotations
import io
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet


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
          table.custom {
            width: 100%;
            border-collapse: collapse;
            margin: 12px 0;
            border: 1px solid #b1b4b6;
          }
          table.custom th, table.custom td {
            border: 1px solid #b1b4b6;
            padding: 6px 10px;
            text-align: left;
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
        prisoner_output = st.slider("Prisoner labour output (%)", 0, 100, default_output, step=5)
    return False, 100, prisoner_output


# -------------------------------
# Formatters
# -------------------------------
def fmt_currency(val) -> str:
    try:
        return f"£{float(val):,.2f}"
    except Exception:
        return str(val)


# -------------------------------
# Export functions
# -------------------------------
def export_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


def export_html(df_host: pd.DataFrame, df_prod: pd.DataFrame,
                title: str, header_block: str = "", segregated_df: pd.DataFrame | None = None) -> str:
    styles = """
    <style>
        body { font-family: Arial, sans-serif; }
        table.custom {
            width: 100%;
            border-collapse: collapse;
            margin: 12px 0;
            border: 1px solid #b1b4b6;
        }
        table.custom th, table.custom td {
            border: 1px solid #b1b4b6;
            padding: 6px 10px;
            text-align: left;
        }
        table.custom th { background: #f3f2f1; font-weight: bold; }
        .neg { color: #d4351c; }
    </style>
    """

    html = f"<html><head><meta charset='utf-8' />{styles}</head><body>"
    html += f"<h1>{title}</h1>"
    html += header_block

    if df_host is not None:
        html += render_table_html(df_host)
    if df_prod is not None:
        html += render_table_html(df_prod)
    if segregated_df is not None:
        html += "<h3>Segregated Costs</h3>"
        html += render_table_html(segregated_df)

    html += """
    <p><strong>Quotation Terms:</strong><br>
    We are pleased to set out below the terms of our Quotation for the Goods and/or Services you are
    currently seeking. We confirm that this Quotation and any subsequent contract entered into as a result
    is, and will be, subject exclusively to our Standard Conditions of Sale of Goods and/or Services a copy
    of which is available on request. Please note that all prices are exclusive of VAT and carriage costs
    at time of order of which the customer shall be additionally liable to pay.
    </p>
    """

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
            df_fmt[col] = df_fmt[col].apply(_fmt_cell)
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
# CSV exporters for flat rows
# -------------------------------
def export_csv_single_row(common: dict, df: pd.DataFrame,
                          seg_df: pd.DataFrame | None = None) -> bytes:
    merged = {**common}
    if df is not None and not df.empty:
        for i, (_, row) in enumerate(df.iterrows(), 1):
            for col, val in row.items():
                merged[f"Item {i} - {col}"] = val
    if seg_df is not None and not seg_df.empty:
        for i, (_, row) in enumerate(seg_df.iterrows(), 1):
            for col, val in row.items():
                merged[f"Seg Item {i} - {col}"] = val
    csv = pd.DataFrame([merged])
    buf = io.StringIO()
    csv.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


def export_csv_bytes_rows(rows: list[dict]) -> bytes:
    df = pd.DataFrame(rows)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


# -------------------------------
# Header block builder
# -------------------------------
def build_header_block(uk_date: str, customer_name: str, prison_name: str,
                       region: str, benefits_desc: str | None = None) -> str:
    html = f"""
    <p><strong>Date:</strong> {uk_date}<br>
    <strong>Customer:</strong> {customer_name}<br>
    <strong>Prison:</strong> {prison_name}<br>
    <strong>Region:</strong> {region}</p>
    """
    if benefits_desc:
        html += f"<p><strong>Additional Prison Benefits:</strong> {benefits_desc}</p>"
    return html