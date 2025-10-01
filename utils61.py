# utils61.py
import streamlit as st
from io import BytesIO
from datetime import date

def inject_govuk_css():
    st.markdown("""
    <style>
      [data-testid="stSidebar"] { min-width: 300px !important; max-width: 300px !important; }
      @media (max-width: 768px) {
        [data-testid="stSidebar"] { min-width: 0 !important; max-width: 0 !important; }
      }
      :root { --govuk-green: #00703c; --govuk-yellow: #ffdd00; }
      .stButton > button {
        background: var(--govuk-green) !important; color: #fff !important;
        border: 2px solid transparent !important; border-radius: 0 !important; font-weight: 600;
      }
      .results-table table { border-collapse: collapse; margin: 12px 0; width: 100%; }
      .results-table th, .results-table td { border:1px solid #b1b4b6; padding:6px 10px; text-align:left; }
      .results-table th { background:#f3f2f1; }
      .results-table tr.total td { font-weight:700; }
    </style>
    """, unsafe_allow_html=True)

def fmt_currency(v):
    try: return f"£{float(v):,.2f}"
    except Exception: return v

def sidebar_controls(default_output: int, show_output_slider: bool = True, rec_pct: int | None = None):
    with st.sidebar:
        st.header("Controls")
        lock_overheads = st.checkbox("Lock overheads to highest instructor salary", value=False)
        default_alloc = min(100, int(rec_pct)) if isinstance(rec_pct, (int, float)) else 100
        instructor_pct = st.slider("Instructor allocation (%)", 0, 100, default_alloc)
        if rec_pct is not None:
            st.caption(f"Instructor allocation is set to {rec_pct}% (adjust in sidebar if required).")
        prisoner_output = 100
        if show_output_slider:
            prisoner_output = st.slider("Prisoner labour output (%)", 0, 100, int(default_output))
        return lock_overheads, instructor_pct, prisoner_output

def render_summary_table(rows, dev_reduction: bool = False) -> str:
    body = []
    for item, val in rows:
        val_str = fmt_currency(val) if isinstance(val, (int, float)) else (val or "")
        row_cls = " class='total'" if "Total" in str(item) or "Subtotal" in str(item) else ""
        body.append(f"<tr{row_cls}><td>{item}</td><td>{val_str}</td></tr>")
    return f"<div class='results-table'><table><tr><th>Item</th><th>Amount (£)</th></tr>{''.join(body)}</table></div>"

def export_doc(title: str, meta: dict, body_html: str, drop_cols: list[str] = None) -> BytesIO:
    css = """
      <style>
        body{font-family:Arial,Helvetica,sans-serif;color:#0b0c0c;margin:20px;}
        table{width:100%;border-collapse:collapse;margin:12px 0;}
        th,td{border:1px solid #b1b4b6;padding:6px 10px;text-align:left;}
        th{background:#f3f2f1;} tr.total td{font-weight:700;}
      </style>
    """
    header_html = f"<h2>{title}</h2>"
    meta_html = (
        f"<p>Date: {date.today().strftime('%d/%m/%Y')}<br/>"
        f"Customer: {meta.get('customer','')}<br/>"
        f"Prison: {meta.get('prison','')}<br/>"
        f"Region: {meta.get('region','')}</p>"
    )
    closing_note = """
    <p>We are pleased to set out below the terms of our Quotation for the Goods and/or Services you are 
    currently seeking. We confirm that this Quotation and any subsequent contract entered into as a result 
    is, and will be, subject exclusively to our Standard Conditions of Sale of Goods and/or Services a copy 
    of which is available on request. Please note that all prices are exclusive of VAT and carriage costs at 
    time of order of which the customer shall be additionally liable to pay. 
    Prices are indicative and may change based on the final scope and site conditions. 
    Please treat this document as confidential and for the intended recipient only.</p>
    """
    html_doc = f"<!doctype html><html><head><meta charset='utf-8'/><title>{title}</title>{css}</head><body>{header_html}{meta_html}{body_html}{closing_note}</body></html>"
    b = BytesIO(html_doc.encode("utf-8")); b.seek(0); return b
