# utils61.py
import io
import base64
import pandas as pd
import streamlit as st
from datetime import date
from io import BytesIO
from html import escape

# -------------------------------------------------------------
# GOV.UK styling injection
# -------------------------------------------------------------
def inject_govuk_css():
    st.markdown(
        """
        <style>
        body, input, select, textarea {
            font-family: "HelveticaNeue", "Helvetica Neue", Helvetica, Arial, sans-serif;
            font-size: 15px;
        }
        .govuk-button {
            background-color: #00703c;
            border-radius: 4px;
            color: white !important;
            padding: 8px 16px;
            font-weight: bold;
        }
        .govuk-button:hover {
            background-color: #005a30;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            margin-bottom: 10px;
        }
        th, td {
            padding: 6px 10px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background: #f3f2f1;
            font-weight: 600;
        }
        tr:last-child td {
            border-bottom: none;
        }
        .red-text {
            color: red;
            font-weight: 600;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# -------------------------------------------------------------
# Sidebar controls
# -------------------------------------------------------------
def sidebar_controls(default_output):
    with st.sidebar:
        st.header("Controls")
        lock_overheads = st.checkbox("Lock Overheads to Highest Instructor", value=False)
        instructor_pct = 100  # fixed now — slider removed
        prisoner_output = st.slider("Prisoner labour output (%)", 0, 100, default_output, step=5)
    return lock_overheads, instructor_pct, prisoner_output


# -------------------------------------------------------------
# Formatting helpers
# -------------------------------------------------------------
def fmt_currency(val, dp=2):
    try:
        return f"£{float(val):,.{dp}f}"
    except Exception:
        return "£0.00"


# -------------------------------------------------------------
# CSV export helpers
# -------------------------------------------------------------
def export_csv_bytes(df: pd.DataFrame):
    output = io.StringIO()
    df.to_csv(output, index=False)
    return output.getvalue().encode("utf-8")


def export_csv_bytes_rows(rows: list[dict]):
    df = pd.DataFrame(rows)
    return export_csv_bytes(df)


def export_csv_single_row(common: dict, df: pd.DataFrame, seg_df: pd.DataFrame | None = None):
    """
    Flattened single-line CSV export with all input columns (common)
    and dynamic output columns (from df and seg_df).
    """
    row = common.copy()
    if isinstance(df, pd.DataFrame):
        for idx, r in df.iterrows():
            item = str(r.get("Item", f"Row{idx+1}")).strip()
            for c in [col for col in df.columns if col != "Item"]:
                key = f"{item} - {c}"
                row[key] = r.get(c)
    if isinstance(seg_df, pd.DataFrame):
        for idx, r in seg_df.iterrows():
            item = str(r.get("Item", f"Seg{idx+1}")).strip()
            for c in [col for col in seg_df.columns if col != "Item"]:
                key = f"Seg {item} - {c}"
                row[key] = r.get(c)
    return export_csv_bytes_rows([row])


# -------------------------------------------------------------
# HTML Export (for PDF-ready HTML)
# -------------------------------------------------------------
def export_html(host_df, prod_df, *, title="Quote", header_block=None, segregated_df=None):
    html = f"<h2>{escape(title)}</h2>"
    if header_block:
        html += "<table>"
        for k, v in header_block.items():
            html += f"<tr><th>{escape(k.title())}</th><td>{escape(str(v))}</td></tr>"
        html += "</table><br>"
    if isinstance(host_df, pd.DataFrame):
        html += render_table_html(host_df)
    if isinstance(prod_df, pd.DataFrame):
        html += render_table_html(prod_df)
    if isinstance(segregated_df, pd.DataFrame):
        html += "<h4>Segregated Costs</h4>"
        html += render_table_html(segregated_df)
    return html.encode("utf-8")


# -------------------------------------------------------------
# Render DataFrame to styled HTML table
# -------------------------------------------------------------
def render_table_html(df: pd.DataFrame, highlight=False):
    if df is None or df.empty:
        return "<p><em>No data.</em></p>"

    def style_cell(v):
        if isinstance(v, (float, int)):
            return fmt_currency(v)
        s = str(v)
        if "Reduction" in s or "discount" in s.lower():
            return f"<span class='red-text'>{escape(s)}</span>"
        return escape(s)

    html = "<table><thead><tr>"
    for col in df.columns:
        html += f"<th>{escape(col)}</th>"
    html += "</tr></thead><tbody>"
    for _, row in df.iterrows():
        html += "<tr>"
        for col in df.columns:
            html += f"<td>{style_cell(row[col])}</td>"
        html += "</tr>"
    html += "</tbody></table>"
    return html


# -------------------------------------------------------------
# Table adjustments (for productivity slider)
# -------------------------------------------------------------
def adjust_table(df: pd.DataFrame, factor: float):
    df2 = df.copy()
    for col in df2.columns:
        if "£" in col or "Amount" in col or "Total" in col:
            try:
                df2[col] = pd.to_numeric(df2[col], errors="coerce") * factor
            except Exception:
                pass
    return df2


# -------------------------------------------------------------
# Header block (fixed to support benefits_desc)
# -------------------------------------------------------------
def build_header_block(
    *,
    uk_date: str,
    customer_name: str,
    prison_name: str,
    region: str,
    benefits_desc: str | None = None,
    **_ignore,
):
    """
    Returns dict for header export. Accepts optional benefits_desc.
    """
    hb = {
        "Date": uk_date,
        "Customer Name": str(customer_name or "").strip(),
        "Prison Name": str(prison_name or "").strip(),
        "Region": str(region or "").strip(),
    }
    if benefits_desc:
        hb["Additional Prison Benefits"] = str(benefits_desc).strip()
    return hb