# newapp61.py
import streamlit as st
import pandas as pd
from config61 import CFG
from utils61 import inject_govuk_css, labour_minutes_budget
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
from host61 import generate_host_quote
from production61 import calculate_production_contractual

# =========================================================
# Page setup
# =========================================================
st.set_page_config(page_title="Cost and Price Calculator", layout="wide")
inject_govuk_css()

st.markdown(
    "<h1 class='govuk-heading-l'>Cost and Price Calculator</h1>",
    unsafe_allow_html=True,
)

# =========================================================
# Sidebar controls
# =========================================================
st.sidebar.header("Adjustments")

lock_overheads = st.sidebar.checkbox("Lock overheads to highest instructor salary", value=False)

inst_allocation = st.sidebar.slider(
    "Adjust instructor % allocation", min_value=0, max_value=100, value=100, step=1
)

prisoner_output = st.sidebar.slider(
    "Prisoner output % (Production only)", min_value=10, max_value=100, value=100, step=5
)

# =========================================================
# Main Form
# =========================================================
with st.form("contract_form"):
    prison_name = st.selectbox("Prison Name", [""] + sorted(PRISON_TO_REGION.keys()))
    customer_name = st.text_input("Customer Name", "")
    contract_type = st.selectbox("Contract Type", ["", "Host", "Production"])

    workshop_hours = st.number_input("How many hours per week is the workshop open?", min_value=0.0, step=0.5)
    num_prisoners = st.number_input("How many prisoners employed per week?", min_value=0, step=1)
    prisoner_salary = st.number_input("Average prisoner salary per week (£)", min_value=0.0, step=1.0)

    num_instructors = st.number_input("How many instructors?", min_value=0, step=1)

    instructor_titles = []
    supervisor_salaries = []
    region = None
    if prison_name:
        region = PRISON_TO_REGION.get(prison_name, "National")

    for i in range(num_instructors):
        sel = st.selectbox(
            f"Instructor {i+1} Title",
            [""] + [entry["title"] for entry in SUPERVISOR_PAY.get(region, [])],
            key=f"instructor_{i}"
        )
        instructor_titles.append(sel)
        if sel:
            salary = next(
                (entry["avg_total"] for entry in SUPERVISOR_PAY[region] if entry["title"] == sel),
                0.0
            )
            supervisor_salaries.append(salary)
            st.caption(f"Region: {region}, Salary: £{salary:,.2f}")

    contracts_overseen = st.number_input("How many contracts do they oversee in this workshop?", min_value=1, value=1)

    employment_support = st.selectbox(
        "Customer Employment Support",
        ["", "None", "Employment on Release / ROTL", "Post Release", "Both"]
    )

    # Production-specific questions
    pricing_mode = None
    items = []
    targets = []
    if contract_type == "Production":
        pricing_mode = st.radio("Contractual or Adhoc?", ["Contractual", "Adhoc"])
        price_basis = st.radio("Would you like a price for:", ["Maximum Output", "Targeted Output"])

        if price_basis == "Targeted Output":
            st.markdown("### Production Items")
            num_items = st.number_input("How many items?", min_value=1, step=1, value=1)
            for i in range(num_items):
                name = st.text_input(f"Item {i+1} Name", key=f"item_name_{i}")
                minutes = st.number_input(f"Minutes per unit (Item {i+1})", min_value=0.0, step=1.0, key=f"item_minutes_{i}")
                required = st.number_input(f"Prisoners required per unit (Item {i+1})", min_value=1, step=1, key=f"item_required_{i}")
                assigned = st.number_input(f"Prisoners assigned to item (Item {i+1})", min_value=0, step=1, key=f"item_assigned_{i}")
                target_units = st.number_input(f"Target units/week (Item {i+1})", min_value=0, step=1, key=f"item_target_{i}")

                items.append({"name": name, "minutes": minutes, "required": required, "assigned": assigned})
                targets.append(target_units)

    submitted = st.form_submit_button("Generate Costs")

# =========================================================
# Development charge adjustment logic
# =========================================================
def adjusted_dev_rate(base_rate: float, support: str) -> float:
    if support == "Employment on Release / ROTL":
        return base_rate - 0.10
    elif support == "Post Release":
        return base_rate - 0.10
    elif support == "Both":
        return base_rate - 0.20
    return base_rate

# =========================================================
# Processing
# =========================================================
if submitted and prison_name and contract_type:
    st.markdown("## Results")

    dev_rate = adjusted_dev_rate(CFG["DEV_RATE_BASE"], employment_support)

    if contract_type == "Host":
        host_df, ctx = generate_host_quote(
            workshop_hours=workshop_hours,
            area_m2=0.0,  # removed
            usage_key="",
            num_prisoners=num_prisoners,
            prisoner_salary=prisoner_salary,
            num_supervisors=num_instructors,
            customer_covers_supervisors=False,
            supervisor_salaries=supervisor_salaries,
            effective_pct=inst_allocation,
            customer_type="Commercial",  # assume Commercial unless you add GOV option
            apply_vat=True,
            vat_rate=CFG["VAT_RATE"],
            dev_rate=dev_rate,
            lock_overheads=lock_overheads,
        )

        st.dataframe(host_df, use_container_width=True)

    elif contract_type == "Production":
        results = calculate_production_contractual(
            items=items,
            output_pct=prisoner_output,
            workshop_hours=workshop_hours,
            prisoner_salary=prisoner_salary,
            supervisor_salaries=supervisor_salaries,
            effective_pct=inst_allocation,
            customer_covers_supervisors=False,
            region=region,
            customer_type="Commercial",
            apply_vat=True,
            vat_rate=CFG["VAT_RATE"],
            num_prisoners=num_prisoners,
            num_supervisors=num_instructors,
            dev_rate=dev_rate,
            pricing_mode="target" if price_basis == "Targeted Output" else "as-is",
            targets=targets,
            lock_overheads=lock_overheads,
        )

        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True)

        total_ex_vat = df["Monthly Total ex VAT (£)"].sum()
        total_inc_vat = df["Monthly Total inc VAT (£)"].sum()
        st.markdown(f"**Grand Total ex VAT:** £{total_ex_vat:,.2f}")
        st.markdown(f"**Grand Total inc VAT:** £{total_inc_vat:,.2f}")