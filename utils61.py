# utils61.py
import streamlit as st
from io import BytesIO
from datetime import date

def inject_govuk_css():
    st.markdown("""
    <style>
      /* Sidebar – visible, and collapses properly on mobile */
      [data-testid="stSidebar"] { min-width: 300px !important; max-width: 300px !important; }
      @media (max-width: 768px) {
        [data-testid="stSidebar"] { min-width: 0 !important; max-width: 0 !important; }
      }

      /* Buttons & sliders: GOV.UK-ish */
      :root { --govuk-green: #00703c; --govuk-yellow: #ffdd00; }
      .stButton > button {
        background: var(--govuk-green) !important; color: #fff !important;
        border: 2px solid transparent !important; border-radius: 0 !important; font-weight: 600;
      }
      .stButton > button:hover { filter: brightness(0.95); }
      .stButton > button:focus, .stButton > button:focus-visible {
        outline: 3px solid var(--govuk-yellow) !important; outline-offset: 0 !important; box-shadow: 0 0 0 1px #000 inset !important;
      }
      [data-testid="stSlider"] [role="slider"] {
        background: var(--govuk-green) !important; border: 2px solid var(--govuk-green) !important; box-shadow: none !important;
      }
      [data-testid="stSlider"] [role="slider"]:focus,
      [data-testid="stSlider"] [role="slider"]:focus-visible {
        outline: 3px solid var(--govuk-yellow) !important; outline-offset: 0 !important; box-shadow: 0 0 0 1px #000 inset !important;
      }

      /* Centered results tables */
      .results-table { max-width: 900px; margin: 1rem auto; }
      .results-table table { width: auto; border-collapse: collapse; margin: 12px auto; }
      .results-table th, .results-table td { border-bottom: 1px solid #b1b4b6; padding: 8px 12px; text-align: left; }
      .results-table th { background: #f3f2f1; }
      .results-table td.neg { color: #d4351c; }
      .results-table tr.total td { font-weight: 700; }
    </style>
    """, unsafe_allow_html=True)

def fmt_currency(v):
    try:
        return f"£{float(v):,.2f}"
    except Exception:
        return ""

def sidebar_controls(default_output: int, show_output_slider: bool = True, rec_pct: int | None = None):
    with st.sidebar:
        st.header("Controls")
        lock_overheads = st.checkbox("Lock overheads to highest instructor salary", value=False)

        # Instructor allocation (%). Use recommendation if passed, capped 100.
        default_alloc = min(100, int(rec_pct)) if isinstance(rec_pct, (int, float)) else 100
        instructor_pct = st.slider("Instructor allocation (%)", 0, 100, default_alloc)
        if rec_pct is not None:
            st.caption(f"Recommended allocation = {rec_pct}% (based on hours/contracts, capped at 100%)")

        prisoner_output = 100
        if show_output_slider:
            prisoner_output = st.slider("Prisoner labour output (%)", 0, 100, int(default_output))
        return lock_overheads, instructor_pct, prisoner_output

def render_summary_table(rows, dev_reduction: bool = False) -> str:
    body = []
    for item, val in rows:
        val_str = fmt_currency(val) if val is not None else ""
        cls = " class='neg'" if dev_reduction and "reduction" in str(item).lower() else ""
        row_cls = " class='total'" if "Total" in str(item) or "Grand" in str(item) or "Subtotal" in str(item) else ""
        body.append(f"<tr{row_cls}><td>{item}</td><td{cls}>{val_str}</td></tr>")
    return f"<div class='results-table'><table><tr><th>Item</th><th>Amount (£)</th></tr>{''.join(body)}</table></div>"

def export_doc(title: str, meta: dict, body_html: str) -> BytesIO:
    css = """
      <style>
        body{font-family:Arial,Helvetica,sans-serif;color:#0b0c0c;margin:20px;}
        table{width:auto;max-width:900px;margin:12px auto;border-collapse:collapse;}
        th,td{border-bottom:1px solid #b1b4b6;padding:8px;text-align:left;}
        th{background:#f3f2f1;} td.neg{color:#d4351c;} tr.total td{font-weight:700;}
        h1,h2,h3{margin:0.2rem 0;}
      </style>
    """
    header_html = f"<h2>{title}</h2>"
    meta_html = (
        f"<p>Date: {date.today().isoformat()}<br/>"
        f"Customer: {meta.get('customer','')}<br/>"
        f"Prison: {meta.get('prison','')}<br/>"
        f"Region: {meta.get('region','')}</p>"
    )
    html_doc = f"<!doctype html><html><head><meta charset='utf-8'/><title>{title}</title>{css}</head><body>{header_html}{meta_html}{body_html}</body></html>"
    b = BytesIO(html_doc.encode("utf-8")); b.seek(0); return b