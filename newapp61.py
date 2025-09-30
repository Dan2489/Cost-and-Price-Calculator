# newapp61.py
import streamlit as st
import pandas as pd
from config61 import CFG
from utils61 import inject_govuk_css, draw_sidebar, fmt_currency
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
from host61 import generate_host_quote
from production61 import calculate_production_contractual, calculate_adhoc
from datetime import date

# ----- UI Setup -----
st.set_page_config(page_title="Cost and Price Calculator", layout="wide")
inject_govuk_css()
draw_sidebar(default_output_pct=CFG.GLOBAL_OUTPUT_DEFAULT)

st.title("Cost and Price Calculator")

# ----- Form -----
with st.form("main_form"):
    # Prison name
    prison_name = st.selectbox("Prison name", [""] + sorted(PRISON_TO_REGION.keys()))
    region = PRISON_TO_REGION.get(prison_name, None)

    # Customer name
    customer_name = st.text_input("Customer name")

    # Contract type
    contract_type = st.radio("Contract type", ["", "Host", "Production"], index=0)

    # Common questions
    workshop_hours = st.number_input("How many hours is the workshop open per week?", min_value=0.0, value=0.0)
    num_prisoners = st.number_input("How many prisoners employed per week?", min_value=0, value=0)
    prisoner_salary = st.number_input("Average prisoner salary per week (£)", min_value=0.0, value=0.0)

    num_supervisors = st.number_input("How many instructors?", min_value=0, value=0, step=1)

    supervisor_salaries = []
    if num_supervisors > 0 and region:
        for i in range(num_supervisors):
            titles = [x["title"] for x in SUPERVISOR_PAY[region]]
            sel_title = st.selectbox(f"Instructor {i+1} title", [""] + titles, key=f"inst_{i}")
            if sel_title:
                sel_salary = next(x["avg_total"] for x in SUPERVISOR_PAY[region] if x["title"] == sel_title)
                st.caption(f"Region: {region} — Salary: £{sel_salary:,.2f}")
                supervisor_salaries.append(sel_salary)

    num_contracts = st.number_input("How many contracts do they oversee in this workshop?", min_value=1, value=1)

    customer_support = st.multiselect(
        "What employment support does the customer offer?",
        ["Employment on release / ROTL", "Post release"],
    )

    submitted = st.form_submit_button("Generate costs")

# ----- Logic -----
if submitted and region and contract_type:
    effective_pct = st.session_state.get("effective_pct", 100)
    output_pct = st.session_state.get("output_pct", CFG.GLOBAL_OUTPUT_DEFAULT)
    lock_overheads = st.session_state.get("lock_overheads", False)

    # Development charge %
    dev_rate = 0.20
    if "Employment on release / ROTL" in customer_support:
        dev_rate -= 0.10
    if "Post release" in customer_support:
        dev_rate -= 0.10
    dev_rate = max(dev_rate, 0.0)

    if contract_type == "Host":
        host_df, ctx = generate_host_quote(
            num_prisoners=num_prisoners,
            prisoner_salary=prisoner_salary,
            num_supervisors=num_supervisors,
            customer_covers_supervisors=(num_supervisors == 0),
            supervisor_salaries=supervisor_salaries,
            effective_pct=effective_pct,
            region=region,
            customer_type="Commercial" if customer_name else "Government",
            dev_rate=dev_rate,
        )

        st.subheader("Host Monthly Costs")
        st.table(host_df.style.format({"Amount (£)": fmt_currency}))

        if "Development charge (applied)" in host_df["Item"].values:
            base = ctx["overheads_monthly"] * 0.20
            reductions = base - ctx["dev_charge"]
            if reductions > 0:
                st.markdown(f"<span style='color:red'>Reductions applied: {fmt_currency(reductions)}</span>", unsafe_allow_html=True)
                st.markdown(f"**Revised Development charge: {fmt_currency(ctx['dev_charge'])}**")

    elif contract_type == "Production":
        mode = st.radio("Production type", ["", "Contractual", "Ad-hoc"], index=0)
        if mode == "Contractual":
            pricing_mode = st.radio("Would you like a price for:", ["Maximum output", "Targeted output"])
            items = []
            num_items = st.number_input("How many different products?", min_value=1, value=1, step=1)
            for i in range(num_items):
                name = st.text_input(f"Item {i+1} name", "")
                minutes = st.number_input(f"Minutes per unit (Item {i+1})", min_value=0.0, value=0.0)
                required = st.number_input(f"Prisoners required per unit (Item {i+1})", min_value=1, value=1)
                assigned = st.number_input(f"Prisoners assigned to Item {i+1}", min_value=0, value=0)
                items.append({"name": name, "minutes": minutes, "required": required, "assigned": assigned})

            targets = None
            if pricing_mode == "Targeted output":
                targets = []
                for i in range(num_items):
                    tgt = st.number_input(f"Target units per week for Item {i+1}", min_value=0, value=0)
                    targets.append(tgt)

            if st.form_submit_button("Generate production costs"):
                results = calculate_production_contractual(
                    items,
                    output_pct,
                    workshop_hours=workshop_hours,
                    prisoner_salary=prisoner_salary,
                    supervisor_salaries=supervisor_salaries,
                    effective_pct=effective_pct,
                    customer_covers_supervisors=(num_supervisors == 0),
                    region=region,
                    customer_type="Commercial" if customer_name else "Government",
                    dev_rate=dev_rate,
                    pricing_mode="target" if pricing_mode == "Targeted output" else "as-is",
                    targets=targets,
                    lock_overheads=lock_overheads,
                )
                st.subheader("Production Contractual Costs")
                st.dataframe(pd.DataFrame(results).style.format(fmt_currency, subset=[c for c in pd.DataFrame(results).columns if "£" in c]))

        elif mode == "Ad-hoc":
            lines = []
            num_lines = st.number_input("How many ad-hoc jobs?", min_value=1, value=1, step=1)
            for i in range(num_lines):
                name = st.text_input(f"Job {i+1} name", "")
                mins_per_item = st.number_input(f"Minutes per unit (Job {i+1})", min_value=0.0, value=0.0)
                pris_per_item = st.number_input(f"Prisoners per unit (Job {i+1})", min_value=1, value=1)
                units = st.number_input(f"Units required (Job {i+1})", min_value=0, value=0)
                deadline = st.date_input(f"Deadline (Job {i+1})", value=date.today())
                lines.append({"name": name, "mins_per_item": mins_per_item, "pris_per_item": pris_per_item, "units": units, "deadline": deadline})

            if st.form_submit_button("Generate ad-hoc costs"):
                results = calculate_adhoc(
                    lines,
                    output_pct,
                    workshop_hours=workshop_hours,
                    num_prisoners=num_prisoners,
                    prisoner_salary=prisoner_salary,
                    supervisor_salaries=supervisor_salaries,
                    effective_pct=effective_pct,
                    customer_covers_supervisors=(num_supervisors == 0),
                    region=region,
                    customer_type="Commercial" if customer_name else "Government",
                    dev_rate=dev_rate,
                    today=date.today(),
                    lock_overheads=lock_overheads,
                )
                st.subheader("Production Ad-hoc Costs")
                st.json(results)