import streamlit as st
import pandas as pd
from datetime import date

# --- GOV.UK styling ---
def inject_govuk_css() -> None:
    st.markdown(
        """
        <style>
          [data-testid="stSidebar"] { min-width: 420px !important; max-width: 420px !important; }
          @media (max-width: 1200px) {
            [data-testid="stSidebar"] { min-width: 360px !important; max-width: 360px !important; }
          }
          :root { --govuk-green: #00703c; --govuk-yellow: #ffdd00; }
          .stButton > button {
            background: var(--govuk-green) !important; color: #fff !important;
            border: 2px solid transparent !important; border-radius: 0 !important; font-weight: 600;
          }
          .stButton > button:hover { filter: brightness(0.95); }
          .stButton > button:focus, .stButton > button:focus-visible {
            outline: 3px solid var(--govuk-yellow) !important; outline-offset: 0 !important;
            box-shadow: 0 0 0 1px #000 inset !important;
          }
          [data-testid="stSlider"] [role="slider"] {
            background: var(--govuk-green) !important; border: 2px solid var(--govuk-green) !important; box-shadow: none !important;
          }
          [data-testid="stSlider"] [role="slider"]:focus,
          [data-testid="stSlider"] [role="slider"]:focus-visible {
            outline: 3px solid var(--govuk-yellow) !important; outline-offset: 0 !important;
            box-shadow: 0 0 0 1px #000 inset !important;
          }
          [data-testid="stSlider"] div[aria-hidden="true"] > div > div { background-color: var(--govuk-green) !important; }
          .govuk-heading-l { font-weight: 700; font-size: 1.75rem; line-height: 1.2; }
          .app-header { display:flex; align-items:center; gap:12px; margin: 0.25rem 0 0.75rem 0; }
          table { width:100%; border-collapse: collapse; margin: 12px 0; }
          th, td { border-bottom: 1px solid #b1b4b6; padding: 8px; text-align: left; }
          th { background: #f3f2f1; }
          td.neg { color: #d4351c; }
          tr.grand td { font-weight: 700; }
        </style>
        """,
        unsafe_allow_html=True
    )

# --- Prison mapping + pay bands ---
PRISON_TO_REGION = {
    "Altcourse": "National", "Ashfield": "National", "Askham Grange": "National",
    "Aylesbury": "National", "Bedford": "National", "Belmarsh": "Inner London",
    "Brixton": "Inner London", "Bronzefield": "Outer London", "Coldingley": "Outer London",
    "Downview": "Outer London", "Feltham A": "Outer London", "Feltham B": "Outer London",
    "High Down": "Outer London", "Isis": "Inner London", "Pentonville": "Inner London",
    "Thameside": "Inner London", "Wandsworth": "Inner London", "Woodhill": "Inner London",
    "Wormwood Scrubs": "Inner London",
    # everything else defaults to National
}
SUPERVISOR_PAY = {
    "Inner London": [
        {"title": "Production Instructor: Band 3", "avg_total": 49203},
        {"title": "Specialist Instructor: Band 4", "avg_total": 55632},
    ],
    "Outer London": [
        {"title": "Production Instructor: Band 3", "avg_total": 45856},
        {"title": "Prison Officer Specialist - Instructor: Band 4", "avg_total": 69584},
    ],
    "National": [
        {"title": "Production Instructor: Band 3", "avg_total": 42248},
        {"title": "Prison Officer Specialist - Instructor: Band 4", "avg_total": 48969},
    ],
}

# --- Sidebar ---
def draw_sidebar() -> None:
    with st.sidebar:
        st.header("Settings")
        st.caption("Adjust overheads and instructor allocation here.")

# --- Currency formatting ---
def currency(v) -> str:
    try:
        return f"£{float(v):,.2f}"
    except Exception:
        return ""

# --- Render helpers ---
def render_host_df_to_html(host_df: pd.DataFrame) -> str:
    rows_html = []
    for _, row in host_df.iterrows():
        item = str(row["Item"])
        val = row["Amount (£)"]
        neg_cls = ""
        try:
            neg_cls = " class='neg'" if float(val) < 0 else ""
        except Exception:
            pass
        grand_cls = " class='grand'" if "Grand Total" in item else ""
        rows_html.append(f"<tr{grand_cls}><td>{item}</td><td{neg_cls}>{currency(val)}</td></tr>")
    header = "<tr><th>Item</th><th>Amount (£)</th></tr>"
    return f"<table>{header}{''.join(rows_html)}</table>"

def render_generic_df_to_html(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    thead = "<tr>" + "".join([f"<th>{c}</th>" for c in cols]) + "</tr>"
    body_rows = []
    for _, row in df.iterrows():
        tds = []
        for col in cols:
            val = row[col]
            if isinstance(val, (int, float)) and pd.notna(val):
                tds.append(f"<td>{currency(val) if '£' in col else f'{float(val):,.2f}'}</td>")
            else:
                tds.append(f"<td>{val}</td>")
        body_rows.append("<tr>" + "".join(tds) + "</tr>")
    return f"<table>{thead}{''.join(body_rows)}</table>"

# --- Export helpers ---
from io import BytesIO
def export_csv_bytes(df: pd.DataFrame) -> BytesIO:
    b = BytesIO()
    df.to_csv(b, index=False)
    b.seek(0)
    return b

def export_html(host_df: pd.DataFrame | None,
                prod_df: pd.DataFrame | None,
                title: str = "Quote") -> BytesIO:
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
    meta = (f"<p>Date: {date.today().isoformat()}<br/>"
            f"Customer: {st.session_state.get('customer_name','')}<br/>"
            f"Prison: {st.session_state.get('prison_choice','')}<br/>"
            f"Region: {st.session_state.get('region','')}</p>")
    parts = [css, header_html, meta]
    if host_df is not None:
        parts += ["<h3>Host Costs</h3>", render_host_df_to_html(host_df)]
    if prod_df is not None:
        section_title = "Production Items"
        parts += [f"<h3>{section_title}</h3>", render_generic_df_to_html(prod_df)]
    parts.append("<p>Prices are indicative and may change based on final scope and site conditions.</p>")
    html_doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8" /><title>{title}</title></head><body>{''.join(parts)}</body></html>"""
    b = BytesIO(html_doc.encode("utf-8"))
    b.seek(0)
    return b

# --- Validation ---
def validate_inputs(prison_choice, region, customer_type, customer_name, workshop_mode,
                    workshop_hours, prisoner_salary, num_prisoners,
                    num_supervisors, customer_covers_supervisors, supervisor_salaries):
    errors = []
    if prison_choice == "Select": errors.append("Select prison")
    if region == "Select": errors.append("Region could not be derived from prison selection")
    if customer_type == "Select": errors.append("Select customer type")
    if not str(customer_name).strip(): errors.append("Enter customer name")
    if workshop_mode == "Select": errors.append("Select contract type")
    if workshop_mode == "Production" and workshop_hours <= 0: errors.append("Hours per week must be > 0 (Production)")
    if prisoner_salary < 0: errors.append("Prisoner salary per week cannot be negative")
    if num_prisoners < 0: errors.append("Prisoners employed cannot be negative")
    if not customer_covers_supervisors:
        if num_supervisors <= 0: errors.append("Enter number of instructors (>0) or tick 'Customer provides instructor(s)'")
        if region == "Select": errors.append("Select a prison/region to populate instructor titles")
        if len(supervisor_salaries) != int(num_supervisors): errors.append("Choose a title for each instructor")
        if any(s <= 0 for s in supervisor_salaries): errors.append("Instructor Avg Total must be > 0")
    return errors