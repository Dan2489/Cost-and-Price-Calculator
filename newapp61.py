# newapp61.py

import streamlit as st
import pandas as pd
from config61 import CFG
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
from utils61 import inject_govuk_css, sidebar_controls, fmt_currency, export_doc
import host61
import production61


# ======================
# MAIN APP
# ======================
def main():
    inject_govuk_css()

    # ---- Header with Logo ----
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:20px; margin-bottom:1rem;">
            <img src="https://raw.githubusercontent.com/Dan2489/Cost-and-Price-Calculator/main/logo.png" style="height:80px;">
            <h2 style="margin:0;">Cost and Price Calculator</h2>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- Sidebar Controls ----
    lock_overheads, instructor_pct, prisoner_output = sidebar_controls(
        CFG.GLOBAL_OUTPUT_DEFAULT
    )

    # ---- Form ----
    with st.form("cost_form"):
        prison_name = st.selectbox("Prison Name", list(PRISON_TO_REGION.keys()))
        customer_name = st.text_input("Customer Name")
        contract_type = st.selectbox("Contract Type", ["Host", "Production"])

        workshop_hours = st.number_input(
            "How many hours is the workshop open per week?", min_value=0.0, step=0.5
        )
        num_prisoners = st.number_input(
            "How many prisoners employed per week?", min_value=0, step=1
        )
        prisoner_salary = st.number_input(
            "Average prisoner salary per week (£)", min_value=0.0, step=0.5
        )
        num_instructors = st.number_input("How many instructors?", min_value=0, step=1)

        supervisor_titles = []
        supervisor_salaries = []
        region = PRISON_TO_REGION.get(prison_name, "National")
        available_roles = SUPERVISOR_PAY.get(region, [])

        for i in range(int(num_instructors)):
            choice = st.selectbox(
                f"Instructor {i+1} Title",
                [r["title"] for r in available_roles],
                key=f"instructor_{i}",
            )
            salary = next(
                (r["avg_total"] for r in available_roles if r["title"] == choice), 0
            )
            supervisor_titles.append(choice)
            supervisor_salaries.append(salary)
            st.caption(f"{region} — £{salary:,.0f}")

        num_contracts = st.number_input(
            "How many contracts do they oversee in this workshop?", min_value=1, step=1
        )

        emp_support = st.selectbox(
            "What employment support does the customer offer?",
            ["None", "Employment on release/RoTL", "Post release", "Both"],
        )

        submitted = st.form_submit_button("Generate Costs", use_container_width=True)

    # ---- Logic ----
    if submitted:
        if contract_type == "Host":
            df, ctx = host61.generate_host_quote(
                workshop_hours=workshop_hours,
                num_prisoners=num_prisoners,
                prisoner_salary=prisoner_salary,
                num_supervisors=num_instructors,
                supervisor_salaries=supervisor_salaries,
                effective_pct=instructor_pct,
                customer_covers_supervisors=False,
                region=region,
                customer_type="Commercial",
                apply_vat=True,
                vat_rate=CFG.vat_rate,
                dev_rate=0.20,
                lock_overheads=lock_overheads,
                emp_support=emp_support,
                num_contracts=num_contracts,
            )

            st.subheader("Host Quote")
            st.table(df.style.format({"Amount (£)": fmt_currency}))

        elif contract_type == "Production":
            df, ctx = production61.calculate_production_costs(
                workshop_hours=workshop_hours,
                num_prisoners=num_prisoners,
                prisoner_salary=prisoner_salary,
                supervisor_salaries=supervisor_salaries,
                effective_pct=instructor_pct,
                region=region,
                customer_type="Commercial",
                apply_vat=True,
                vat_rate=CFG.vat_rate,
                lock_overheads=lock_overheads,
                prisoner_output=prisoner_output,
                emp_support=emp_support,
                num_contracts=num_contracts,
            )

            st.subheader("Production Quote")
            st.table(df.style.format(fmt_currency))

        # ---- Export ----
        export_doc(df, customer_name, contract_type)


if __name__ == "__main__":
    main()