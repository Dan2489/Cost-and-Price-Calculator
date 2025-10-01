# utils61.py
import streamlit as st
from io import BytesIO
from datetime import date

# ======================
# GOV.UK CSS Injection
# ======================
def inject_govuk_css() -> None:
    st.markdown(
        """
        <style>
          @media (min-width: 1200px) {
            [data-testid="stSidebar"] { width: 350px !important; }
          }
          @media (max-width: 768px) {
            [data-testid="stSidebar"] {
              width: auto !important; min-width: unset !important; max-width: unset !important;
            }
          }
          :root { --govuk-green: #00703c; --govuk-yellow: #ffdd00; }
          .stButton > button {
            background: var(--govuk-green) !important; color: #fff !important;
            border: 2px solid transparent !important; border-radius: 0 !important; font-weight: 600;
          }
          .stButton > button:hover { filter: brightness(0.95); }
          .stButton > button:focus, .stButton > button:focus-visible {
            outline: 3px solid var(--govuk-yellow) !important;
            outline-offset: 0 !important; box-shadow: 0 0 0 1px #000 inset !important;
          }
          [data-testid="stSlider"] [role="slider"] {
            background: var(--govuk-green) !important; border: 2px solid var(--govuk-green) !important; box-shadow: none !important;
          }
          [data-testid="stSlider"] [role="slider"]:focus,
          [data-testid="stSlider"] [role="slider"]:focus-visible {
            outline: 3px solid var(--govuk-yellow) !important;
            outline-offset: 0 !important; box-shadow: 0 0 0 1px #000 inset !important;
          }
          [data-testid="stSlider"] div[aria-hidden="true"] > div > div { background-color: var(--govuk-green) !important; }

          /* Results tables */
          .results-table { max-width: 900px; margin: 1rem auto; }
          .results-table table { width: 100%; border-collapse: collapse; margin: 12px 0; }
          .results-table th, .results-table td { border-bottom: 1px solid #b1b4b6; padding: 8px; text-align: left; }
          .results-table th { background: #f3f2f1; }
          .results-table td.neg { color: #d4351c; }
          .results-table tr.total td { font-weight: 700; }
        </style>
        """,
        unsafe_allow_html=True
    )

# ======================
# Currency Formatter
# ======================
def fmt_currency(v) -> str:
    try: return f"£{float(v):,.2f}"
    except Exception: return ""

# ======================
# Sidebar Controls
# ======================
def sidebar_controls(global_output_default: int, workshop_hours: float = 37.5, contracts: int = 1):
    with st.sidebar:
        st.header("Controls")
        lock_overheads = st.checkbox("Lock overheads to highest instructor salary", value=False)

        # Instructor allocation slider
        rec = 0.0
        if workshop_hours > 0 and contracts > 0:
            rec = min(100.0, (workshop_hours / 37.5) * (1 / contracts) * 100.0)
        instructor_pct = st.slider("Instructor allocation (%)", 0, 100, int(round(rec)) if rec > 0 else 100)
        if rec > 0: st.caption(f"Recommended: {rec:.0f}%")

        # Prisoner labour output slider (only shown if Production)
        prisoner_output = st.slider("Prisoner labour output (%)", 0, 100, global_output_default)

        return lock_overheads, instructor_pct, prisoner_output

# ======================
# Render Summary Table
# ======================
def render_summary_table(rows, dev_reduction: bool = False) -> str:
    body = []
    for item, val in rows:
        val_str = fmt_currency(val) if val is not None else ""
        cls = ""
        if dev_reduction and "reduction" in str(item).lower(): cls = " class='neg'"
        if "Total" in str(item):
            body.append(f"<tr class='total'><td>{item}</td><td>{val_str}</td></tr>")
        else:
            body.append(f"<tr><td>{item}</td><td{cls}>{val_str}</td></tr>")
    return f"<div class='results-table'><table><tr><th>Item</th><th>Amount (£)</th></tr>{''.join(body)}</table></div>"

# ======================
# Export HTML/PDF
# ======================
def export_doc(title: str, meta: dict, body_html: str) -> BytesIO:
    """Return BytesIO of HTML with consistent GOV.UK style + logo for HTML/PDF exports."""
    css = """
      <style>
        body{font-family:Arial,Helvetica,sans-serif;color:#0b0c0c;margin:20px;}
        table{width:100%;border-collapse:collapse;margin:12px 0;}
        th,td{border-bottom:1px solid #b1b4b6;padding:8px;text-align:left;}
        th{background:#f3f2f1;} td.neg{color:#d4351c;} tr.total td{font-weight:700;}
        h1,h2,h3{margin:0.2rem 0;}
      </style>
    """
    header_html = f"""
    <div style="display:flex; align-items:center; gap:15px; margin-bottom:1rem;">
        <img src="https://raw.githubusercontent.com/Dan2489/Cost-and-Price-Calculator/main/logo.png" style="height:60px;">
        <h2>{title}</h2>
    </div>
    """
    meta_html = (
        f"<p>Date: {date.today().isoformat()}<br/>"
        f"Customer: {meta.get('customer','')}<br/>"
        f"Prison: {meta.get('prison','')}<br/>"
        f"Region: {meta.get('region','')}</p>"
    )
    html_doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8" /><title>{title}</title>{css}</head>
<body>{header_html}{meta_html}{body_html}</body></html>"""
    b = BytesIO(html_doc.encode("utf-8"))
    b.seek(0)
    return b