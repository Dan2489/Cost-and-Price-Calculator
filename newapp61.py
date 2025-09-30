from io import BytesIO
from datetime import date
import pandas as pd
import streamlit as st

from config61 import CFG
from utils61 import inject_govuk_css, draw_sidebar
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
from host61 import generate_host_quote
from production61 import labour_minutes_budget, calculate_production_contractual

# -----------------------------------------------------------------------------
# Page config + CSS
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Cost and Price Calculator", page_icon="💷", layout="centered")
inject_govuk_css()

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _currency(v) -> str:
    try:
        return f"£{float(v):,.2f}"
    except Exception:
        return ""

def render_df_to_html(df: pd.DataFrame) -> str:
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

def export_html(df: pd.DataFrame, title: str = "Quote") -> BytesIO:
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
    parts = [css, header_html, meta, render_df_to_html(df)]
    html_doc = f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8" /><title>{title}</title></head>
<body>{''.join(parts)}</body></html>"""
    b = BytesIO(html_doc.encode("utf-8"))
    b.seek(0)
    return b

# -----------------------------------------------------------------------------
# Base inputs
# -----------------------------------------------------------------------------
with st.form("main_form", clear_on_submit=False, border=True):
    prisons_sorted = ["Select"] + sorted(PRISON_TO_REGION.keys())
    prison_choice = st.selectbox("Prison Name", prisons_sorted, index=0, key="prison_choice")
    region = PRISON_TO_REGION.get(prison_choice, "Select") if prison_choice != "Select" else "Select"
    st.session_state["region"] = region

    customer_type = st.selectbox("Customer type", ["Select", "Commercial", "Another Government Department"], key="customer_type")
    customer_name = st.text_input("Customer Name", key="customer_name")
    workshop_mode = st.selectbox("Contract type?", ["Select", "Host", "Production"], key="workshop_mode")

    # Prisoners & instructors
    workshop_hours = st.number_input("Hours per week workshop open", min_value=0.0, format="%.2f", key="workshop_hours")
    num_prisoners = st.number_input("How many prisoners employed?", min_value=0, step=1, key="num_prisoners")
    prisoner_salary = st.number_input("Prisoner salary per week (£)", min_value=0.0, format="%.2f", key="prisoner_salary")
    num_supervisors = st.number_input("How many instructors?", min_value=0, step=1, key="num_supervisors")
    customer_covers_supervisors = st.checkbox("Customer provides instructor(s)?", key="customer_covers_supervisors")

    supervisor_salaries = []
    if not customer_covers_supervisors and region != "Select":
        titles_for_region = SUPERVISOR_PAY.get(region, [])
        for i in range(int(num_supervisors)):
            options = [t["title"] for t in titles_for_region]
            sel = st.selectbox(f"Instructor {i+1} title", options, key=f"inst_title_{i}")
            pay = next(t["avg_total"] for t in titles_for_region if t["title"] == sel)
            st.caption(f"Avg Total for {region}: **£{pay:,.0f}** per year")
            supervisor_salaries.append(float(pay))

    contracts = st.number_input("How many contracts do these instructors oversee?", min_value=1, value=1, key="contracts")

    # Development charge (Commercial only)
    dev_rate = 0.0
    if customer_type == "Commercial":
        support = st.selectbox(
            "Customer employment support?",
            ["None", "Employment on release/RoTL", "Post release", "Both"],
            help="Affects development charge on overheads"
        )
        if support == "None":
            dev_rate = 0.20
        elif support in ("Employment on release/RoTL", "Post release"):
            dev_rate = 0.10
        else:
            dev_rate = 0.00

    submitted = st.form_submit_button("Continue")

# Sidebar controls
draw_sidebar(CFG.GLOBAL_OUTPUT_DEFAULT)
effective_pct = int(st.session_state.get("chosen_pct", 100))
lock_overheads = st.session_state.get("lock_overheads", False)
planned_output_pct = st.session_state.get("planned_output_pct", CFG.GLOBAL_OUTPUT_DEFAULT)

# -----------------------------------------------------------------------------
# HOST
# -----------------------------------------------------------------------------
if submitted and workshop_mode == "Host":
    host_df, _ctx = generate_host_quote(
        num_prisoners=int(num_prisoners),
        prisoner_salary=float(prisoner_salary),
        num_supervisors=int(num_supervisors),
        customer_covers_supervisors=bool(customer_covers_supervisors),
        supervisor_salaries=supervisor_salaries,
        effective_pct=float(effective_pct),
        region=region,
        customer_type=customer_type,
        vat_rate=20.0,
        dev_rate=float(dev_rate),
        lock_overheads=bool(lock_overheads),
    )
    st.markdown(render_df_to_html(host_df), unsafe_allow_html=True)
    st.download_button("Download CSV", data=export_csv_bytes(host_df), file_name="host_quote.csv", mime="text/csv")
    st.download_button("Download HTML", data=export_html(host_df, "Host Quote"), file_name="host_quote.html", mime="text/html")

# -----------------------------------------------------------------------------
# PRODUCTION
# -----------------------------------------------------------------------------
if submitted and workshop_mode == "Production":
    # Planned minutes
    budget_minutes_raw = labour_minutes_budget(int(num_prisoners), float(workshop_hours))
    budget_minutes_planned = budget_minutes_raw * (planned_output_pct / 100.0)
    st.markdown(f"**Planned available Labour minutes @ {planned_output_pct}%:** {budget_minutes_planned:,.0f}")

    num_items = st.number_input("Number of items produced?", min_value=1, value=1, step=1, key="num_items_prod")
    items, targets = [], []
    for i in range(int(num_items)):
        with st.expander(f"Item {i+1} details", expanded=(i == 0)):
            name = st.text_input(f"Item {i+1} Name", key=f"name_{i}")
            disp = (name.strip() or f"Item {i+1}") if isinstance(name, str) else f"Item {i+1}"
            required = st.number_input(f"Prisoners required to make 1 item ({disp})", min_value=1, value=1, step=1, key=f"req_{i}")
            minutes_per = st.number_input(f"Minutes to make 1 item ({disp})", min_value=1.0, value=10.0, format="%.2f", key=f"mins_{i}")
            assigned = st.number_input(f"How many prisoners work solely on this item ({disp})", min_value=0, max_value=int(num_prisoners), step=1, key=f"assigned_{i}")
            items.append({"name": name, "required": int(required), "minutes": float(minutes_per), "assigned": int(assigned)})

    results = calculate_production_contractual(
        items,
        planned_output_pct,
        workshop_hours=float(workshop_hours),
        prisoner_salary=float(prisoner_salary),
        supervisor_salaries=supervisor_salaries,
        effective_pct=float(effective_pct),
        customer_covers_supervisors=bool(customer_covers_supervisors),
        region=region,
        customer_type=customer_type,
        apply_vat=True,
        vat_rate=20.0,
        num_prisoners=int(num_prisoners),
        num_supervisors=int(num_supervisors),
        dev_rate=float(dev_rate),
        pricing_mode="as-is",
        lock_overheads=bool(lock_overheads),
    )
    prod_df = pd.DataFrame(results)
    st.markdown(render_df_to_html(prod_df), unsafe_allow_html=True)
    st.download_button("Download CSV", data=export_csv_bytes(prod_df), file_name="production_quote.csv", mime="text/csv")
    st.download_button("Download HTML", data=export_html(prod_df, "Production Quote"), file_name="production_quote.html", mime="text/html")