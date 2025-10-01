from io import BytesIO
from datetime import date
import pandas as pd
import streamlit as st

def inject_govuk_css() -> None:
    st.markdown(
        """
        <style>
          body { font-family: Arial, Helvetica, sans-serif; }
          table { width:100%; border-collapse: collapse; margin: 12px 0; }
          th, td { border-bottom: 1px solid #b1b4b6; padding: 8px; text-align: left; }
          th { background: #f3f2f1; }
          td.neg { color: #d4351c; }
          tr.grand td { font-weight: 700; }

          /* GOV.UK buttons */
          .stButton > button {
            background: #00703c !important;
            color: #fff !important;
            border: 2px solid transparent !important;
            border-radius: 0 !important;
            font-weight: 600;
          }
          .stButton > button:hover { filter: brightness(0.95); }
          .stButton > button:focus, .stButton > button:focus-visible {
            outline: 3px solid #ffdd00 !important;
            outline-offset: 0 !important;
            box-shadow: 0 0 0 1px #000 inset !important;
          }

          /* Let Streamlit handle collapsing on mobile */
          [data-testid="stSidebar"] {
            min-width: unset !important;
            max-width: unset !important;
          }
        </style>
        """,
        unsafe_allow_html=True
    )

def fmt_currency(v) -> str:
    try:
        return f"£{float(v):,.2f}"
    except Exception:
        return ""

def export_csv_bytes(df: pd.DataFrame) -> BytesIO:
    b = BytesIO()
    df.to_csv(b, index=False)
    b.seek(0)
    return b

def export_html(host_df=None, prod_df=None, title="Quote", extra_note=None) -> BytesIO:
    css = """
      <style>
        body{font-family:Arial,Helvetica,sans-serif;color:#0b0c0c;}
        table{width:100%;border-collapse:collapse;margin:12px 0;}
        th,td{border-bottom:1px solid #b1b4b6;padding:8px;text-align:left;}
        th{background:#f3f2f1;} td.neg{color:#d4351c;} tr.grand td{font-weight:700;}
        h1,h2,h3{margin:0.2rem 0;}
      </style>
    """
    header_html = f"<h2>{title}</h2>"
    meta = (f"<p>Date: {date.today().strftime('%d/%m/%Y')}<br/>"
            f"Customer: {st.session_state.get('customer_name','')}<br/>"
            f"Prison: {st.session_state.get('prison_choice','')}<br/>"
            f"Region: {st.session_state.get('region','')}</p>")
    parts = [css, header_html, meta]
    if host_df is not None:
        parts += ["<h3>Host Costs</h3>", host_df.to_html(index=False, border=1)]
    if prod_df is not None:
        parts += ["<h3>Production Items</h3>", prod_df.to_html(index=False, border=1)]
    if extra_note:
        parts.append(extra_note)
    parts.append("<p>Prices are indicative and may change based on final scope and site conditions.</p>")
    html_doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8" /><title>{title}</title></head><body>{''.join(parts)}</body></html>"""
    b = BytesIO(html_doc.encode("utf-8")); b.seek(0); return b

def sidebar_controls(default_output: int = 100):
    with st.sidebar:
        st.header("Controls")
        lock_overheads = st.checkbox("Lock overheads to highest instructor salary?", value=False)
        instructor_pct = st.slider("Instructor allocation (%)", 0, 100, 100, step=5,
                                   help="How much of instructor salary is applied to this quote")
        prisoner_output = st.slider("Prisoner labour output (%)", 0, 100, default_output, step=5,
                                    help="Effective productivity of prisoner labour")
    return lock_overheads, instructor_pct, prisoner_output

def render_table_html(df: pd.DataFrame) -> str:
    if df is None or not isinstance(df, pd.DataFrame): return ""
    df2 = df.copy()
    currency_cols = {
        "Amount (£)", "Unit Cost (£)", "Unit Price ex VAT (£)", "Unit Price inc VAT (£)",
        "Monthly Total ex VAT (£)", "Monthly Total inc VAT (£)", "Monthly Total (£)",
        "Subtotal", "VAT (20%)", "Grand Total (£/month)"
    }
    for col in df2.columns:
        if col in currency_cols or "£" in str(col):
            try:
                df2[col] = pd.to_numeric(df2[col], errors="coerce").map(lambda x: fmt_currency(x) if pd.notna(x) else "")
            except Exception:
                pass
    return df2.to_html(index=False, border=1)