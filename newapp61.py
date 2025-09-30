# newapp61.py
# Streamlit app using instructor-only overheads model (no utilities).
import pandas as pd
import streamlit as st
from io import BytesIO
from datetime import date

from config61 import CFG
from style61 import inject_govuk_css
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
from production61 import (
    labour_minutes_budget,
    calculate_production_contractual,
    calculate_adhoc,
)
from host61 import generate_host_quote

# -----------------------------------------------------------------------------
# Page setup
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Cost and Price Calculator", page_icon="💷", layout="centered")
inject_govuk_css()
st.markdown("## Cost and Price Calculator (Instructor Cost Model)")

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
# Sidebar
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("Options")
    lock_overheads = st.checkbox("Lock overheads against highest instructor cost", key="lock_overheads")

# -----------------------------------------------------------------------------
# Inputs
# -----------------------------------------------------------------------------
prisons_sorted = ["Select"] + sorted(PRISON_TO_REGION.keys())
prison_choice = st.selectbox("Prison Name", prisons_sorted, index=0, key="prison_choice")
region = PRISON_TO_REGION.get(prison_choice, "Select") if prison_choice != "Select" else "Select"
st.session_state["region"] = region

customer_type = st.selectbox("I want to quote for", ["Select", "Commercial", "Another Government Department"], key="customer_type")
customer_name = st.text_input("Customer Name", key="customer_name")
workshop_mode = st.selectbox("Contract type?", ["Select", "Host", "Production"], key="workshop_mode")

workshop_hours = st.number_input("How many hours per week is the workshop open?", min_value=0.0, format="%.2f", key="workshop_hours")
num_prisoners   = st.number_input("How many prisoners employed?", min_value=0, step=1, key="num_prisoners")
prisoner_salary = st.number_input("Prisoner salary per week (£)", min_value=0.0, format="%.2f", key="prisoner_salary")
num_supervisors = st.number_input("How many instructors?", min_value=0, step=1, key="num_supervisors")
customer_covers_supervisors = st.checkbox("Customer provides instructor(s)?", key="customer_covers_supervisors")

supervisor_salaries = []
if not customer_covers_supervisors:
    titles_for_region = SUPERVISOR_PAY.get(region, [])
    if region == "Select" or not titles_for_region:
        st.warning("Select a prison to derive the Region before assigning instructor titles.")
    else:
        for i in range(int(num_supervisors)):
            options = [t["title"] for t in titles_for_region]
            sel = st.selectbox(f"Instructor {i+1} title", options, key=f"inst_title_{i}")
            pay = next(t["avg_total"] for t in titles_for_region if t["title"] == sel)
            st.caption(f"Avg Total for {region}: **£{pay:,.0f}** per year")
            supervisor_salaries.append(float(pay))

contracts = st.number_input("How many contracts do these instructors oversee?", min_value=1, value=1, key="contracts")
recommended_pct = round((workshop_hours / 37.5) * (1 / contracts) * 100, 1) if contracts and workshop_hours >= 0 else 0
st.subheader("Instructor Time Allocation")
st.info(f"Recommended: {recommended_pct}%")
chosen_pct = st.slider("Adjust instructor % allocation", 0, 100, int(recommended_pct), key="chosen_pct")
effective_pct = int(round(recommended_pct)) if chosen_pct < int(round(recommended_pct)) else int(chosen_pct)
if chosen_pct < int(round(recommended_pct)):
    st.warning("You selected less than recommended — using the recommended % for pricing.")

# Development charge (Commercial only)
dev_rate = 0.0
if customer_type == "Commercial":
    support = st.selectbox(
        "Customer employment support?",
        ["None", "Employment on release/RoTL", "Post release", "Both"],
        help="Affects development charge (on overheads). 'Both' reduces dev charge to 0%."
    )
    if support == "None":
        dev_rate = 0.20
    elif support in ("Employment on release/RoTL", "Post release"):
        dev_rate = 0.10
    else:
        dev_rate = 0.00

# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------
def validate_inputs():
    errors = []
    if prison_choice == "Select": errors.append("Select prison")
    if region == "Select": errors.append("Region could not be derived from prison selection")
    if customer_type == "Select": errors.append("Select customer type")
    if not str(customer_name).strip(): errors.append("Enter customer name")
    if workshop_mode == "Select": errors.append("Select contract type")
    if workshop_mode == "Production" and workshop_hours <= 0: errors.append("Hours per week must be > 0 (Production)")
    if prisoner_salary < 0: errors.append("Prisoner salary per week cannot be negative")
    if num_prisoners < 0: errors.append("Prisoners employed cannot be negative")
    if not customer_covers_supervisors:
        if num_supervisors <= 0: errors.append("Enter number of instructors (>0) or tick 'Customer provides instructor(s)'")
        if region == "Select": errors.append("Select a prison/region to populate instructor titles")
        if len(supervisor_salaries) != int(num_supervisors): errors.append("Choose a title for each instructor")
        if any(s <= 0 for s in supervisor_salaries): errors.append("Instructor Avg Total must be > 0")
    return errors

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
if workshop_mode == "Host":
    if st.button("Generate Costs"):
        errors_top = validate_inputs()
        if errors_top:
            st.error("Fix errors:\n- " + "\n- ".join(errors_top))
        else:
            host_df, _ctx = generate_host_quote(
                workshop_hours=float(workshop_hours),
                num_prisoners=int(num_prisoners),
                prisoner_salary=float(prisoner_salary),
                num_supervisors=int(num_supervisors),
                customer_covers_supervisors=bool(customer_covers_supervisors),
                supervisor_salaries=supervisor_salaries,
                effective_pct=float(effective_pct),
                customer_type=customer_type,
                apply_vat=True,
                vat_rate=20.0,
                region=region,
                lock_overheads=bool(lock_overheads),
                dev_rate=float(dev_rate),
            )
            st.dataframe(host_df)
            st.download_button("Download CSV", data=export_csv_bytes(host_df), file_name="host_quote.csv", mime="text/csv")

elif workshop_mode == "Production":
    st.subheader("Production settings")
    planned_output_pct = st.slider("Planned Output (%)", min_value=0, max_value=100, value=CFG.GLOBAL_OUTPUT_DEFAULT)
    prod_type = st.radio("Work type", ["Contractual work", "Ad-hoc costs (with deadlines)"], index=0, key="prod_type")

    if prod_type == "Contractual work":
        pricing_mode = st.radio("Price based on", ["Maximum units", "Target units"], index=0, key="pricing_mode")
        pricing_mode = "as-is" if pricing_mode.startswith("Maximum") else "target"

        num_items = st.number_input("Number of items produced?", min_value=1, value=1, step=1, key="num_items_prod")
        items, targets = [], []
        for i in range(int(num_items)):
            with st.expander(f"Item {i+1}", expanded=(i == 0)):
                name = st.text_input(f"Item {i+1} Name", key=f"name_{i}")
                required = st.number_input(f"Prisoners required", min_value=1, value=1, step=1, key=f"req_{i}")
                minutes_per = st.number_input(f"Minutes per unit", min_value=1.0, value=10.0, format="%.2f", key=f"mins_{i}")
                assigned = st.number_input(f"Prisoners assigned", min_value=0, value=1, step=1, key=f"assigned_{i}")
                items.append({"name": name, "required": int(required), "minutes": float(minutes_per), "assigned": int(assigned)})
                if pricing_mode == "target":
                    tgt = st.number_input(f"Target units per week", min_value=0, value=100, step=1, key=f"target_{i}")
                    targets.append(int(tgt))

        results = calculate_production_contractual(
            items, planned_output_pct,
            workshop_hours=float(workshop_hours),
            prisoner_salary=float(prisoner_salary),
            supervisor_salaries=supervisor_salaries,
            effective_pct=float(effective_pct),
            customer_covers_supervisors=bool(customer_covers_supervisors),
            customer_type=customer_type,
            apply_vat=True,
            vat_rate=20.0,
            num_prisoners=int(num_prisoners),
            num_supervisors=int(num_supervisors),
            lock_overheads=bool(lock_overheads),
            region=region,
            dev_rate=float(dev_rate),
            pricing_mode=pricing_mode,
            targets=targets if pricing_mode == "target" else None,
        )
        st.dataframe(pd.DataFrame(results))

# -----------------------------------------------------------------------------
# Reset
# -----------------------------------------------------------------------------
if st.button("Reset Selections", key="reset_app_footer"):
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.experimental_rerun()