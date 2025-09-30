import streamlit as st
import pandas as pd

from config61 import CFG
from host61 import generate_host_quote
from production61 import (
    labour_minutes_budget,
    calculate_production_contractual,
    calculate_adhoc,
)
from utils61 import inject_govuk_css, PRISON_TO_REGION, SUPERVISOR_PAY, draw_sidebar

# ------------------------
# App styling
# ------------------------
inject_govuk_css()

st.title("Cost and Price Calculator (Instructor Cost Model)")

# ------------------------
# Sidebar controls
# ------------------------
lock_overheads, chosen_pct, prisoner_salary = draw_sidebar(
    recommended_pct=st.session_state.get("recommended_pct", 50),
    chosen_pct=st.session_state.get("chosen_pct", 50),
    prisoner_salary=st.session_state.get("prisoner_salary", 0.0),
)

st.session_state["chosen_pct"] = chosen_pct
st.session_state["prisoner_salary"] = prisoner_salary

# ------------------------
# Main form
# ------------------------
with st.form("main_form"):
    prison = st.selectbox("Prison Name", ["Select"] + sorted(PRISON_TO_REGION.keys()))
    customer_name = st.text_input("Customer Name")
    contract_type = st.selectbox("Contract type?", ["Select", "Commercial", "Public"])
    num_prisoners = st.number_input("How many prisoners employed?", min_value=0, step=1)
    prisoner_salary_input = st.number_input("Prisoner salary per week (£)", min_value=0.0, step=0.5)
    num_supervisors = st.number_input("How many instructors?", min_value=0, step=1)
    customer_covers_supervisors = st.checkbox("Customer provides instructor(s)?")
    workshop_hours = st.number_input("How many hours per week is the workshop open?", min_value=0.0, step=0.5)

    submitted = st.form_submit_button("Generate Costs")

# ------------------------
# Process submission
# ------------------------
if submitted:
    if prison == "Select" or contract_type == "Select":
        st.error("Please select a prison and contract type.")
    else:
        # Run cost model
        host_df, ctx = generate_host_quote(
            workshop_hours=workshop_hours,
            area_m2=0.0,
            usage_key="low",  # utilities removed, placeholder
            num_prisoners=num_prisoners,
            prisoner_salary=prisoner_salary_input,
            num_supervisors=num_supervisors,
            customer_covers_supervisors=customer_covers_supervisors,
            supervisor_salaries=[
                SUPERVISOR_PAY[PRISON_TO_REGION[prison]][0]["avg_total"]
                for _ in range(num_supervisors)
            ],
            effective_pct=chosen_pct,
            customer_type=contract_type,
            apply_vat=True,
            vat_rate=20.0,
            dev_rate=0.1,  # development rate
        )

        # ------------------------
        # Insert Development charge breakdown
        # ------------------------
        if "Development charge (applied)" in host_df["Item"].values:
            dev_row = host_df.loc[host_df["Item"] == "Development charge (applied)"].iloc[0]
            dev_charge = dev_row["Amount (£)"]

            # Example rule for reductions — you can replace with your logic
            reduction = dev_charge * 0.2 if contract_type == "Commercial" else 0.0
            revised = dev_charge - reduction

            # Insert rows in proper order
            extra_rows = []
            extra_rows.append(("Development charge (applied)", dev_charge))
            if reduction > 0:
                extra_rows.append(("Reductions", -reduction))
            extra_rows.append(("Revised Development charge", revised))

            # Remove old row and replace
            host_df = host_df[host_df["Item"] != "Development charge (applied)"]
            for row in extra_rows[::-1]:
                host_df.loc[len(host_df)] = row

        # ------------------------
        # Show results
        # ------------------------
        st.subheader("Monthly Cost Breakdown")
        def highlight_neg(val):
            return "color: red;" if val < 0 else ""
        st.dataframe(host_df.style.applymap(highlight_neg, subset=["Amount (£)"]))