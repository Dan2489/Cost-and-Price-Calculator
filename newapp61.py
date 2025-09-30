import sys, os
sys.path.append(os.path.dirname(__file__))
import streamlit as st
import pandas as pd
import datetime as dt

import config61
CFG = config61.CFG
from utils61 import inject_govuk_css, fmt_currency, render_sidebar
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
from host61 import generate_host_quote
from production61 import labour_minutes_budget, calculate_production_contractual, calculate_adhoc

st.set_page_config(page_title="Cost and Price Calculator", layout="centered")
inject_govuk_css()
st.markdown("<h1 class='govuk-heading-l'>Cost and Price Calculator</h1>", unsafe_allow_html=True)

# ----- Sidebar (only these 3 controls) -----
render_sidebar()
lock_overheads = bool(st.session_state.get("lock_overheads", False))
effective_pct  = float(st.session_state.get("effective_pct", 100))
output_pct     = int(st.session_state.get("output_pct", CFG.GLOBAL_OUTPUT_DEFAULT))

# ----- Main form -----
with st.form("main_form"):
    prison_name = st.selectbox("Prison Name", [""] + sorted(PRISON_TO_REGION.keys()))
    region = PRISON_TO_REGION.get(prison_name) if prison_name else None

    customer_type = st.selectbox("I want to quote for", ["", "Commercial", "Another Government Department"])
    customer_name = st.text_input("Customer Name", "")

    contract_type = st.selectbox("Contract type?", ["", "Host", "Production"])

    workshop_hours = st.number_input("How many hours per week is the workshop open?", min_value=0.0, step=0.5, format="%.2f")
    num_prisoners  = st.number_input("How many prisoners employed per week?", min_value=0, step=1)
    prisoner_salary = st.number_input("Average prisoner salary per week (£)", min_value=0.0, step=1.0, format="%.2f")

    num_instructors = st.number_input("How many instructors?", min_value=0, step=1)
    titles = SUPERVISOR_PAY.get(region, []) if region else []
    supervisor_salaries = []
    if num_instructors and region:
        for i in range(int(num_instructors)):
            sel = st.selectbox(f"Instructor {i+1} title", [""] + [t["title"] for t in titles], key=f"inst_title_{i}")
            if sel:
                pay = next(t["avg_total"] for t in titles if t["title"] == sel)
                st.caption(f"Region: {region} — Salary: £{pay:,.2f}")
                supervisor_salaries.append(float(pay))

    contracts_overseen = st.number_input("How many contracts do they oversee in this workshop?", min_value=1, value=1, step=1)

    support = st.selectbox(
        "Customer employment support?",
        ["", "None", "Employment on release/ROTL", "Post release", "Both"]
    )

    prod_mode = None
    pricing_basis = None
    items = []
    targets = None
    adhoc_lines = []
    if contract_type == "Production":
        prod_mode = st.radio("Contractual or Ad-hoc?", ["Contractual", "Ad-hoc"], index=0)
        if prod_mode == "Contractual":
            pricing_basis = st.radio("Price based on:", ["Maximum units from capacity", "Target units per week"], index=0)
            num_items = st.number_input("Number of items produced?", min_value=1, value=1, step=1)
            for i in range(int(num_items)):
                with st.expander(f"Item {i+1} details", expanded=(i == 0)):
                    name = st.text_input("Item name", key=f"name_{i}")
                    required = st.number_input("Prisoners required to make 1 item", min_value=1, value=1, step=1, key=f"req_{i}")
                    minutes_per = st.number_input("Minutes to make 1 item", min_value=1.0, value=10.0, format="%.2f", key=f"mins_{i}")
                    assigned = st.number_input("Prisoners assigned solely to this item", min_value=0, value=0, step=1, key=f"assigned_{i}")
                    items.append({"name": name, "required": int(required), "minutes": float(minutes_per), "assigned": int(assigned)})
            if pricing_basis == "Target units per week":
                targets = []
                for i in range(int(num_items)):
                    tgt = st.number_input(f"Target units/week for Item {i+1}", min_value=0, value=0, step=1, key=f"target_{i}")
                    targets.append(tgt)
        else:
            num_lines = st.number_input("How many product lines?", min_value=1, value=1, step=1, key="adhoc_num")
            for i in range(int(num_lines)):
                with st.expander(f"Product line {i+1}", expanded=(i == 0)):
                    name = st.text_input("Item name", key=f"adhoc_name_{i}")
                    units_requested = st.number_input("Units requested", min_value=1, value=100, step=1, key=f"adhoc_units_{i}")
                    pris_per_item = st.number_input("Prisoners to make one", min_value=1, value=1, step=1, key=f"adhoc_pris_{i}")
                    minutes_per_item = st.number_input("Minutes to make one", min_value=1.0, value=10.0, format="%.2f", key=f"adhoc_mins_{i}")
                    deadline = st.date_input("Deadline", value=dt.date.today(), key=f"adhoc_deadline_{i}")
                    adhoc_lines.append({"name": (name or f"Item {i+1}"), "units": int(units_requested),
                                        "deadline": deadline, "pris_per_item": int(pris_per_item),
                                        "mins_per_item": float(minutes_per_item)})

    submitted = st.form_submit_button("Generate Costs")

def _dev_rate(base: float, support_choice: str, cust_type: str) -> float:
    if cust_type == "Another Government Department": return 0.0
    rate = base
    if support_choice == "Employment on release/ROTL": rate -= 0.10
    elif support_choice == "Post release": rate -= 0.10
    elif support_choice == "Both": rate -= 0.20
    return max(rate, 0.0)

if submitted:
    errs = []
    if not prison_name: errs.append("Select prison")
    if not region: errs.append("Region not derived from prison")
    if not customer_type: errs.append("Select customer type")
    if not contract_type: errs.append("Select contract type")
    if errs:
        st.error("Fix errors:\n- " + "\n- ".join(errs))
    else:
        dev_rate = _dev_rate(CFG.DEV_RATE_BASE, support, customer_type)

        if contract_type == "Host":
            host_df, ctx = generate_host_quote(
                num_prisoners=int(num_prisoners),
                prisoner_salary=float(prisoner_salary),
                num_supervisors=int(num_instructors),
                customer_covers_supervisors=(int(num_instructors) == 0),
                supervisor_salaries=supervisor_salaries,
                effective_pct=float(effective_pct),
                region=region,
                customer_type=customer_type,
                dev_rate=float(dev_rate),
                contracts_overseen=int(contracts_overseen),
                lock_overheads=bool(lock_overheads),
            )
            st.subheader("Host Monthly Costs")
            st.table(host_df.style.format({"Amount (£)": fmt_currency}))

            if customer_type == "Commercial":
                base_dev = ctx["overheads_monthly"] * 0.20
                reduction = base_dev - ctx["dev_charge"]
                if reduction > 1e-9:
                    st.markdown(f"<span style='color:#d4351c'>Development charge reductions: {fmt_currency(reduction)}</span>", unsafe_allow_html=True)
                    st.markdown(f"**Revised development charge:** {fmt_currency(ctx['dev_charge'])}")

        else:
            if prod_mode == "Contractual":
                results = calculate_production_contractual(
                    items,
                    output_pct=int(output_pct),
                    workshop_hours=float(workshop_hours),
                    prisoner_salary=float(prisoner_salary),
                    supervisor_salaries=supervisor_salaries,
                    effective_pct=float(effective_pct),
                    customer_covers_supervisors=(int(num_instructors) == 0),
                    region=region,
                    customer_type=customer_type,
                    dev_rate=float(dev_rate),
                    pricing_mode=("target" if pricing_basis == "Target units per week" else "as-is"),
                    targets=targets,
                    lock_overheads=bool(lock_overheads),
                    num_prisoners=int(num_prisoners),
                    contracts_overseen=int(contracts_overseen),
                )
                df = pd.DataFrame(results)
                money_cols = [c for c in df.columns if "£" in c]
                st.subheader("Production (Contractual)")
                st.table(df.style.format({c: fmt_currency for c in money_cols}))
                if "Monthly Total ex VAT (£)" in df:
                    st.markdown(f"**Total monthly (ex VAT):** {fmt_currency(df['Monthly Total ex VAT (£)'].sum())}")
                if "Monthly Total inc VAT (£)" in df:
                    st.markdown(f"**Total monthly (inc VAT):** {fmt_currency(df['Monthly Total inc VAT (£)'].sum())}")

            else:
                result = calculate_adhoc(
                    adhoc_lines,
                    output_pct=int(output_pct),
                    workshop_hours=float(workshop_hours),
                    num_prisoners=int(num_prisoners),
                    prisoner_salary=float(prisoner_salary),
                    supervisor_salaries=supervisor_salaries,
                    effective_pct=float(effective_pct),
                    customer_covers_supervisors=(int(num_instructors) == 0),
                    region=region,
                    customer_type=customer_type,
                    dev_rate=float(dev_rate),
                    today=dt.date.today(),
                    lock_overheads=bool(lock_overheads),
                    contracts_overseen=int(contracts_overseen),
                )
                per = result["per_line"]
                df = pd.DataFrame([{
                    "Item": r["name"],
                    "Units": r["units"],
                    "Unit Cost (ex VAT £)": r["unit_cost_ex_vat"],
                    "Unit Cost (inc VAT £)": r["unit_cost_inc_vat"],
                    "Line Total (ex VAT £)": r["line_total_ex_vat"],
                    "Line Total (inc VAT £)": r["line_total_inc_vat"],
                } for r in per])
                money_cols = [c for c in df.columns if "£" in c]
                st.subheader("Production (Ad-hoc)")
                st.table(df.style.format({c: fmt_currency for c in money_cols}))
                st.markdown(f"**Total Job Cost (ex VAT):** {fmt_currency(result['totals']['ex_vat'])}")
                st.markdown(f"**Total Job Cost (inc VAT):** {fmt_currency(result['totals']['inc_vat'])}")