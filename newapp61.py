import streamlit as st
import pandas as pd

from config61 import CFG
from host61 import generate_host_quote
from production61 import calculate_production_contractual
from utils61 import inject_govuk_css, PRISON_TO_REGION, SUPERVISOR_PAY, draw_sidebar

# ------------------------------------------------------
# App setup
# ------------------------------------------------------
st.set_page_config(page_title="Cost and Price Calculator (Instructor Cost Model)", layout="wide")
inject_govuk_css()

st.markdown(
    '<div class="app-header"><h1 class="govuk-heading-l">Cost and Price Calculator (Instructor Cost Model)</h1></div>',
    unsafe_allow_html=True,
)

# Sidebar
draw_sidebar()

# ------------------------------------------------------
# Inputs
# ------------------------------------------------------
prison_name = st.selectbox("Prison Name", ["Select"] + sorted(PRISON_TO_REGION.keys()))
customer_name = st.text_input("Customer Name")
contract_type = st.selectbox("Contract type?", ["Select", "Commercial", "Public"])

workshop_hours = st.number_input("How many hours per week is the workshop open?", min_value=0.0, step=0.25)
num_prisoners = st.number_input("How many prisoners employed?", min_value=0, step=1)
prisoner_salary = st.number_input("Prisoner salary per week (£)", min_value=0.0, step=1.0)

num_instructors = st.number_input("How many instructors?", min_value=0, step=1)
customer_covers_instructors = st.checkbox("Customer provides instructor(s)?")

effective_pct = st.slider("Adjust instructor % allocation", min_value=0, max_value=100, value=100)

apply_vat = True
vat_rate = 20.0
dev_rate = 0.0

# ------------------------------------------------------
# Logic
# ------------------------------------------------------
def get_instructor_and_overheads(region: str, num_instructors: int, pct: float, customer_covers: bool):
    """
    Returns (instructor_cost, overheads_cost) depending on whether the customer
    provides the instructor(s).
    """
    if customer_covers:
        # Shadow cost: Band 3 only (salary not shown, only used for overheads)
        band3 = next((s for s in SUPERVISOR_PAY[region] if "Band 3" in s["title"]), None)
        if not band3:
            raise ValueError(f"No Band 3 salary found for region {region}")
        shadow_salary = band3["avg_total"]
        instructor_cost = 0.0
        overheads = 0.61 * shadow_salary
    else:
        # Real instructor salary, adjusted by allocation %
        total_salary = 0.0
        for region_pay in SUPERVISOR_PAY[region]:
            if "Band 3" in region_pay["title"] or "Band 4" in region_pay["title"]:
                # For simplicity, take the first selected type from sidebar selection later
                pass
        # Here, assume user always selects Band from region list in real app
        # For now just pick Band 3
        band3 = next((s for s in SUPERVISOR_PAY[region] if "Band 3" in s["title"]), None)
        if not band3:
            raise ValueError(f"No Band 3 salary found for region {region}")
        adj_salary = (band3["avg_total"] * (pct / 100.0)) * num_instructors
        instructor_cost = adj_salary
        overheads = 0.61 * adj_salary
    return instructor_cost, overheads


if st.button("Generate Costs"):
    if prison_name == "Select" or contract_type == "Select":
        st.error("Please select a valid prison and contract type.")
    else:
        region = PRISON_TO_REGION[prison_name]

        instructor_cost, overheads = get_instructor_and_overheads(
            region, num_instructors, effective_pct, customer_covers_instructors
        )

        prisoner_monthly = num_prisoners * prisoner_salary * (52.0 / 12.0)
        instructor_monthly = instructor_cost / 12.0
        overheads_monthly = overheads / 12.0

        subtotal = prisoner_monthly + instructor_monthly + overheads_monthly
        vat_amount = subtotal * (vat_rate / 100.0)
        grand_total = subtotal + vat_amount

        breakdown = [
            ("Prisoner wages", prisoner_monthly),
        ]
        if instructor_cost > 0:
            breakdown.append(("Instructors", instructor_monthly))
        breakdown.append(("Overheads (61%)", overheads_monthly))

        breakdown += [
            ("Subtotal", subtotal),
            (f"VAT ({vat_rate:.1f}%)", vat_amount),
            ("Grand Total (£/month)", grand_total),
        ]

        df = pd.DataFrame(breakdown, columns=["Item", "Amount (£)"])
        st.subheader("Monthly Breakdown")
        st.table(df)