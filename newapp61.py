import streamlit as st
import pandas as pd

from config61 import CFG
from host61 import generate_host_quote
from production61 import calculate_production_contractual
from utils61 import (
    inject_govuk_css,
    PRISON_TO_REGION,
    SUPERVISOR_PAY,
    draw_sidebar,
    render_host_df_to_html,
    render_generic_df_to_html,
    export_csv_bytes,
    export_html,
    validate_inputs,
    currency,
)

# ------------------------------------------------------
# Page setup
# ------------------------------------------------------
st.set_page_config(page_title="Cost and Price Calculator", layout="wide")
inject_govuk_css()

st.markdown(
    '<div class="app-header"><h1 class="govuk-heading-l">Cost and Price Calculator</h1></div>',
    unsafe_allow_html=True,
)

# Sidebar
draw_sidebar()
effective_pct = st.sidebar.slider("Adjust instructor % allocation", min_value=0, max_value=100, value=100)

# ------------------------------------------------------
# Base inputs
# ------------------------------------------------------
prisons_sorted = ["Select"] + sorted(PRISON_TO_REGION.keys())
prison_choice = st.selectbox("Prison Name", prisons_sorted, index=0, key="prison_choice")
region = PRISON_TO_REGION.get(prison_choice, "Select") if prison_choice != "Select" else "Select"
st.session_state["region"] = region

customer_type = st.selectbox("I want to quote for", ["Select", "Commercial", "Public"], key="customer_type")
customer_name = st.text_input("Customer Name", key="customer_name")
workshop_mode = st.selectbox("Contract type?", ["Select", "Host", "Production"], key="workshop_mode")

workshop_hours = st.number_input("How many hours per week is the workshop open?", min_value=0.0, format="%.2f", key="workshop_hours")
num_prisoners = st.number_input("How many prisoners employed?", min_value=0, step=1, key="num_prisoners")
prisoner_salary = st.number_input("Prisoner salary per week (£)", min_value=0.0, format="%.2f", key="prisoner_salary")
num_supervisors = st.number_input("How many instructors?", min_value=0, step=1, key="num_supervisors")
customer_covers_supervisors = st.checkbox("Customer provides instructor(s)?", key="customer_covers_supervisors")

supervisor_salaries = []
if not customer_covers_supervisors and region != "Select":
    for i in range(int(num_supervisors)):
        options = [t["title"] for t in SUPERVISOR_PAY.get(region, [])]
        if options:
            sel = st.selectbox(f"Instructor {i+1} title", options, key=f"inst_title_{i}")
            pay = next(t["avg_total"] for t in SUPERVISOR_PAY[region] if t["title"] == sel)
            st.caption(f"Avg Total for {region}: **£{pay:,.0f}** per year")
            supervisor_salaries.append(float(pay))

# ------------------------------------------------------
# Run Host
# ------------------------------------------------------
if workshop_mode == "Host" and st.button("Generate Host Costs"):
    errors = validate_inputs(prison_choice, region, customer_type, customer_name, workshop_mode,
                             workshop_hours, prisoner_salary, num_prisoners,
                             num_supervisors, customer_covers_supervisors, supervisor_salaries)
    if errors:
        st.error("Fix errors:\n- " + "\n- ".join(errors))
    else:
        host_df, _ = generate_host_quote(
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
        )
        st.markdown(render_host_df_to_html(host_df), unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.download_button("Download CSV (Host)", data=export_csv_bytes(host_df), file_name="host_quote.csv", mime="text/csv")
        with c2:
            st.download_button(
                "Download PDF-ready HTML (Host)",
                data=export_html(host_df, None, title="Host Quote"),
                file_name="host_quote.html", mime="text/html"
            )

# ------------------------------------------------------
# Run Production
# ------------------------------------------------------
if workshop_mode == "Production" and st.button("Generate Production Costs"):
    errors = validate_inputs(prison_choice, region, customer_type, customer_name, workshop_mode,
                             workshop_hours, prisoner_salary, num_prisoners,
                             num_supervisors, customer_covers_supervisors, supervisor_salaries)
    if errors:
        st.error("Fix errors:\n- " + "\n- ".join(errors))
    else:
        items = []
        num_items = st.number_input("Number of items produced?", min_value=1, value=1, step=1, key="num_items_prod")
        for i in range(int(num_items)):
            with st.expander(f"Item {i+1} details", expanded=(i == 0)):
                name = st.text_input(f"Item {i+1} Name", key=f"name_{i}")
                required = st.number_input(f"Prisoners required to make 1 item", min_value=1, value=1, step=1, key=f"req_{i}")
                minutes_per = st.number_input(f"Minutes to make 1 item", min_value=1.0, value=10.0, format="%.2f", key=f"mins_{i}")
                assigned = st.number_input(f"How many prisoners work solely on this item", min_value=0, max_value=num_prisoners, value=0, step=1, key=f"assigned_{i}")
                items.append({"name": name, "required": int(required), "minutes": float(minutes_per), "assigned": int(assigned)})

        results = calculate_production_contractual(
            items, 100,
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
            dev_rate=0.0,
            overheads_weekly=(0.61 * (sum(supervisor_salaries) / 52.0)) if not customer_covers_supervisors else (0.61 * (supervisor_salaries[0] / 52.0) if supervisor_salaries else 0.0),
        )

        prod_df = pd.DataFrame(results["per_item"])
        st.markdown(render_generic_df_to_html(prod_df), unsafe_allow_html=True)
        st.markdown(f"**Grand Monthly Total: {currency(results['grand_monthly_total'])}**")
        d1, d2 = st.columns(2)
        with d1:
            st.download_button("Download CSV (Production)", data=export_csv_bytes(prod_df), file_name="production_quote.csv", mime="text/csv")
        with d2:
            st.download_button(
                "Download PDF-ready HTML (Production)",
                data=export_html(None, prod_df, title="Production Quote"),
                file_name="production_quote.html", mime="text/html"
            )