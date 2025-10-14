import streamlit as st
import pandas as pd
from datetime import date

from config61 import CFG
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
from utils61 import (
    inject_govuk_css, sidebar_controls, fmt_currency,
    export_html, render_table_html, build_header_block,
    export_csv_bytes_rows, export_csv_single_row
)
from production61 import (
    labour_minutes_budget,
    calculate_production_contractual,
    calculate_adhoc,
    build_adhoc_table,
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
_sc = sidebar_controls(CFG.GLOBAL_OUTPUT_DEFAULT)
if isinstance(_sc, tuple):
    prisoner_output = _sc[-1]
else:
    prisoner_output = _sc

# -------------------------------
# Base inputs
# -------------------------------
prisons_sorted = ["Select"] + sorted(PRISON_TO_REGION.keys())
prison_choice = st.selectbox("Prison Name", prisons_sorted, index=0)
region = PRISON_TO_REGION.get(prison_choice, "Select") if prison_choice != "Select" else "Select"
st.session_state["region"] = region

customer_name = st.text_input("Customer Name")
contract_type = st.selectbox("Contract Type", ["Select", "Host", "Production"])

workshop_hours = st.number_input("How many hours is the workshop open per week?", min_value=0.0, format="%.2f")
num_prisoners = st.number_input("How many prisoners employed per week?", min_value=0, step=1)
prisoner_salary = st.number_input("Average prisoner salary per week (£)", min_value=0.0, format="%.2f")

num_supervisors = st.number_input("How many instructors are required at full contract capacity.", min_value=1, step=1)
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
employment_support = st.selectbox(
    "What employment support does the customer offer?",
    ["None", "Employment on release/RoTL", "Post release", "Both"],
)

benefits_yes = st.checkbox("Any additional prison benefits that you feel warrant a further reduction?")
benefits_text = ""
if benefits_yes:
    benefits_text = st.text_area("Describe the benefits")

# -------------------------------
# Helpers
# -------------------------------
def _uk_date(d: date) -> str:
    return d.strftime("%d/%m/%Y")

def _dev_rate_from_support(s: str) -> float:
    if s == "None":
        return 0.20
    if s in ("Employment on release/RoTL", "Post release"):
        return 0.10
    return 0.00

def _recommended_pct(hours: float, contracts_count: int) -> float:
    try:
        if hours > 0 and contracts_count > 0:
            return min(100.0, round((hours / 37.5) * (1.0 / contracts_count) * 100.0, 1))
    except Exception:
        pass
    return 0.0

effective_instructor_pct = _recommended_pct(workshop_hours, int(contracts))

def validate_inputs():
    errors = []
    if prison_choice == "Select": errors.append("Select prison")
    if region == "Select": errors.append("Region could not be derived from prison selection")
    if not str(customer_name).strip(): errors.append("Enter customer name")
    if contract_type == "Select": errors.append("Select contract type")
    if workshop_hours <= 0: errors.append("Workshop hours must be greater than zero")
    if num_prisoners < 0: errors.append("Prisoners employed cannot be negative")
    if not customer_covers_supervisors and num_supervisors > 0 and len(supervisor_salaries) != num_supervisors:
        errors.append("Choose a title for each instructor")
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
                instructor_allocation=effective_instructor_pct,
                lock_overheads=False,
            )

            if "Item" in host_df.columns:
                host_df["Item"] = host_df["Item"].astype(str).str.replace("Overheads (61%)", "Overheads", regex=False)

            if benefits_yes:
                for i, row in host_df.iterrows():
                    item = str(row["Item"]).lower()
                    if "instructor salary" in item or "overheads" in item:
                        host_df.at[i, "Amount (£)"] = round(row["Amount (£)"] * 0.9, 2)

            dev_rate = _dev_rate_from_support(employment_support)
            dev_charge = None
            for i, row in host_df.iterrows():
                if "Development charge" in str(row["Item"]):
                    dev_charge = float(row["Amount (£)"])
                    if dev_charge > 0:
                        discount = round(dev_charge * dev_rate, 2)
                        host_df.at[i, "Amount (£)"] = dev_charge - discount
                        host_df.loc[len(host_df)] = {"Item": "Development Discount", "Amount (£)": -discount}

            if benefits_yes:
                red_amount = round(sum(float(r["Amount (£)"]) for _, r in host_df.iterrows() if "instructor salary" in str(r["Item"]).lower() or "overheads" in str(r["Item"]).lower()) * 0.1, 2)
                host_df.loc[len(host_df)] = {"Item": "Additional Benefit Discount (10%)", "Amount (£)": -red_amount}

            subtotal = host_df["Amount (£)"].sum()
            vat = round(subtotal * 0.2, 2)
            grand_total = round(subtotal + vat, 2)
            host_df.loc[len(host_df)] = {"Item": "Grand Total (ex VAT)", "Amount (£)": subtotal}
            host_df.loc[len(host_df)] = {"Item": "Grand Total (+ VAT)", "Amount (£)": grand_total}

            df_display = host_df.copy()
            df_display["Item"] = df_display["Item"].apply(
                lambda x: f"<span style='color:red'>{x}</span>" if "discount" in str(x).lower() else x
            )

            st.markdown(render_table_html(df_display), unsafe_allow_html=True)
            st.session_state["host_df"] = host_df

            header_block = build_header_block(
                uk_date=_uk_date(date.today()),
                customer_name=customer_name,
                prison_name=prison_choice,
                region=region
            )

            host_csv = export_csv_bytes_rows([{
                "Quote Type": "Host",
                "Date": _uk_date(date.today()),
                "Prison Name": prison_choice,
                "Region": region,
                "Customer Name": customer_name,
                "Contract Type": "Host",
                "Workshop Hours / week": workshop_hours,
                "Prisoners Employed": num_prisoners,
                "Prisoner Salary / week": prisoner_salary,
                "Instructors Count": num_supervisors,
                "Customer Provides Instructors": "Yes" if customer_covers_supervisors else "No",
                "Instructor Allocation (%)": effective_instructor_pct,
                "Employment Support": employment_support,
                "Contracts Overseen": contracts,
                "Additional Prison Benefits?": "Yes" if benefits_yes else "No",
                "Benefits Notes": benefits_text,
                "VAT Rate (%)": 20.0,
                "Host: Grand Total (ex VAT)": subtotal,
                "Host: Grand Total (+ VAT)": grand_total
            }])

            c1, c2 = st.columns(2)
            with c1:
                st.download_button("Download CSV (Host)", data=host_csv, file_name="host_quote.csv", mime="text/csv")
            with c2:
                st.download_button(
                    "Download PDF-ready HTML (Host)",
                    data=export_html(host_df, None, title="Host Quote", header_block=header_block),
                    file_name="host_quote.html",
                    mime="text/html"
                )

# -------------------------------
# PRODUCTION
# -------------------------------
if contract_type == "Production":
    st.markdown("---")
    st.subheader("Production settings")

    output_scale = float(prisoner_output) / 100.0
    budget_minutes_raw = labour_minutes_budget(int(num_prisoners), float(workshop_hours))
    budget_minutes_planned = budget_minutes_raw * output_scale
    st.info(f"Available Labour minutes per week @ {prisoner_output}% = **{budget_minutes_planned:,.0f} minutes**.")

    prod_mode = st.radio("Do you want contractual or ad-hoc costs?", ["Contractual", "Ad-hoc"], index=0)
    if prod_mode == "Contractual":
        pricing_mode = st.radio("Price based on:", ["Maximum units from capacity", "Target units per week"], index=0)
        pricing_mode_key = "as-is" if pricing_mode.startswith("Maximum") else "target"

        num_items = st.number_input("Number of items produced?", min_value=1, value=1, step=1)
        items, targets = [], []

        for i in range(int(num_items)):
            with st.expander(f"Item {i+1} details", expanded=(i == 0)):
                name = st.text_input(f"Item {i+1} Name", key=f"name_{i}")
                required = st.number_input(f"Prisoners required to make 1 item ({name or f'Item {i+1}'})", min_value=1, value=1)
                unit_choice = st.radio(f"Input unit for production time ({name or f'Item {i+1}'})", ["Minutes", "Seconds"], horizontal=True)
                minutes_per = st.number_input(
                    f"How long to make 1 item ({name or f'Item {i+1}'}) ({unit_choice.lower()})",
                    min_value=0.0, value=10.0, format="%.4f"
                ) / (60.0 if unit_choice == "Seconds" else 1.0)
                assigned = st.number_input(f"How many prisoners work solely on this item ({name or f'Item {i+1}'})", min_value=0, value=1)
                cap_100 = (assigned * workshop_hours * 60.0) / (minutes_per * required) if minutes_per > 0 else 0.0
                st.caption(f"Capacity @100%: {cap_100:.0f} units/week")

                if pricing_mode_key == "target":
                    tgt = st.number_input(f"Target units per week ({name or f'Item {i+1}'})", min_value=0, value=int(round(cap_100)))
                    targets.append(tgt)
                items.append({"name": name, "required": required, "minutes": minutes_per, "assigned": assigned})

        if st.button("Generate Production Costs"):
            results = calculate_production_contractual(
                items, int(prisoner_output),
                workshop_hours=float(workshop_hours),
                prisoner_salary=float(prisoner_salary),
                supervisor_salaries=supervisor_salaries,
                effective_pct=float(effective_instructor_pct),
                customer_covers_supervisors=customer_covers_supervisors,
                region=region,
                customer_type="Commercial",
                apply_vat=True, vat_rate=20.0,
                num_prisoners=int(num_prisoners),
                num_supervisors=int(num_supervisors),
                dev_rate=_dev_rate_from_support(employment_support),
                pricing_mode=pricing_mode_key,
                targets=targets if pricing_mode_key == "target" else None,
                lock_overheads=False,
                employment_support=employment_support,
            )

            df = pd.DataFrame(results)
            st.markdown(render_table_html(df), unsafe_allow_html=True)

            header_block = build_header_block(
                uk_date=_uk_date(date.today()),
                customer_name=customer_name,
                prison_name=prison_choice,
                region=region
            )

            csv_bytes = export_csv_single_row({
                "Quote Type": "Production",
                "Date": _uk_date(date.today()),
                "Prison Name": prison_choice,
                "Region": region,
                "Customer Name": customer_name,
                "Contract Type": "Production",
                "Workshop Hours / week": workshop_hours,
                "Prisoners Employed": num_prisoners,
                "Prisoner Salary / week": prisoner_salary,
                "Instructors Count": num_supervisors,
                "Employment Support": employment_support,
                "Contracts Overseen": contracts,
                "Additional Prison Benefits?": "Yes" if benefits_yes else "No",
                "Benefits Notes": benefits_text,
                "VAT Rate (%)": 20.0
            }, df, None)

            st.download_button("Download CSV (Production)", data=csv_bytes, file_name="production_quote.csv", mime="text/csv")
            st.download_button(
                "Download PDF-ready HTML (Production)",
                data=export_html(df, None, title="Production Quote", header_block=header_block),
                file_name="production_quote.html",
                mime="text/html"
            )