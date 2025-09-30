import streamlit as st
import pandas as pd

from config61 import CFG
from utils61 import inject_govuk_css, PRISON_TO_REGION, SUPERVISOR_PAY
from host61 import generate_host_quote, host_summary_table
from production61 import calculate_production_costs, production_summary_table

# -----------------------------------------------------------------------------
# PAGE CONFIG
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Cost and Price Calculator (Instructor Cost Model)", layout="wide")
inject_govuk_css()

# -----------------------------------------------------------------------------
# FORM INPUTS
# -----------------------------------------------------------------------------
st.markdown('<div class="app-header"><h1 class="govuk-heading-l">Cost and Price Calculator (Instructor Cost Model)</h1></div>', unsafe_allow_html=True)

with st.form("quote_form"):
    st.subheader("Contract details")

    prison_name = st.selectbox("Prison Name", ["Select"] + sorted(PRISON_TO_REGION.keys()))
    customer_name = st.text_input("Customer Name")
    contract_type = st.selectbox("Contract type?", ["Select", "Commercial", "Government Dept", "Other"])

    st.subheader("Workshop & staffing")

    workshop_hours = st.number_input("How many hours per week is the workshop open?", min_value=0.0, step=0.5)
    num_prisoners = st.number_input("How many prisoners employed?", min_value=0, step=1)
    prisoner_salary = st.number_input("Prisoner salary per week (£)", min_value=0.0, step=1.0)
    num_instructors = st.number_input("How many instructors?", min_value=0, step=1)
    customer_covers_supervisors = st.checkbox("Customer provides instructor(s)?")

    # dynamically render instructor selection boxes
    region = PRISON_TO_REGION.get(prison_name, "National")
    supervisor_band = SUPERVISOR_PAY.get(region, [])
    supervisor_salaries = []
    for i in range(int(num_instructors)):
        band = st.selectbox(f"Instructor {i+1} title", [s["title"] for s in supervisor_band], key=f"instr_title_{i}")
        salary = next(s["avg_total"] for s in supervisor_band if s["title"] == band)
        supervisor_salaries.append(salary)

    submitted = st.form_submit_button("Generate Costs")

# -----------------------------------------------------------------------------
# SIDEBAR CONTROLS
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("Adjust assumptions")

    lock_overheads = st.checkbox("Lock overheads to highest instructor", value=False, key="lock_overheads")
    instructor_allocation = st.slider("Adjust instructor % allocation", 0, 100, 100, step=1, key="instructor_allocation")
    prisoner_output_pct = st.slider("Prisoner labour output %", 0, 200, CFG.GLOBAL_OUTPUT_DEFAULT, step=5, key="prisoner_output_pct")

# -----------------------------------------------------------------------------
# RUN CALCULATIONS
# -----------------------------------------------------------------------------
if submitted and prison_name != "Select" and contract_type != "Select":
    if st.session_state.get("mode", "Host") == "Host":
        # HOST MODE
        host_df, ctx = generate_host_quote(
            workshop_hours=workshop_hours,
            num_prisoners=num_prisoners,
            prisoner_salary=prisoner_salary,
            num_supervisors=num_instructors,
            customer_covers_supervisors=customer_covers_supervisors,
            supervisor_salaries=supervisor_salaries,
            effective_pct=instructor_allocation,
            customer_type=contract_type,
            lock_overheads=lock_overheads,
            output_pct=prisoner_output_pct,
        )

        st.subheader("Host Cost Breakdown")
        st.table(host_summary_table(host_df, ctx))

    else:
        # PRODUCTION MODE
        prod_df, ctx = calculate_production_costs(
            workshop_hours=workshop_hours,
            num_prisoners=num_prisoners,
            prisoner_salary=prisoner_salary,
            num_supervisors=num_instructors,
            customer_covers_supervisors=customer_covers_supervisors,
            supervisor_salaries=supervisor_salaries,
            effective_pct=instructor_allocation,
            customer_type=contract_type,
            lock_overheads=lock_overheads,
            output_pct=prisoner_output_pct,
        )

        st.subheader("Production Cost Breakdown")
        st.table(production_summary_table(prod_df, ctx))
else:
    st.info("Fill in the form above and click *Generate Costs* to see results.")