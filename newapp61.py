# newapp61.py
# Streamlit app for Instructor-based Cost and Price Calculator (no utilities).
from io import BytesIO
from datetime import date
import pandas as pd
import streamlit as st

from config61 import CFG
from style61 import inject_govuk_css
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY, BAND3_SHADOW_COSTS
from sidebar61 import draw_sidebar
from production61 import (
    labour_minutes_budget,
    calculate_production_contractual,
    calculate_adhoc,
)
from host61 import generate_host_quote

# -----------------------------------------------------------------------------
# Page config + CSS
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Cost and Price Calculator", page_icon="💷", layout="centered")
inject_govuk_css()

# -----------------------------------------------------------------------------
# Header
# -----------------------------------------------------------------------------
st.markdown("## Cost and Price Calculator")

# -----------------------------------------------------------------------------
# Helpers: formatting + export
# -----------------------------------------------------------------------------
def _currency(v) -> str:
    try:
        return f"£{float(v):,.2f}"
    except Exception:
        return ""

def render_generic_df_to_html(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    thead = "<tr>" + "".join([f"<th>{c}</th>" for c in cols]) + "</tr>"
    body_rows = []
    for _, row in df.iterrows():
        tds = []
        for col in cols:
            val = row[col]
            if isinstance(val, (int, float)) and pd.notna(val):
                tds.append(f"<td>{_currency(val)}</td>")
            else:
                tds.append(f"<td>{val}</td>")
        body_rows.append("<tr>" + "".join(tds) + "</tr>")
    return f"<table>{thead}{''.join(body_rows)}</table>"

def export_csv_bytes(df: pd.DataFrame) -> BytesIO:
    b = BytesIO()
    df.to_csv(b, index=False)
    b.seek(0)
    return b

def export_html(prod_df: pd.DataFrame | None, title: str = "Quote") -> BytesIO:
    css = """<style>
    body{font-family:Arial,Helvetica,sans-serif;color:#0b0c0c;}
    table{width:100%;border-collapse:collapse;margin:12px 0;}
    th,td{border-bottom:1px solid #b1b4b6;padding:8px;text-align:left;}
    th{background:#f3f2f1;} td.neg{color:#d4351c;}
    tr.grand td{font-weight:700;}
    </style>"""
    header_html = f"<h2>{title}</h2>"
    meta = (f"<p>Date: {date.today().isoformat()}<br/>"
            f"Customer: {st.session_state.get('customer_name','')}<br/>"
            f"Prison: {st.session_state.get('prison_choice','')}<br/>"
            f"Region: {st.session_state.get('region','')}</p>")
    parts = [css, header_html, meta]
    if prod_df is not None:
        parts += [f"<h3>Production Items</h3>", render_generic_df_to_html(prod_df)]
    parts.append("<p>Prices are indicative and may change based on final scope and site conditions.</p>")
    html_doc = f"<!doctype html><html><head><meta charset='utf-8'/><title>{title}</title></head><body>{''.join(parts)}</body></html>"
    b = BytesIO(html_doc.encode("utf-8"))
    b.seek(0)
    return b

# -----------------------------------------------------------------------------
# Base inputs
# -----------------------------------------------------------------------------
prisons_sorted = ["Select"] + sorted(PRISON_TO_REGION.keys())
prison_choice = st.selectbox("Prison Name", prisons_sorted, index=0, key="prison_choice")
region = PRISON_TO_REGION.get(prison_choice, "Select") if prison_choice != "Select" else "Select"
st.session_state["region"] = region

customer_type = st.selectbox("I want to quote for", ["Select", "Commercial", "Another Government Department"], key="customer_type")
customer_name = st.text_input("Customer Name", key="customer_name")
workshop_mode = st.selectbox("Contract type?", ["Select", "Host", "Production"], key="workshop_mode")

# Instructors
workshop_hours = st.number_input("How many hours per week is the workshop open?", min_value=0.0, format="%.2f", key="workshop_hours")
num_prisoners = st.number_input("How many prisoners employed?", min_value=0, step=1, key="num_prisoners")
prisoner_salary = st.number_input("Prisoner salary per week (£)", min_value=0.0, format="%.2f", key="prisoner_salary")
num_supervisors = st.number_input("How many instructors?", min_value=0, step=1, key="num_supervisors")
customer_covers_supervisors = st.checkbox("Customer provides instructor(s)?", key="customer_covers_supervisors")

supervisor_salaries = []
if not customer_covers_supervisors:
    titles_for_region = SUPERVISOR_PAY.get(region, [])
    if region == "Select" or not titles_for_region:
        st.warning("Select a prison to derive the Region before assigning instructor titles.")
    else:
        for i in range(int(num_supervisors)):
            options = [t["title"] for t in titles_for_region]
            sel = st.selectbox(f"Instructor {i+1} title", options, key=f"inst_title_{i}")
            pay = next(t["avg_total"] for t in titles_for_region if t["title"] == sel)
            st.caption(f"Avg Total for {region}: **£{pay:,.0f}** per year")
            supervisor_salaries.append(float(pay))

# Lock overheads toggle
lock_overheads = st.sidebar.checkbox("Lock overheads to highest instructor cost", key="lock_overheads")

# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------
def validate_inputs():
    errors = []
    if prison_choice == "Select":
        errors.append("Select prison")
    if region == "Select":
        errors.append("Region could not be derived from prison selection")
    if customer_type == "Select":
        errors.append("Select customer type")
    if not str(customer_name).strip():
        errors.append("Enter customer name")
    if workshop_mode == "Select":
        errors.append("Select contract type")
    if workshop_mode == "Production" and workshop_hours <= 0:
        errors.append("Hours per week must be > 0 (Production)")
    if prisoner_salary < 0:
        errors.append("Prisoner salary per week cannot be negative")
    if num_prisoners < 0:
        errors.append("Prisoners employed cannot be negative")
    if not customer_covers_supervisors:
        if num_supervisors <= 0:
            errors.append("Enter number of instructors (>0) or tick 'Customer provides instructor(s)'")
        if region == "Select":
            errors.append("Select a prison/region to populate instructor titles")
        if len(supervisor_salaries) != int(num_supervisors):
            errors.append("Choose a title for each instructor")
        if any(s <= 0 for s in supervisor_salaries):
            errors.append("Instructor Avg Total must be > 0")
    return errors

# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
if workshop_mode == "Host":
    host_df, _ = generate_host_quote(
        workshop_hours=float(workshop_hours),
        num_prisoners=int(num_prisoners),
        prisoner_salary=float(prisoner_salary),
        num_supervisors=int(num_supervisors),
        customer_covers_supervisors=bool(customer_covers_supervisors),
        supervisor_salaries=supervisor_salaries,
        lock_overheads=bool(lock_overheads),
        region=region,
        apply_vat=True,
        vat_rate=20.0,
    )
    st.markdown(render_generic_df_to_html(host_df), unsafe_allow_html=True)
    st.download_button("Download CSV (Host)", data=export_csv_bytes(host_df), file_name="host_quote.csv", mime="text/csv")
    st.download_button("Download PDF-ready HTML (Host)", data=export_html(host_df, title="Host Quote"), file_name="host_quote.html", mime="text/html")

elif workshop_mode == "Production":
    errors_top = validate_inputs()
    if errors_top:
        st.error("Fix errors before production:\n- " + "\n- ".join(errors_top))
    else:
        # Run production logic
        results = calculate_production_contractual(
            items=[],  # actual items collected in production61.py
            output_pct=CFG.GLOBAL_OUTPUT_DEFAULT,
            workshop_hours=float(workshop_hours),
            prisoner_salary=float(prisoner_salary),
            supervisor_salaries=supervisor_salaries,
            customer_covers_supervisors=bool(customer_covers_supervisors),
            customer_type=customer_type,
            apply_vat=True,
            vat_rate=20.0,
            num_prisoners=int(num_prisoners),
            num_supervisors=int(num_supervisors),
            lock_overheads=bool(lock_overheads),
            region=region,
        )
        prod_df = pd.DataFrame(results)
        st.markdown(render_generic_df_to_html(prod_df), unsafe_allow_html=True)
        st.download_button("Download CSV (Production)", data=export_csv_bytes(prod_df), file_name="production_quote.csv", mime="text/csv")
        st.download_button("Download PDF-ready HTML (Production)", data=export_html(prod_df, title="Production Quote"), file_name="production_quote.html", mime="text/html")

# Reset
if st.button("Reset Selections", key="reset_app_footer"):
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()