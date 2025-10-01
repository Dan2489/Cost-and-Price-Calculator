from io import BytesIO
from datetime import date
import pandas as pd
import streamlit as st

# Inject CSS for GOV.UK style
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
        </style>
        """,
        unsafe_allow_html=True
    )

# Format currency
def fmt_currency(v) -> str:
    try:
        return f"£{float(v):,.2f}"
    except Exception:
        return ""

# Export DataFrame as CSV bytes
def export_csv_bytes(df: pd.DataFrame) -> BytesIO:
    b = BytesIO()
    df.to_csv(b, index=False)
    b.seek(0)
    return b

# Export as HTML for PDF-ready download
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

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>{title}</title>
</head>
<body>
{''.join(parts)}
</body>
</html>"""
    b = BytesIO(html_doc.encode("utf-8"))
    b.seek(0)
    return b