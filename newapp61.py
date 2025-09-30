import streamlit as st
import pandas as pd
from datetime import date

from config61 import CFG
from host61 import generate_host_quote
from production61 import (
    labour_minutes_budget,
    calculate_production_contractual,
    calculate_adhoc,
)
from utils61 import (
    inject_govuk_css,
    PRISON_TO_REGION,
    SUPERVISOR_PAY,
    draw_sidebar_controls,   # ✅ fixed import
)

# ----------------- Page setup -----------------
st.set_page_config(page_title="Cost and Price Calculator", layout="wide")
inject_govuk_css()

# ----------------- Sidebar controls -----------------
draw_sidebar_controls()   # ✅ fixed call

# ----------------- Main UI -----------------
st.markdown(
    """
    <div class="app-header">
      <img class="app-logo" src="https://upload.wikimedia.org/wikipedia/commons/5/5e/UK_Government_logo.png">
      <span class="govuk-heading-l">Cost and Price Calculator</span>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.form("main_form", clear_on_submit=False):
    st.header("Quote Details")

    customer_name = st.text_input("Customer Name")
    prison_name = st.selectbox("Prison Name", ["Select"] + list(PRISON_TO_REGION.keys()))
    contract_type = st.selectbox("Contract type?", ["Select", "Production", "Ad-hoc", "Host"])

    workshop_hours = st.number_input("How many hours per week is the workshop open?", min_value=0.0, step=0.5)
    num_prisoners = st.number_input("How many prisoners employed?", min_value=0, step=1)
    prisoner_salary = st.number_input("Prisoner salary per week (£)", min_value=0.0, step=1.0)

    num_supervisors = st.number_input("How many instructors?", min_value=0, step=1)
    customer_covers_supervisors = st.checkbox("Customer provides instructor(s)?")

    supervisor_salaries = []
    if num_supervisors > 0:
        region = PRISON_TO_REGION.get(prison_name, "National")
        options = SUPERVISOR_PAY[region]
        for i in range(num_supervisors):
            sup = st.selectbox(
                f"Instructor {i+1} role",
                [opt["title"] for opt in options],
                key=f"sup{i}",
            )
            salary = next(opt["avg_total"] for opt in options if opt["title"] == sup)
            supervisor_salaries.append(salary)

    effective_pct = st.slider("Adjust instructor % allocation", 0, 100, 100)

    customer_type = st.radio("Customer employment support?", ["Commercial", "Public"])

    dev_rate = st.slider("Development charge %", 0, 20, 10) / 100.0
    vat_rate = 20.0

    submitted = st.form_submit_button("Generate Costs", use_container_width=True)

# ----------------- Run calculations -----------------
if submitted and contract_type != "Select":
    st.subheader("Results Summary")

    if contract_type == "Host":
        host_df, ctx = generate_host_quote(
            workshop_hours=workshop_hours,
            area_m2=100.0,  # placeholder
            usage_key="medium",
            num_prisoners=num_prisoners,
            prisoner_salary=prisoner_salary,
            num_supervisors=num_supervisors,
            customer_covers_supervisors=customer_covers_supervisors,
            supervisor_salaries=supervisor_salaries,
            effective_pct=effective_pct,
            customer_type=customer_type,
            apply_vat=True,
            vat_rate=vat_rate,
            dev_rate=dev_rate,
        )
        st.table(host_df)

    elif contract_type == "Production":
        st.info("Production contract calculations will go here.")

    elif contract_type == "Ad-hoc":
        st.info("Ad-hoc contract calculations will go here.")

else:
    st.caption("⬅ Fill out the form and click *Generate Costs* to calculate.")