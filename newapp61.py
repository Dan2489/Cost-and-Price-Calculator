# newapp61.py
# Streamlit app for Instructor-based Cost & Price Calculator (overheads fixed at 61%)

from io import BytesIO
from datetime import date
import pandas as pd
import streamlit as st

from config61 import CFG
from style61 import inject_govuk_css
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY, BAND3_SHADOW
from sidebar61 import draw_sidebar
from production61 import (
    labour_minutes_budget,
    calculate_production_contractual,
    calculate_adhoc,
)
from host61 import generate_host_quote

# -----------------------------------------------------------------------------
# Page config + CSS
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Instructor Cost Calculator", page_icon="💷", layout="centered")
inject_govuk_css()

st.markdown("## Instructor Cost & Price Calculator")

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _currency(v) -> str:
    try:
        return f"£{float(v):,.2f}"
    except Exception:
        return ""

def export_csv_bytes(df: pd.DataFrame) -> BytesIO:
    b = BytesIO()
    df.to_csv(b, index=False)
    b.seek(0)
    return b

# -----------------------------------------------------------------------------
# Base inputs
# -----------------------------------------------------------------------------
prisons_sorted = ["Select"] + sorted(PRISON_TO_REGION.keys())
prison_choice = st.selectbox("Prison Name", prisons_sorted, index=0, key="prison_choice")
region = PRISON_TO_REGION.get(prison_choice, "Select") if prison_choice != "Select" else "Select"
st.session_state["region"] = region

customer_type = st.selectbox("I want to quote for", ["Select", "Commercial", "Another Government Department"], key="customer_type")
customer_name = st.text_input("Customer Name", key="customer_name")
contract_mode = st.selectbox("Contract type?", ["Select", "Host", "Production"], key="contract_mode")

# Prisoner & instructor inputs
workshop_hours = st.number_input("How many hours per week is the workshop open?", min_value=0.0, format="%.2f", key="workshop_hours")
num_prisoners = st.number_input("How many prisoners employed?", min_value=0, step=1, key="num_prisoners")
prisoner_salary = st.number_input("Prisoner salary per week (£)", min_value=0.0, format="%.2f", key="prisoner_salary")

num_instructors = st.number_input("How many instructors?", min_value=0, step=1, key="num_instructors")
customer_covers_instructors = st.checkbox("Customer provides instructor(s)?", key="customer_covers_instructors")

instructor_salaries = []
if not customer_covers_instructors:
    titles_for_region = SUPERVISOR_PAY.get(region, [])
    if region == "Select" or not titles_for_region:
        st.warning("Select a prison to derive the Region before assigning instructor titles.")
    else:
        for i in range(int(num_instructors)):
            options = [t["title"] for t in titles_for_region]
            sel = st.selectbox(f"Instructor {i+1} title", options, key=f"inst_title_{i}")
            pay = next(t["avg_total"] for t in titles_for_region if t["title"] == sel)
            st.caption(f"Avg Total for {region}: **£{pay:,.0f}** per year")
            instructor_salaries.append(float(pay))

contracts = st.number_input("How many contracts do these instructors oversee?", min_value=1, value=1, key="contracts")
recommended_pct = round((workshop_hours / 37.5) * (1 / contracts) * 100, 1) if contracts and workshop_hours >= 0 else 0
st.subheader("Instructor Time Allocation")
st.info(f"Recommended: {recommended_pct}%")
chosen_pct = st.slider("Adjust instructor % allocation", 0, 100, int(recommended_pct), key="chosen_pct")
effective_pct = int(round(recommended_pct)) if chosen_pct < int(round(recommended_pct)) else int(chosen_pct)

# -----------------------------------------------------------------------------
# Sidebar option: Lock overheads to highest instructor
# -----------------------------------------------------------------------------
draw_sidebar()

# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------
def validate_inputs():
    errors = []
    if prison_choice == "Select":
        errors.append("Select prison")
    if region == "Select":
        errors.append("Region could not be derived from prison selection")
    if customer_type == "Select":
        errors.append("Select customer type")
    if not str(customer_name).strip():
        errors.append("Enter customer name")
    if contract_mode == "Select":
        errors.append("Select contract type")
    if workshop_hours <= 0:
        errors.append("Hours per week must be > 0")
    if prisoner_salary < 0:
        errors.append("Prisoner salary per week cannot be negative")
    if num_prisoners < 0:
        errors.append("Prisoners employed cannot be negative")
    if not customer_covers_instructors:
        if num_instructors <= 0:
            errors.append("Enter number of instructors (>0) or tick 'Customer provides instructor(s)'")
        if region == "Select":
            errors.append("Select a prison/region to populate instructor titles")
        if len(instructor_salaries) != int(num_instructors):
            errors.append("Choose a title for each instructor")
        if any(s <= 0 for s in instructor_salaries):
            errors.append("Instructor Avg Total must be > 0")
    return errors

# -----------------------------------------------------------------------------
# HOST / PRODUCTION HANDLERS
# -----------------------------------------------------------------------------
def run_host():
    errors_top = validate_inputs()
    if st.button("Generate Host Costs"):
        if errors_top:
            st.error("Fix errors:\n- " + "\n- ".join(errors_top))
            return
        host_df, _ctx = generate_host_quote(
            workshop_hours=float(workshop_hours),
            num_prisoners=int(num_prisoners),
            prisoner_salary=float(prisoner_salary),
            num_instructors=int(num_instructors),
            customer_covers_instructors=bool(customer_covers_instructors),
            instructor_salaries=instructor_salaries,
            effective_pct=float(effective_pct),
            customer_type=customer_type,
            apply_vat=True,
            vat_rate=20.0,
        )
        st.dataframe(host_df)

def run_production():
    errors_top = validate_inputs()
    if errors_top:
        st.error("Fix errors:\n- " + "\n- ".join(errors_top))
        return
    st.markdown("---")
    st.subheader("Production settings")

    planned_output_pct = st.slider("Planned Output (%)", min_value=0, max_value=100, value=CFG.GLOBAL_OUTPUT_DEFAULT)
    output_scale = float(planned_output_pct) / 100.0

    prod_type = st.radio("Do you want ad-hoc costs with a deadline, or contractual work?",
                         ["Contractual work", "Ad-hoc costs with deadlines"], index=0, key="prod_type")

    if prod_type == "Contractual work":
        # simplified — show costs per unit and monthly
        num_items = st.number_input("Number of items produced?", min_value=1, value=1, step=1, key="num_items_prod")
        items = []
        for i in range(int(num_items)):
            with st.expander(f"Item {i+1} details", expanded=(i == 0)):
                name = st.text_input(f"Item {i+1} Name", key=f"name_{i}")
                required = st.number_input(f"Prisoners required to make 1 item", min_value=1, value=1, step=1, key=f"req_{i}")
                minutes_per = st.number_input(f"Minutes to make 1 item", min_value=1.0, value=10.0, format="%.2f", key=f"mins_{i}")
                assigned = st.number_input(f"Prisoners assigned to this item", min_value=0, max_value=int(num_prisoners), step=1, key=f"assigned_{i}")
                items.append({"name": name, "required": int(required), "minutes": float(minutes_per), "assigned": int(assigned)})

        results = calculate_production_contractual(
            items, planned_output_pct,
            workshop_hours=float(workshop_hours),
            prisoner_salary=float(prisoner_salary),
            instructor_salaries=instructor_salaries,
            effective_pct=float(effective_pct),
            customer_covers_instructors=bool(customer_covers_instructors),
            customer_type=customer_type,
            apply_vat=True,
            vat_rate=20.0,
            num_prisoners=int(num_prisoners),
            num_instructors=int(num_instructors),
        )
        prod_df = pd.DataFrame(results)
        st.dataframe(prod_df)

    else:
        # Ad-hoc simplified
        num_lines = st.number_input("How many product lines are needed?", min_value=1, value=1, step=1, key="adhoc_num_lines")
        lines = []
        for i in range(int(num_lines)):
            with st.expander(f"Product line {i+1}", expanded=(i == 0)):
                item_name = st.text_input("Item name", key=f"adhoc_name_{i}")
                units_requested = st.number_input("Units requested", min_value=1, value=100, step=1, key=f"adhoc_units_{i}")
                minutes_per_item = st.number_input("Minutes to make one", min_value=1.0, value=10.0, format="%.2f", key=f"adhoc_mins_{i}")
                pris_per_item = st.number_input("Prisoners per unit", min_value=1, value=1, step=1, key=f"adhoc_pris_{i}")
                lines.append({
                    "name": item_name.strip() or f"Item {i+1}",
                    "units": int(units_requested),
                    "mins_per_item": float(minutes_per_item),
                    "pris_per_item": int(pris_per_item),
                })
        if st.button("Calculate Ad-hoc Cost", key="calc_adhoc"):
            result = calculate_adhoc(
                lines, planned_output_pct,
                workshop_hours=float(workshop_hours),
                num_prisoners=int(num_prisoners),
                prisoner_salary=float(prisoner_salary),
                instructor_salaries=instructor_salaries,
                effective_pct=float(effective_pct),
                customer_covers_instructors=bool(customer_covers_instructors),
                customer_type=customer_type,
                apply_vat=True,
                vat_rate=20.0,
                today=date.today(),
            )
            st.json(result)

# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
if contract_mode == "Host":
    run_host()
elif contract_mode == "Production":
    run_production()

# Reset button
if st.button("Reset Selections", key="reset_app_footer"):
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    try:
        st.rerun()
    except Exception:
        st.experimental_rerun()
