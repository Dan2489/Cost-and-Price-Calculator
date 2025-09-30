# newapp61.py
import streamlit as st
import host61
import production61
from utils61 import inject_govuk_css, sidebar_controls, render_summary_table
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
from config61 import CFG


def main():
    inject_govuk_css()

    st.title("Cost and Price Calculator")

    # ---- Form ----
    with st.form("main_form"):
        prison_name = st.selectbox("Prison Name", sorted(PRISON_TO_REGION.keys()))
        customer_name = st.text_input("Customer Name")
        contract_type = st.selectbox("Contract Type", ["Host", "Production"])
        workshop_hours = st.number_input("How many hours is the workshop open per week?", min_value=0.0, step=0.5)
        num_prisoners = st.number_input("How many prisoners employed per week?", min_value=0, step=1)
        prisoner_salary = st.number_input("Average prisoner salary per week (£)", min_value=0.0, step=0.5)
        num_instructors = st.number_input("How many instructors?", min_value=0, step=1)

        supervisor_titles = []
        supervisor_salaries = []
        region = PRISON_TO_REGION.get(prison_name, "National")
        for i in range(num_instructors):
            title = st.selectbox(
                f"Instructor {i+1} Title",
                [s["title"] for s in SUPERVISOR_PAY[region]],
                key=f"inst_title_{i}"
            )
            supervisor_titles.append(title)
            salary = next(s["avg_total"] for s in SUPERVISOR_PAY[region] if s["title"] == title)
            supervisor_salaries.append(salary)
            st.caption(f"{region} — £{salary:,.0f}")

        num_contracts = st.number_input("How many contracts do they oversee in this workshop?", min_value=1, step=1)
        emp_support = st.selectbox(
            "What employment support does the customer offer?",
            ["None", "Employment on release/RoTL", "Post release", "Both"]
        )

        submitted = st.form_submit_button("Generate Costs")

    # ---- Sidebar ----
    lock_overheads, instructor_pct, prisoner_output = sidebar_controls(
        CFG["GLOBAL_OUTPUT_DEFAULT"], workshop_hours, num_contracts
    )

    if not submitted:
        return

    # ---- Dev charge rate ----
    dev_rate = 0.2
    if emp_support == "Employment on release/RoTL":
        dev_rate -= 0.1
    elif emp_support == "Post release":
        dev_rate -= 0.1
    elif emp_support == "Both":
        dev_rate -= 0.2
    dev_rate = max(dev_rate, 0.0)

    # ---- Host ----
    if contract_type == "Host":
        df, ctx = host61.generate_host_quote(
            workshop_hours=workshop_hours,
            num_prisoners=num_prisoners,
            prisoner_salary=prisoner_salary,
            supervisor_salaries=supervisor_salaries,
            effective_pct=instructor_pct,
            customer_covers_supervisors=(num_instructors == 0),
            region=region,
            dev_rate=dev_rate,
            customer_type="Commercial",
            lock_overheads=lock_overheads,
        )

        st.subheader("Host Monthly Breakdown")
        st.markdown(render_summary_table(list(df.itertuples(index=False)), dev_reduction=True), unsafe_allow_html=True)

    # ---- Production ----
    else:
        mode = st.selectbox("Production Mode", ["Contractual", "Ad-hoc"])
        if mode == "Contractual":
            pricing_mode = st.radio("Would you like a price for:", ["Maximum output", "Targeted output"])
            items = []
            num_items = st.number_input("Number of production items", min_value=1, step=1)
            for i in range(num_items):
                st.markdown(f"**Item {i+1}**")
                name = st.text_input("Name", key=f"item_name_{i}")
                minutes = st.number_input("Minutes per unit", min_value=0.0, step=1.0, key=f"item_mins_{i}")
                required = st.number_input("Prisoners required per unit", min_value=1, step=1, key=f"item_req_{i}")
                assigned = st.number_input("Prisoners assigned", min_value=0, step=1, key=f"item_ass_{i}")
                items.append({"name": name, "minutes": minutes, "required": required, "assigned": assigned})

            results = production61.calculate_production_contractual(
                items, prisoner_output,
                workshop_hours=workshop_hours,
                prisoner_salary=prisoner_salary,
                supervisor_salaries=supervisor_salaries,
                effective_pct=instructor_pct,
                customer_covers_supervisors=(num_instructors == 0),
                region=region,
                customer_type="Commercial",
                apply_vat=True,
                vat_rate=20.0,
                num_prisoners=num_prisoners,
                num_supervisors=num_instructors,
                dev_rate=dev_rate,
                pricing_mode="target" if pricing_mode == "Targeted output" else "as-is",
                lock_overheads=lock_overheads,
            )

            st.subheader("Production Contractual Pricing")
            st.dataframe(results)

        else:
            st.info("Ad-hoc production not yet implemented.")


if __name__ == "__main__":
    main()