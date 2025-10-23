import streamlit as st
import pandas as pd
from datetime import date

from config61 import CFG
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
from utils61 import (
    inject_govuk_css, sidebar_controls, fmt_currency,
    export_csv_bytes, export_html, render_table_html, adjust_table,
    export_csv_single_row, export_csv_bytes_rows, build_header_block
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
prisoner_output = sidebar_controls(CFG.GLOBAL_OUTPUT_DEFAULT)

# -------------------------------
# Base Inputs
# -------------------------------
prisons_sorted = ["Select"] + sorted(PRISON_TO_REGION.keys())
prison_choice = st.selectbox("Prison Name", prisons_sorted, index=0, key="prison_choice")
region = PRISON_TO_REGION.get(prison_choice, "Select") if prison_choice != "Select" else "Select"
st.session_state["region"] = region

customer_name = st.text_input("Customer Name", key="customer_name")
contract_type = st.selectbox("Contract Type", ["Select", "Host", "Production"], key="contract_type")

workshop_hours = st.number_input("How many hours is the workshop open per week?", min_value=0.0, format="%.2f")
num_prisoners = st.number_input("How many prisoners employed per week?", min_value=0, step=1)
prisoner_salary = st.number_input("Average prisoner salary per week (£)", min_value=0.0, format="%.2f")

# Instructor inputs
num_supervisors = st.number_input(
    "How many instructors required when the contract is at full capacity.",
    min_value=1, step=1
)
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

# Contracts (hidden if customer provides instructors)
if not customer_covers_supervisors:
    contracts = st.number_input("How many contracts do they oversee in this workshop?", min_value=1, value=1)
else:
    contracts = 1

# Employment support (updated wording)
employment_support = st.selectbox(
    "What employment support does the customer offer?",
    ["None", "Employment on release/RoTL", "Pre-release support", "Both"],
)

# Additional benefits
additional_benefits = st.checkbox("Any additional prison benefits that you feel warrant a further reduction?", value=False)
benefits_desc = ""
if additional_benefits:
    benefits_desc = st.text_area("Please describe the additional benefits", value="")

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
    if num_prisoners < 0: errors.append("Prisoners employed cannot be negative")
    if not customer_covers_supervisors and num_supervisors > 0 and len(supervisor_salaries) != num_supervisors:
        errors.append("Choose a title for each instructor")
    return errors

def _dev_rate_from_support(s: str) -> float:
    if s == "None":
        return 0.20
    if s in ("Employment on release/RoTL", "Pre-release support"):
        return 0.10
    return 0.00

def _uk_date(d: date) -> str:
    return d.strftime("%d/%m/%Y")

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
                additional_benefits=additional_benefits,
            )
            st.session_state["host_df"] = host_df

    if "host_df" in st.session_state:
        df = st.session_state["host_df"].copy()
        if customer_covers_supervisors and "Item" in df.columns:
            df = df[~df["Item"].astype(str).str.contains("Instructor", na=False)]

        # Highlight reductions
        if "Item" in df.columns:
            df_display = df.copy()
            df_display["Item"] = df_display["Item"].apply(
                lambda x: f"<span style='color:red'>{x}</span>"
                if any(w in str(x).lower() for w in ["discount", "reduction"])
                else x
            )
            st.markdown(render_table_html(df_display), unsafe_allow_html=True)
        else:
            st.markdown(render_table_html(df), unsafe_allow_html=True)

        header_block = build_header_block(
            uk_date=_uk_date(date.today()),
            customer_name=customer_name,
            prison_name=prison_choice,
            region=region
        )

        source_df = st.session_state["host_df"].copy()

        def _grab_amount(needle: str) -> float:
            try:
                m = source_df["Item"].astype(str).str.contains(needle, case=False, na=False)
                if m.any():
                    raw = str(source_df.loc[m, "Amount (£)"].iloc[-1]).replace("£", "").replace(",", "")
                    return float(raw)
            except Exception:
                pass
            return 0.0

        amounts = {
            "Host: Prisoner wages (£/month)": _grab_amount("Prisoner Wages"),
            "Host: Instructor Cost (£/month)": _grab_amount("Instructor"),
            "Host: Overheads (£/month)": _grab_amount("Overheads"),
            "Host: Development charge (£/month)": _grab_amount("Development Charge (before"),
            "Host: Development Reduction (£/month)": _grab_amount("discount"),
            "Host: Revised development charge (£/month)": _grab_amount("Revised development"),
            "Host: Additional benefit discount (£/month)": _grab_amount("Additional benefit"),
            "Host: Grand Total (£/month)": _grab_amount("Grand Total (£/month)"),
            "Host: VAT (£/month)": _grab_amount("VAT"),
            "Host: Grand Total + VAT (£/month)": _grab_amount("Grand Total + VAT"),
        }

        common = {
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
            "Employment Support": employment_support,
            "Contracts Overseen": contracts,
            "VAT Rate (%)": 20.0,
            "Additional Benefits": "Yes" if additional_benefits else "No",
            "Additional Benefits (desc)": benefits_desc,
        }

        host_csv = export_csv_bytes_rows([{**common, **amounts}])
        c1, c2 = st.columns(2)
        with c1:
            st.download_button("Download CSV (Host)", data=host_csv, file_name="host_quote.csv", mime="text/csv")
        with c2:
            st.download_button(
                "Download PDF-ready HTML (Host)",
                data=export_html(df, None, title="Host Quote", header_block=header_block, segregated_df=None),
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
                disp = name or f"Item {i+1}"
                required = st.number_input(f"Prisoners required to make 1 item ({disp})", min_value=1, value=1)
                unit_choice = st.radio(f"Input unit for production time ({disp})", ["Minutes", "Seconds"], horizontal=True)
                if unit_choice == "Minutes":
                    minutes_per = st.number_input(f"How long to make 1 item ({disp}) (minutes)", min_value=0.0, value=10.0)
                else:
                    seconds_val = st.number_input(f"How long to make 1 item ({disp}) (seconds)", min_value=0.0, value=30.0)
                    minutes_per = seconds_val / 60.0

                assigned = st.number_input(f"How many prisoners work solely on this item ({disp})", min_value=0, value=1)
                cap_100 = (assigned * workshop_hours * 60.0) / (minutes_per * required) if minutes_per > 0 else 0.0
                cap_planned = cap_100 * output_scale
                st.caption(f"{disp} capacity @ 100%: {cap_100:.0f} units/week · @ {prisoner_output}%: {cap_planned:.0f}")

                if pricing_mode_key == "target":
                    tgt_default = int(round(cap_planned)) if cap_planned > 0 else 0
                    tgt = st.number_input(f"Target units per week ({disp})", min_value=0, value=tgt_default)
                    targets.append(int(tgt))
                items.append({"name": name, "required": required, "minutes": minutes_per, "assigned": assigned})

        if st.button("Generate Production Costs"):
            errs = validate_inputs()
            if errs:
                st.error("Fix errors:\n- " + "\n- ".join(errs))
            else:
                results = calculate_production_contractual(
                    items, int(prisoner_output),
                    workshop_hours=float(workshop_hours),
                    prisoner_salary=float(prisoner_salary),
                    supervisor_salaries=supervisor_salaries,
                    customer_covers_supervisors=False,
                    region=region,
                    customer_type="Commercial",
                    apply_vat=True, vat_rate=20.0,
                    num_prisoners=int(num_prisoners),
                    num_supervisors=int(num_supervisors),
                    pricing_mode=pricing_mode_key,
                    targets=targets if pricing_mode_key == "target" else None,
                    employment_support=employment_support,
                    contracts=int(contracts),
                )
                df = pd.DataFrame(results)
                st.markdown(render_table_html(df), unsafe_allow_html=True)
                st.session_state["prod_df"] = df

    # === Downloads ===
    if "prod_df" in st.session_state:
        df = st.session_state["prod_df"]
        header_block = build_header_block(
            uk_date=_uk_date(date.today()),
            customer_name=customer_name,
            prison_name=prison_choice,
            region=region
        )
        c1, c2 = st.columns(2)
        with c1:
            csv_bytes = export_csv_single_row({}, df, None)
            st.download_button("Download CSV (Production)", data=csv_bytes, file_name="production_quote.csv", mime="text/csv")
        with c2:
            st.download_button("Download PDF-ready HTML (Production)",
                data=export_html(None, df, title="Production Quote", header_block=header_block, segregated_df=None),
                file_name="production_quote.html", mime="text/html")