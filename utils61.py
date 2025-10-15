# utils61.py
import io
import pandas as pd
import streamlit as st
from html import escape

# -----------------------------
# GOV.UK styling + Streamlit buttons
# -----------------------------
def inject_govuk_css():
    st.markdown(
        """
        <style>
        body, input, select, textarea {
          font-family: "HelveticaNeue", "Helvetica Neue", Helvetica, Arial, sans-serif;
          font-size: 15px;
        }
        table { width:100%; border-collapse:collapse; margin:10px 0; }
        th, td { padding:6px 10px; text-align:left; border-bottom:1px solid #ddd; }
        th { background:#f3f2f1; font-weight:600; }
        .red-text { color:#d4351c; font-weight:600; }

        /* Make ALL Streamlit buttons GOV.UK green */
        .stButton > button {
          background-color: #00703c !important;
          color: #fff !important;
          border-radius: 4px !important;
          font-weight: 700 !important;
          border: 0 !important;
          padding: 0.4rem 0.9rem !important;
        }
        .stButton > button:hover { background-color:#005a30 !important; }
        </style>
        """,
        unsafe_allow_html=True
    )

# -----------------------------
# Sidebar controls
# -----------------------------
def sidebar_controls(default_output: int):
    with st.sidebar:
        st.header("Controls")
        lock_overheads = st.checkbox("Lock Overheads to Highest Instructor", value=False)
        instructor_pct = 100  # fixed – slider removed
        prisoner_output = st.slider("Prisoner labour output (%)", 0, 100, default_output, step=5)
    return lock_overheads, instructor_pct, prisoner_output

# -----------------------------
# Formatting
# -----------------------------
def fmt_currency(val, dp=2):
    try:
        return f"£{float(val):,.{dp}f}"
    except Exception:
        return "£0.00"

# -----------------------------
# CSV helpers
# -----------------------------
def export_csv_bytes(df: pd.DataFrame) -> bytes:
    sio = io.StringIO()
    df.to_csv(sio, index=False)
    return sio.getvalue().encode("utf-8")

def export_csv_bytes_rows(rows: list[dict]) -> bytes:
    return export_csv_bytes(pd.DataFrame(rows))

def export_csv_single_row(common: dict, df: pd.DataFrame, seg_df: pd.DataFrame | None = None) -> bytes:
    row = dict(common)
    if isinstance(df, pd.DataFrame):
        for i, r in df.iterrows():
            item = str(r.get("Item", f"Row{i+1}")).strip()
            for c in [c for c in df.columns if c != "Item"]:
                row[f"{item} - {c}"] = r.get(c)
    if isinstance(seg_df, pd.DataFrame):
        for i, r in seg_df.iterrows():
            item = str(r.get("Item", f"Seg{i+1}")).strip()
            for c in [c for c in seg_df.columns if c != "Item"]:
                row[f"Seg {item} - {c}"] = r.get(c)
    return export_csv_bytes_rows([row])

# -----------------------------
# Render tables
# -----------------------------
def render_table_html(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "<p><em>No data.</em></p>"
    def cell(v):
        if isinstance(v, (int, float)):
            return fmt_currency(v)
        s = str(v)
        if "Reduction" in s or "discount" in s.lower():
            return f"<span class='red-text'>{escape(s)}</span>"
        return escape(s)
    h = ["<table><thead><tr>"] + [f"<th>{escape(c)}</th>" for c in df.columns] + ["</tr></thead><tbody>"]
    for _, r in df.iterrows():
        h.append("<tr>")
        for c in df.columns:
            h.append(f"<td>{cell(r[c])}</td>")
        h.append("</tr>")
    h.append("</tbody></table>")
    return "".join(h)

# -----------------------------
# HTML export
# -----------------------------
def export_html(host_df, prod_df, *, title="Quote", header_block=None, segregated_df=None) -> bytes:
    html = [f"<h2>{escape(title)}</h2>"]
    if header_block:
        html.append("<table>")
        for k, v in header_block.items():
            html.append(f"<tr><th>{escape(k.title())}</th><td>{escape(str(v))}</td></tr>")
        html.append("</table><br>")
    if isinstance(host_df, pd.DataFrame):
        html.append(render_table_html(host_df))
    if isinstance(prod_df, pd.DataFrame):
        html.append(render_table_html(prod_df))
    if isinstance(segregated_df, pd.DataFrame):
        html.append("<h4>Segregated Costs</h4>")
        html.append(render_table_html(segregated_df))
    return "".join(html).encode("utf-8")

# -----------------------------
# Header block (accepts benefits_desc)
# -----------------------------
def build_header_block(
    *, uk_date: str, customer_name: str, prison_name: str, region: str,
    benefits_desc: str | None = None, **_unused
):
    hb = {
        "Date": uk_date,
        "Customer Name": str(customer_name or "").strip(),
        "Prison Name": str(prison_name or "").strip(),
        "Region": str(region or "").strip(),
    }
    if benefits_desc:
        hb["Additional Prison Benefits"] = str(benefits_desc).strip()
    return hb

# (kept for interface completeness)
def adjust_table(df: pd.DataFrame, factor: float) -> pd.DataFrame:
    df2 = df.copy()
    for col in df2.columns:
        if any(k in col for k in ["£", "Amount", "Total"]):
            try:
                df2[col] = pd.to_numeric(df2[col], errors="coerce") * factor
            except Exception:
                pass
    return df2