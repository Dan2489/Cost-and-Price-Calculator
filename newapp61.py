# newapp61.py

import sys, os
sys.path.append(os.path.dirname(__file__))

import streamlit as st
import pandas as pd

import config61
import tariff61
import utils61
import host61
import production61

CFG = config61.CFG

# ------------------------------
# Streamlit App
# ------------------------------

def main():
    st.title("Cost and Price Calculator")

    # --- Form ---
    with st.form("cost_form"):
        prison_name = st.selectbox("Prison Name", list(tariff61.PRISON_TO_REGION.keys()))
        customer_name = st.text_input("Customer Name")

        contract_type = st.selectbox("Contract Type", ["Host", "Production"])
        workshop_hours = st.number_input("How many hours is the workshop open per week?", min_value=1.0, step=0.5)
        num_prisoners = st.number_input("How many prisoners employed per week?", min_value=0, step=1)
        prisoner_salary = st.number_input("Average prisoner salary per week (£)", min_value=0.0, step=1.0)

        num_instructors = st.number_input("How many instructors?", min_value=0, step=1)

        instructor_salaries = []
        if num_instructors > 0:
            region = tariff61.PRISON_TO_REGION[prison_name]
            region_band = tariff61.SUPERVISOR_PAY[region]
            for i in range(int(num_instructors)):
                title = st.selectbox(f"Instructor {i+1} Title", [r["title"] for r in region_band], key=f"inst_{i}")
                selected = next(r for r in region_band if r["title"] == title)
                st.caption(f"{region} — £{selected['avg_total']:,}")
                instructor_salaries.append(selected["avg_total"])

        contracts_overseen = st.number_input("How many contracts do they oversee in this workshop?", min_value=1, step=1)

        emp_support = st.selectbox(
            "What employment support does the customer offer?",
            ["None", "Employment on Release/ROTL", "Post Release", "Both"]
        )

        if contract_type == "Production":
            prod_mode = st.radio("Production Type", ["Contractual", "Adhoc"])
            pricing_mode = st.radio("Pricing Mode", ["Maximum Output", "Target Output"])
        else:
            prod_mode, pricing_mode = None, None

        submitted = st.form_submit_button("Generate Costs")

    # --- Sidebar ---
    with st.sidebar:
        st.header("Controls")
        lock_overheads = st.checkbox("Lock overheads to highest instructor salary", value=False)
        effective_pct = st.slider("Instructor allocation (%)", 0, 100, 100)
        prisoner_output = st.slider("Prisoner labour output (%)", 0, 100, CFG["GLOBAL_OUTPUT_DEFAULT"])

    # --- Results ---
    if submitted:
        region = tariff61.PRISON_TO_REGION[prison_name]

        if contract_type == "Host":
            df, ctx = host61.generate_host_quote(
                workshop_hours=workshop_hours,
                num_prisoners=num_prisoners,
                prisoner_salary=prisoner_salary,
                instructor_salaries=instructor_salaries,
                contracts_overseen=contracts_overseen,
                emp_support=emp_support,
                lock_overheads=lock_overheads,
                instructor_allocation=effective_pct,
            )
            st.subheader("Host Costs")
            st.dataframe(df.style.format({"£ per Week/Month": "£{:.2f}"}))

        elif contract_type == "Production":
            if prod_mode == "Contractual":
                results = production61.calculate_production_contractual(
                    items=[{"name": "Item 1", "minutes": 10, "required": 1, "assigned": num_prisoners}],
                    output_pct=prisoner_output,
                    workshop_hours=workshop_hours,
                    prisoner_salary=prisoner_salary,
                    supervisor_salaries=instructor_salaries,
                    effective_pct=effective_pct,
                    customer_covers_supervisors=(num_instructors == 0),
                    region=region,
                    customer_type="Commercial",  # could extend later
                    apply_vat=True,
                    vat_rate=CFG["vat_rate"],
                    num_prisoners=num_prisoners,
                    num_supervisors=num_instructors,
                    dev_rate=CFG["development_charge"],
                    pricing_mode="target" if pricing_mode == "Target Output" else "as-is",
                    targets=None,
                    lock_overheads=lock_overheads,
                )
                st.subheader("Production Costs")
                st.dataframe(pd.DataFrame(results).style.format("£{:.2f}"))
            else:
                st.info("Adhoc production pricing not yet implemented in this file.")

if __name__ == "__main__":
    main()