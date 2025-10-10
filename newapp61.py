import streamlit as st
import pandas as pd
from datetime import date

from config61 import CFG
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
from utils61 import (
    inject_govuk_css, sidebar_controls, fmt_currency,
    export_csv_bytes, export_html, render_table_html, adjust_table,
    render_comparison_table, build_powerbi_export
)
from production61 import (
    labour_minutes_budget,
    calculate_production_contractual,
    calculate_adhoc,
    build_adhoc_table,
    build_production_comparison
)
import host61

# -------------------------------
# Page setup
# -------------------------------
st.set_page_config(page_title="Cost and Price Calculator", page_icon="💷", layout="centered")
inject_govuk_css()
st.title("Cost and Price Calculator")

# -------------------------------
# Sidebar
# -------------------------------
lock_overheads, instructor_pct, prisoner_output = sidebar_controls(CFG.GLOBAL_OUTPUT_DEFAULT)

# -------------------------------
# Base inputs
# -------------------------------
prisons_sorted = ["Select"] + sorted(PRISON_TO_REGION.keys())
prison_choice = st.selectbox("Prison Name", prisons_sorted, index=0)
region = PRISON_TO_REGION.get(prison_choice, "Select") if prison_choice != "Select" else "Select"

customer_name = st.text_input("Customer Name")
contract_type = st.selectbox("Contract Type", ["Select", "Host", "Production"])

workshop_hours = st.number_input("How many hours is the workshop open per week?", min_value=0.0, format="%.2f")
num_prisoners = st.number_input("How many prisoners employed per week?", min_value=0, step=1)
prisoner_salary = st.number_input("Average prisoner salary per week (£)", min_value=0.0, format="%.2f")

# Instructor inputs
num_supervisors = st.number_input("How many Instructors?", min_value=1, step=1)
customer_covers_supervisors = st.checkbox("Customer provides Instructor(s)?", value=False)

supervisor_salaries = []
if num_supervisors > 0 and region != "Select" and not customer_covers_supervisors:
    titles_for_region = SUPERVISOR_PAY.get(region, [])
    for i in range(int(num_supervisors)):
        options = [t["title"] for t in titles_for_region]
        sel = st.selectbox(f"Instructor {i+1} Title", options, key=f"inst_title_{i}")
        pay = next(t["avg_total"] for t in titles_for_region if t["title"] == sel)
        st.caption(f"{region} — £{pay:,.0f}")
        supervisor_salaries.append(float(pay))

contracts = st.number_input("How many contracts do they oversee in this workshop?", min_value=1, value=1)

# Recommended instructor allocation
if workshop_hours > 0:
    recommended_pct = min(100.0, (workshop_hours / 37.5) * (1 / contracts) * 100.0)
    st.info(f"Recommended Instructor allocation: **{recommended_pct:.1f}%** (based on hours open and contracts)")
else:
    recommended_pct = 100.0

employment_support = st.selectbox(
    "What employment support does the customer offer?",
    ["None", "Employment on release/RoTL", "Post release", "Both"],
)

# -------------------------------
# Validation
# -------------------------------
def validate_inputs():
    errors = []
    if prison_choice == "Select": errors.append("Select prison")
    if region == "Select": errors.append("Region could not be derived from prison selection")
    if not str(customer_name).strip(): errors.append("Enter customer name")
    if contract_type == "Select": errors.append("Select contract type")
    if workshop_hours <= 0: errors.append("Workshop hours must be greater than zero")
    if num_prisoners <= 0: errors.append("Prisoners employed must be greater than zero")
    return errors

# -------------------------------
# HOST
# -------------------------------
if contract_type == "Host":
    if st.button("Generate Host Costs"):
        errs = validate_inputs()
        if errs:
            st.error("Fix errors:\n- " + "\n- ".join(errs))
        else:
            host_df, ctx = host61.generate_host_quote(
                workshop_hours=workshop_hours,
                num_prisoners=num_prisoners,
                prisoner_salary=prisoner_salary,
                num_supervisors=num_supervisors,
                customer_covers_supervisors=customer_covers_supervisors,
                supervisor_salaries=supervisor_salaries,
                region=region,
                contracts=contracts,
                employment_support=employment_support,
                instructor_allocation=instructor_pct,
                lock_overheads=lock_overheads,
            )
            st.session_state["host_df"] = host_df
            st.session_state["host_comp"] = ctx["comparison"]

    if "host_df" in st.session_state:
        df = st.session_state["host_df"]
        df_comp = st.session_state.get("host_comp")

        st.markdown(render_table_html(df), unsafe_allow_html=True)
        st.markdown("---")
        render_comparison_table(df_comp, "Instructor % Comparison (Host)")

        # Downloads
        meta = {"Type": "Host", "Prison": prison_choice, "Customer": customer_name, "Date": date.today()}
        csv_data = build_powerbi_export(meta, df, df_comp)
        c1, c2 = st.columns(2)
        with c1:
            st.download_button("Download CSV (Host + Comparison)", data=csv_data,
                               file_name="host_quote.csv", mime="text/csv")
        with c2:
            st.download_button(
                "Download PDF-ready HTML (Host)",
                data=export_html(df, None, title="Host Quote", comparison_df=df_comp),
                file_name="host_quote.html", mime="text/html"
            )

# -------------------------------
# PRODUCTION
# -------------------------------
if contract_type == "Production":
    st.markdown("---")
    st.subheader("Production settings")

    output_scale = float(prisoner_output) / 100.0
    budget_minutes = labour_minutes_budget(num_prisoners, workshop_hours) * output_scale
    st.info(f"Available Labour minutes per week @ {prisoner_output}% = **{budget_minutes:,.0f} minutes**.")

    prod_mode = st.radio("Do you want contractual or ad-hoc costs?", ["Contractual", "Ad-hoc"], index=0)

    # ----- Contractual -----
    if prod_mode == "Contractual":
        pricing_mode = st.radio("Price based on:", ["Maximum units from capacity", "Target units per week"], index=0)
        pricing_key = "as-is" if pricing_mode.startswith("Maximum") else "target"

        num_items = st.number_input("Number of items produced?", min_value=1, value=1, step=1)
        items = []
        for i in range(num_items):
            with st.expander(f"Item {i+1} details", expanded=(i == 0)):
                name = st.text_input(f"Item {i+1} Name", key=f"name_{i}")
                disp = name or f"Item {i+1}"

                required = st.number_input(
                    f"Prisoners required to make 1 item ({disp})",
                    min_value=1, value=1, key=f"req_{i}"
                )

                mins_or_secs = st.radio(
                    f"Input unit for production time ({disp})",
                    ["Minutes", "Seconds"], key=f"unit_{i}", horizontal=True
                )

                time_value = st.number_input(
                    f"How long to make 1 item ({disp}) ({mins_or_secs.lower()})",
                    min_value=0.01, format="%.2f", key=f"time_{i}"
                )
                minutes_per = time_value / 60.0 if mins_or_secs == "Seconds" else time_value

                assigned = st.number_input(
                    f"How many prisoners work solely on this item ({disp})",
                    min_value=0, max_value=num_prisoners, value=1, step=1, key=f"assigned_{i}"
                )

                current_price = st.number_input(
                    f"Current price per unit (£) ({disp})",
                    min_value=0.0, format="%.2f", key=f"curr_{i}"
                )

                target_units = None
                if pricing_key == "target":
                    target_units = st.number_input(
                        f"Target units per week ({disp})",
                        min_value=0, value=0, step=1, key=f"target_{i}"
                    )

                items.append({
                    "name": disp,
                    "required": required,
                    "minutes": minutes_per,
                    "assigned": assigned,
                    "current_price": current_price,
                    "target": target_units
                })

        if st.button("Generate Production Costs"):
            errs = validate_inputs()
            if errs:
                st.error("Fix errors:\n- " + "\n- ".join(errs))
            else:
                results = calculate_production_contractual(
                    items, prisoner_output,
                    workshop_hours=workshop_hours,
                    prisoner_salary=prisoner_salary,
                    supervisor_salaries=supervisor_salaries,
                    effective_pct=instructor_pct,
                    customer_covers_supervisors=customer_covers_supervisors,
                    region=region,
                    customer_type="Commercial",
                    apply_vat=True, vat_rate=20.0,
                    num_prisoners=num_prisoners,
                    num_supervisors=num_supervisors,
                    dev_rate=0.0,
                    pricing_mode=pricing_key,
                    lock_overheads=lock_overheads,
                    employment_support=employment_support,
                )

                df = pd.DataFrame(results)
                df_display = df.copy()
                for c in df_display.columns:
                    if "£" in c or "Total" in c or "Price" in c:
                        df_display[c] = df_display[c].apply(fmt_currency)
                    if "Uplift" in c:
                        df_display[c] = df_display[c].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "—")
                st.session_state["prod_df"] = df_display
                st.session_state["prod_comp"] = build_production_comparison(supervisor_salaries, region, employment_support, lock_overheads, customer_covers_supervisors)

    # ----- Ad-hoc -----
    if prod_mode == "Ad-hoc":
        num_lines = st.number_input("How many product lines are needed?", min_value=1, value=1)
        lines = []
        for i in range(num_lines):
            with st.expander(f"Product line {i+1}", expanded=(i == 0)):
                item_name = st.text_input("Item name", key=f"adhoc_name_{i}")
                units_requested = st.number_input("Units requested", min_value=1, value=100, key=f"adhoc_units_{i}")
                deadline = st.date_input("Deadline", value=date.today(), key=f"adhoc_deadline_{i}")
                pris_per_item = st.number_input("Prisoners to make one", min_value=1, value=1, key=f"adhoc_pris_{i}")
                mins_or_secs = st.radio("Input unit for production time", ["Minutes", "Seconds"], key=f"adhoc_unit_{i}", horizontal=True)
                time_value = st.number_input("Time to make one item", min_value=0.01, format="%.2f", key=f"adhoc_time_{i}")
                minutes_per_item = time_value / 60.0 if mins_or_secs == "Seconds" else time_value
                current_price = st.number_input("Current price per unit (£)", min_value=0.0, format="%.2f", key=f"adhoc_curr_{i}")
                lines.append({
                    "name": item_name or f"Item {i+1}",
                    "units": units_requested,
                    "deadline": deadline,
                    "pris_per_item": pris_per_item,
                    "mins_per_item": minutes_per_item,
                    "current_price": current_price,
                })

        if st.button("Generate Ad-hoc Costs"):
            errs = validate_inputs()
            if errs:
                st.error("Fix errors:\n- " + "\n- ".join(errs))
            else:
                result = calculate_adhoc(
                    lines, prisoner_output,
                    workshop_hours=workshop_hours,
                    num_prisoners=num_prisoners,
                    prisoner_salary=prisoner_salary,
                    supervisor_salaries=supervisor_salaries,
                    effective_pct=instructor_pct,
                    customer_covers_supervisors=customer_covers_supervisors,
                    region=region,
                    customer_type="Commercial",
                    apply_vat=True, vat_rate=20.0,
                    dev_rate=0.0,
                    today=date.today(),
                    lock_overheads=lock_overheads,
                    employment_support=employment_support,
                )
                df, totals = build_adhoc_table(result)
                st.session_state["prod_df"] = df
                st.session_state["prod_comp"] = build_production_comparison(supervisor_salaries, region, employment_support, lock_overheads, customer_covers_supervisors)

    # ----- Display results -----
    if "prod_df" in st.session_state:
        df = st.session_state["prod_df"]
        df_comp = st.session_state.get("prod_comp")

        st.markdown(render_table_html(df), unsafe_allow_html=True)
        st.markdown("---")
        render_comparison_table(df_comp, "Instructor % Comparison (Production)")

        meta = {"Type": "Production", "Prison": prison_choice, "Customer": customer_name, "Date": date.today()}
        csv_data = build_powerbi_export(meta, df, df_comp)
        c1, c2 = st.columns(2)
        with c1:
            st.download_button("Download CSV (Production + Comparison)", data=csv_data,
                               file_name="production_quote.csv", mime="text/csv")
        with c2:
            st.download_button(
                "Download PDF-ready HTML (Production)",
                data=export_html(None, df, title="Production Quote", comparison_df=df_comp),
                file_name="production_quote.html",
                mime="text/html"
            )