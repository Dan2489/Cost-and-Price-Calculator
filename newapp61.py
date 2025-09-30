# newapp61.py
import streamlit as st
import pandas as pd
from datetime import date

from config61 import CFG
from utils61 import inject_govuk_css, fmt_currency, sidebar_controls
import host61
import production61
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY


# -------------------------------------------------
# Page Setup
# -------------------------------------------------
st.set_page_config(page_title="Cost and Price Calculator", page_icon="💷", layout="centered")
inject_govuk_css()

st.markdown("## Cost and Price Calculator")

# Sidebar controls
controls = sidebar_controls()
lock_overheads = controls["lock_overheads"]
instructor_pct = controls["instructor_pct"]
prisoner_output = controls["prisoner_output"]


# -------------------------------------------------
# Helper for table rendering
# -------------------------------------------------
def render_df(df: pd.DataFrame) -> None:
    if df is not None and not df.empty:
        st.markdown(df.to_html(index=False, escape=False), unsafe_allow_html=True)


# -------------------------------------------------
# Main App
# -------------------------------------------------
def main():
    # Prison
    prison_choice = st.selectbox("Prison Name", ["Select"] + sorted(PRISON_TO_REGION.keys()))
    region = PRISON_TO_REGION.get(prison_choice, "Select")

    # Customer
    customer_name = st.text_input("Customer Name")
    contract_type = st.selectbox("Contract Type", ["Select", "Host", "Production"])

    # Core inputs
    workshop_hours = st.number_input("How many hours is the workshop open per week?", min_value=0.0, format="%.2f")
    num_prisoners = st.number_input("How many prisoners employed per week?", min_value=0, step=1)
    prisoner_salary = st.number_input("Average prisoner salary per week (£)", min_value=0.0, format="%.2f")

    # Instructors
    num_supervisors = st.number_input("How many instructors?", min_value=0, step=1)
    supervisor_salaries = []
    if region != "Select" and num_supervisors > 0:
        titles_for_region = SUPERVISOR_PAY.get(region, [])
        for i in range(int(num_supervisors)):
            options = [t["title"] for t in titles_for_region]
            sel = st.selectbox(f"Instructor {i+1} Title", options, key=f"inst_title_{i}")
            pay = next(t["avg_total"] for t in titles_for_region if t["title"] == sel)
            st.caption(f"{region} — £{pay:,.0f}")
            supervisor_salaries.append(float(pay))

    contracts = st.number_input("How many contracts do they oversee in this workshop?", min_value=1, value=1)

    # Development charge
    support = st.selectbox(
        "What employment support does the customer offer?",
        ["None", "Employment on release/RoTL", "Post release", "Both"],
    )
    dev_rate = 0.20
    if support == "Employment on release/RoTL":
        dev_rate -= 0.10
    elif support == "Post release":
        dev_rate -= 0.10
    elif support == "Both":
        dev_rate -= 0.20

    # ------------------------
    # Run Host Mode
    # ------------------------
    if contract_type == "Host":
        if st.button("Generate Host Costs"):
            df, ctx = host61.generate_host_quote(
                workshop_hours=workshop_hours,
                num_prisoners=num_prisoners,
                prisoner_salary=prisoner_salary,
                num_supervisors=num_supervisors,
                supervisor_salaries=supervisor_salaries,
                instructor_allocation=instructor_pct,
                customer_type="Commercial",
                dev_rate=dev_rate,
                lock_overheads=lock_overheads,
                region=region,
            )
            render_df(df)

    # ------------------------
    # Run Production Mode
    # ------------------------
    elif contract_type == "Production":
        prod_mode = st.radio("Contractual or Ad-hoc?", ["Contractual", "Ad-hoc"])

        if prod_mode == "Contractual":
            pricing_mode = st.radio("Pricing method", ["Maximum units", "Target units"])
            num_items = st.number_input("Number of items", min_value=1, value=1, step=1)

            items, targets = [], []
            for i in range(int(num_items)):
                with st.expander(f"Item {i+1} details", expanded=True):
                    name = st.text_input(f"Item {i+1} Name", key=f"name_{i}")
                    required = st.number_input(f"Prisoners required per unit", min_value=1, value=1, key=f"req_{i}")
                    minutes_per = st.number_input(f"Minutes to make one unit", min_value=1.0, value=10.0, key=f"mins_{i}")
                    assigned = st.number_input(f"Prisoners assigned", min_value=0, value=0, key=f"assigned_{i}")
                    items.append({"name": name, "required": int(required), "minutes": float(minutes_per), "assigned": int(assigned)})

                    if pricing_mode == "Target units":
                        tgt = st.number_input("Target units per week", min_value=0, value=0, key=f"target_{i}")
                        targets.append(int(tgt))

            if st.button("Generate Production Costs"):
                results = production61.calculate_production_contractual(
                    items,
                    prisoner_output,
                    workshop_hours=workshop_hours,
                    prisoner_salary=prisoner_salary,
                    supervisor_salaries=supervisor_salaries,
                    effective_pct=instructor_pct,
                    customer_covers_supervisors=False,  # checkbox removed for clarity
                    region=region,
                    customer_type="Commercial",
                    apply_vat=True,
                    vat_rate=20.0,
                    num_prisoners=num_prisoners,
                    num_supervisors=num_supervisors,
                    dev_rate=dev_rate,
                    pricing_mode="target" if pricing_mode == "Target units" else "as-is",
                    targets=targets if pricing_mode == "Target units" else None,
                    lock_overheads=lock_overheads,
                )
                df = pd.DataFrame(results)
                render_df(df)

        else:  # Ad-hoc
            st.write("Ad-hoc production pricing not yet implemented.")


# -------------------------------------------------
# Run
# -------------------------------------------------
if __name__ == "__main__":
    main()