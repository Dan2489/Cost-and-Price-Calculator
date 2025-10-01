# newapp61.py
import streamlit as st
import pandas as pd

from config61 import CFG
import host61
import production61
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
from utils61 import inject_govuk_css, sidebar_controls, render_summary_table, export_doc

# ======================
# App Header with Logo
# ======================
def app_header():
    st.markdown(
        """
        <div style="display:flex; align-items:center; gap:20px; margin-bottom:1rem;">
            <img src="https://raw.githubusercontent.com/Dan2489/Cost-and-Price-Calculator/main/logo.png" style="height:80px;">
            <h2 style="margin:0;">Cost and Price Calculator</h2>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ======================
# Main
# ======================
def main():
    inject_govuk_css()
    app_header()

    # Sidebar controls
    lock_overheads, instructor_pct, prisoner_output = sidebar_controls(
        CFG.GLOBAL_OUTPUT_DEFAULT
    )

    # Main form
    with st.form("main_form"):
        prison_name = st.selectbox("Prison Name", sorted(PRISON_TO_REGION.keys()))
        customer_name = st.text_input("Customer Name")
        contract_type = st.selectbox("Contract Type", ["Host", "Production"])
        workshop_hours = st.number_input("How many hours is the workshop open per week?", min_value=0.0, step=0.5)
        num_prisoners = st.number_input("How many prisoners employed per week?", min_value=0, step=1)
        prisoner_salary = st.number_input("Average prisoner salary per week (£)", min_value=0.0, step=0.5)

        num_supervisors = st.number_input("How many instructors?", min_value=0, step=1)
        supervisor_titles, supervisor_salaries = [], []

        region = PRISON_TO_REGION.get(prison_name, "National")
        if num_supervisors > 0:
            for i in range(num_supervisors):
                options = [s["title"] for s in SUPERVISOR_PAY[region]]
                sel_title = st.selectbox(f"Instructor {i+1} Title", options, key=f"sup_title_{i}")
                sup_salary = next(s["avg_total"] for s in SUPERVISOR_PAY[region] if s["title"] == sel_title)
                supervisor_titles.append(sel_title)
                supervisor_salaries.append(sup_salary)
                st.caption(f"{region} — £{sup_salary:,.0f}")

        num_contracts = st.number_input("How many contracts do they oversee in this workshop?", min_value=1, step=1)
        employment_support = st.selectbox(
            "What employment support does the customer offer?",
            ["None", "Employment on release/RoTL", "Post release", "Both"],
        )

        submitted = st.form_submit_button("Generate Costs")

    # Run calculation
    if submitted:
        meta = {"customer": customer_name, "prison": prison_name, "region": region}

        if contract_type == "Host":
            df, ctx = host61.generate_host_quote(
                num_prisoners=num_prisoners,
                prisoner_salary=prisoner_salary,
                num_supervisors=num_supervisors,
                supervisor_salaries=supervisor_salaries,
                effective_pct=instructor_pct,
                customer_covers_supervisors=False,
                customer_type="Commercial",
                dev_rate=0.20 if employment_support == "None" else 0.10 if employment_support in ["Employment on release/RoTL", "Post release"] else 0.00,
                contracts_overseen=num_contracts,
                lock_overheads=lock_overheads,
                region=region,
            )
            st.markdown(render_summary_table(df.values.tolist(), dev_reduction=True), unsafe_allow_html=True)
            st.download_button("Download HTML", data=export_doc("Host Quote", meta, df.to_html(index=False)), file_name="host_quote.html", mime="text/html")

        else:  # Production
            df, ctx = production61.calculate_production_costs(
                workshop_hours=workshop_hours,
                num_prisoners=num_prisoners,
                prisoner_salary=prisoner_salary,
                supervisor_salaries=supervisor_salaries,
                effective_pct=instructor_pct,
                prisoner_output=prisoner_output,
                region=region,
                lock_overheads=lock_overheads,
                employment_support=employment_support,
            )
            st.markdown(render_summary_table(df.values.tolist()), unsafe_allow_html=True)
            st.download_button("Download HTML", data=export_doc("Production Quote", meta, df.to_html(index=False)), file_name="production_quote.html", mime="text/html")

    # Reset button
    if st.button("Reset Selections"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.experimental_rerun()


if __name__ == "__main__":
    main()