import streamlit as st
import pandas as pd
import datetime as dt

from config61 import CFG
from host61 import generate_host_quote, host_summary_table
from production61 import calculate_production_costs, production_summary_table
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
from utils61 import (
    render_sidebar,
    format_currency,
    format_number,
    format_percent,
)

# ---------------- APP SETUP ----------------
st.set_page_config(page_title="Cost and Price Calculator", layout="wide")

st.title("Cost and Price Calculator")

# ---------------- MAIN FORM ----------------
with st.form("contract_form"):
    # Prison Name
    prison_name = st.selectbox("Prison Name", [""] + list(PRISON_TO_REGION.keys()))

    # Customer Name
    customer_name = st.text_input("Customer Name", "")

    # Contract Type
    contract_type = st.selectbox("Contract Type", ["", "Host", "Production"])

    # Workshop hours per week
    workshop_hours = st.number_input(
        "How many hours per week is the workshop open?",
        min_value=0.0,
        step=0.5,
        format="%.2f",
    )

    # Prisoners employed
    num_prisoners = st.number_input(
        "How many prisoners employed?",
        min_value=0,
        step=1,
    )

    # Prisoner salary
    prisoner_salary = st.number_input(
        "Average prisoner salary per week (£)",
        min_value=0.0,
        step=1.0,
        format="%.2f",
    )

    # Instructors
    num_instructors = st.number_input(
        "How many instructors?",
        min_value=0,
        step=1,
    )

    instructor_titles = []
    instructor_salaries = []
    if num_instructors > 0 and prison_name:
        region = PRISON_TO_REGION.get(prison_name, "National")
        for i in range(num_instructors):
            title = st.selectbox(
                f"Instructor {i+1} Title",
                list(SUPERVISOR_PAY.keys()),
                key=f"instructor_title_{i}",
            )
            instructor_titles.append(title)
            salary = SUPERVISOR_PAY[title][region]
            instructor_salaries.append(salary)
            st.caption(f"Region: {region} – Salary: £{salary:,.2f}")

    # Contracts overseen
    contracts_overseen = st.number_input(
        "How many contracts do they oversee in this workshop?",
        min_value=1,
        step=1,
        value=1,
    )

    # Customer employment support
    emp_support = st.selectbox(
        "What employment support does the customer offer?",
        ["", "None", "Employment on Release/ROTL", "Post Release", "Both"],
    )

    submitted = st.form_submit_button("Generate Costs")

# ---------------- SIDEBAR ----------------
usage_key = render_sidebar()

# ---------------- RESULTS ----------------
if submitted:
    today = dt.date.today().strftime("%d %B %Y")

    if contract_type == "Host":
        st.subheader("Host Quote")
        df_host, ctx_host = generate_host_quote(
            workshop_hours=workshop_hours,
            num_prisoners=num_prisoners,
            prisoner_salary=prisoner_salary,
            instructor_salaries=instructor_salaries,
            contracts_overseen=contracts_overseen,
            emp_support=emp_support,
            lock_overheads=st.session_state.get("lock_overheads", False),
            instructor_allocation=st.session_state.get("instructor_allocation", 100),
        )
        st.write(host_summary_table(df_host, ctx_host))

    elif contract_type == "Production":
        st.subheader("Production Quote")
        df_prod, ctx_prod = calculate_production_costs(
            workshop_hours=workshop_hours,
            num_prisoners=num_prisoners,
            prisoner_salary=prisoner_salary,
            instructor_salaries=instructor_salaries,
            contracts_overseen=contracts_overseen,
            emp_support=emp_support,
            lock_overheads=st.session_state.get("lock_overheads", False),
            instructor_allocation=st.session_state.get("instructor_allocation", 100),
            prisoner_output=st.session_state.get("prisoner_output", 100),
        )
        st.write(production_summary_table(df_prod, ctx_prod))

    else:
        st.warning("Please select a contract type.")