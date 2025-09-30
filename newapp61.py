import streamlit as st
import pandas as pd
from config61 import CFG
from utils61 import inject_govuk_css, PRISON_TO_REGION, SUPERVISOR_PAY
from host61 import generate_host_quote, host_summary_table
from production61 import calculate_production_costs, production_summary_table

# -----------------------------------------------------------------------------
# App setup
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Cost and Price Calculator", layout="wide")
inject_govuk_css()

st.markdown(
    """
    <div class="app-header">
        <h1 class="govuk-heading-l">Cost and Price Calculator</h1>
    </div>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Sidebar controls
# -----------------------------------------------------------------------------
with st.sidebar:
    st.subheader("Settings")
    lock_overheads = st.checkbox("Lock overheads to highest instructor", value=False)
    effective_pct = st.slider("Adjust instructor % allocation", 0, 100, 100, step=1)
    output_pct = st.slider("Prisoner labour output %", 0, 100, 100, step=5)

# -----------------------------------------------------------------------------
# Main form
# -----------------------------------------------------------------------------
with st.form("inputs_form"):
    # Prison name first
    prison_name = st.selectbox("Prison Name", ["Select"] + sorted(PRISON_TO_REGION.keys()))
    customer_name = st.text_input("Customer Name")
    contract_type = st.selectbox("Contract type?", ["Select", "Host", "Production"])

    workshop_hours = st.number_input("How many hours per week is the workshop open?", 0.0, 80.0, 37.5, step=0.5)
    num_prisoners = st.number_input("How many prisoners employed?", 0, 200, 0, step=1)
    prisoner_salary = st.number_input("Prisoner salary per week (£)", 0.0, 100.0, 10.0, step=0.5)

    num_supervisors = st.number_input("How many instructors?", 0, 10, 0, step=1)

    supervisor_salaries = []
    if num_supervisors > 0:
        region = PRISON_TO_REGION.get(prison_name, "National")
        band_options = SUPERVISOR_PAY.get(region, [])
        for i in range(num_supervisors):
            choice = st.selectbox(
                f"Instructor {i+1} band",
                [b["title"] for b in band_options],
                key=f"instructor_{i}"
            )
            salary = next((b["avg_total"] for b in band_options if b["title"] == choice), 0)
            supervisor_salaries.append(salary)

    customer_covers_supervisors = st.checkbox("Customer provides instructor(s)?", value=False)

    # Development charge rule (Commercial only)
    dev_rate = 0.0
    support = st.selectbox(
        "Customer employment support?",
        ["None", "Employment on release/RoTL", "Post release", "Both"],
        help="Affects development charge. 'Both' reduces dev charge to 0%."
    )
    if support == "None":
        dev_rate = 0.20
    elif support in ("Employment on release/RoTL", "Post release"):
        dev_rate = 0.10
    elif support == "Both":
        dev_rate = 0.00

    submit = st.form_submit_button("Generate Costs")

# -----------------------------------------------------------------------------
# Run Calculations
# -----------------------------------------------------------------------------
if submit and contract_type != "Select":
    if contract_type == "Host":
        st.header("Host Model Results")
        df, ctx = generate_host_quote(
            workshop_hours=workshop_hours,
            area_m2=100.0,  # placeholder
            usage_key="low",
            num_prisoners=num_prisoners,
            prisoner_salary=prisoner_salary,
            num_supervisors=num_supervisors,
            customer_covers_supervisors=customer_covers_supervisors,
            supervisor_salaries=supervisor_salaries,
            effective_pct=effective_pct,
            customer_type="Commercial",
            apply_vat=True,
            vat_rate=20.0,
            dev_rate=dev_rate,
            lock_overheads=lock_overheads,
        )
        st.dataframe(host_summary_table(df))

    elif contract_type == "Production":
        st.header("Production Model Results")
        items = [
            {"name": "Example Item", "assigned": num_prisoners, "minutes": 30, "units": 100}
        ]
        df = calculate_production_costs(
            items,
            workshop_hours=workshop_hours,
            prisoner_salary=prisoner_salary,
            supervisor_salaries=supervisor_salaries,
            effective_pct=effective_pct,
            customer_covers_supervisors=customer_covers_supervisors,
            customer_type="Commercial",
            output_pct=output_pct,
            lock_overheads=lock_overheads,
            dev_rate=dev_rate,
        )
        st.dataframe(production_summary_table(df))