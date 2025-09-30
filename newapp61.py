# newapp61.py
import sys, os
sys.path.append(os.path.dirname(__file__))

import streamlit as st
import pandas as pd

from config61 import CFG
from utils61 import inject_govuk_css, fmt_currency, sidebar_controls
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
from host61 import generate_host_quote
from production61 import labour_minutes_budget, calculate_production_contractual

# -----------------------------------------------------------------------------
# Page setup + CSS
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Cost and Price Calculator", layout="centered")
inject_govuk_css()
st.markdown("<h1 class='govuk-heading-l'>Cost and Price Calculator</h1>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Sidebar (exactly 3 controls)
# -----------------------------------------------------------------------------
lock_overheads, instructor_pct, prisoner_output = sidebar_controls(CFG.global_output_default)

# -----------------------------------------------------------------------------
# Main inputs (no form, dynamic like original)
# -----------------------------------------------------------------------------
prisons_sorted = [""] + sorted(PRISON_TO_REGION.keys())
prison_name = st.selectbox("Prison Name", prisons_sorted, index=0)
region = PRISON_TO_REGION.get(prison_name) if prison_name else None

customer_type = st.selectbox("I want to quote for", ["", "Commercial", "Another Government Department"], index=0)
customer_name = st.text_input("Customer Name", "")

contract_type = st.selectbox("Contract Type", ["", "Host", "Production"], index=0)

workshop_hours = st.number_input("How many hours is the workshop open per week?", min_value=0.0, step=0.5, format="%.2f")
num_prisoners = st.number_input("How many prisoners employed per week?", min_value=0, step=1)
prisoner_salary = st.number_input("Average prisoner salary per week (£)", min_value=0.0, step=1.0, format="%.2f")

num_instructors = st.number_input("How many instructors?", min_value=0, step=1)

# Instructor titles (dynamic; show as soon as num_instructors set)
supervisor_salaries = []
if prison_name and region and num_instructors > 0:
    titles_for_region = SUPERVISOR_PAY.get(region, [])
    if not titles_for_region:
        st.warning("Select a prison to derive the Region before assigning instructor titles.")
    else:
        for i in range(int(num_instructors)):
            sel = st.selectbox(f"Instructor {i+1} title", [""] + [t["title"] for t in titles_for_region], key=f"inst_title_{i}")
            if sel:
                pay = next(t["avg_total"] for t in titles_for_region if t["title"] == sel)
                st.caption(f"Region: {region} — Salary: £{pay:,.2f}")
                supervisor_salaries.append(float(pay))

contracts_overseen = st.number_input("How many contracts do they oversee in this workshop?", min_value=1, value=1, step=1)

support = st.selectbox(
    "What employment support does the customer offer?",
    ["", "None", "Employment on release/ROTL", "Post release", "Both"],
    index=0
)

# Production options
prod_mode = None
pricing_mode = None
items, targets = [], None
if contract_type == "Production":
    prod_mode = st.radio("Production Type", ["Contractual", "Ad-hoc"], index=0)
    if prod_mode == "Contractual":
        pricing_mode = st.radio("Would you like a price for:", ["Maximum output", "Targeted output"], index=0)
        num_items = st.number_input("Number of items produced?", min_value=1, value=1, step=1)
        for i in range(int(num_items)):
            with st.expander(f"Item {i+1} details", expanded=(i == 0)):
                name = st.text_input(f"Item {i+1} Name", key=f"name_{i}")
                required = st.number_input("Prisoners required to make 1 item", min_value=1, value=1, step=1, key=f"req_{i}")
                minutes_per = st.number_input("Minutes to make 1 item", min_value=1.0, value=10.0, format="%.2f", key=f"mins_{i}")
                assigned = st.number_input("Prisoners assigned solely to this item", min_value=0, value=0, step=1, key=f"assigned_{i}")
                items.append({"name": name, "required": int(required), "minutes": float(minutes_per), "assigned": int(assigned)})
        if pricing_mode == "Targeted output":
            targets = []
            for i in range(int(num_items)):
                tgt = st.number_input(f"Target units/week for Item {i+1}", min_value=0, value=0, step=1, key=f"tgt_{i}")
                targets.append(int(tgt))

# Generate button (keeps UI dynamic like original)
if st.button("Generate Costs"):
    # Dev charge rate after reductions
    def _dev_rate(base: float, support_choice: str, cust_type: str) -> float:
        if cust_type == "Another Government Department":
            return 0.0
        rate = base
        if support_choice == "Employment on release/ROTL": rate -= 0.10
        elif support_choice == "Post release": rate -= 0.10
        elif support_choice == "Both": rate -= 0.20
        return max(rate, 0.0)

    dev_rate = _dev_rate(CFG.development_charge, support, customer_type)

    # Validation
    errs = []
    if not prison_name: errs.append("Select prison")
    if not region: errs.append("Region not derived from prison")
    if not customer_type: errs.append("Select customer type")
    if not contract_type: errs.append("Select contract type")
    if contract_type == "Production" and workshop_hours <= 0: errs.append("Hours per week must be > 0 (Production)")
    if errs:
        st.error("Fix errors:\n- " + "\n- ".join(errs))
    else:
        if contract_type == "Host":
            host_df, ctx = generate_host_quote(
                num_prisoners=int(num_prisoners),
                prisoner_salary=float(prisoner_salary),
                num_supervisors=int(num_instructors),
                customer_covers_supervisors=(int(num_instructors) == 0),
                supervisor_salaries=supervisor_salaries,
                effective_pct=float(instructor_pct),
                region=region,
                customer_type=customer_type,
                dev_rate=float(dev_rate),
                contracts_overseen=int(contracts_overseen),
                lock_overheads=bool(lock_overheads),
            )
            st.subheader("Host Monthly Costs")
            st.table(host_df.style.format({"Amount (£)": fmt_currency}))

        elif contract_type == "Production":
            if prod_mode == "Contractual":
                results = calculate_production_contractual(
                    items, output_pct=int(prisoner_output),
                    workshop_hours=float(workshop_hours),
                    prisoner_salary=float(prisoner_salary),
                    supervisor_salaries=supervisor_salaries,
                    effective_pct=float(instructor_pct),
                    customer_covers_supervisors=(int(num_instructors) == 0),
                    region=region,
                    customer_type=customer_type,
                    dev_rate=float(dev_rate),
                    pricing_mode=("target" if pricing_mode == "Targeted output" else "as-is"),
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
                    st.markdown(f"**Total monthly (ex VAT): {fmt_currency(df['Monthly Total ex VAT (£)'].sum())}**")
                if "Monthly Total inc VAT (£)" in df:
                    st.markdown(f"**Total monthly (inc VAT): {fmt_currency(df['Monthly Total inc VAT (£)'].sum())}**")
            else:
                st.info("Ad-hoc calculation hook is ready; add if needed.")