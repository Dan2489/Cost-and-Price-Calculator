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
lock_overheads = False  # permanently disabled

# -------------------------------
# Base inputs
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

# Auto allocation (no slider)
recommended_pct = 0.0
try:
    if workshop_hours > 0 and contracts > 0:
        recommended_pct = min(100.0, round((workshop_hours / 37.5) * (1.0 / contracts) * 100.0, 1))
except Exception:
    recommended_pct = 0.0

employment_support = st.selectbox(
    "What employment support does the customer offer?",
    ["None", "Employment on release/RoTL", "Post release", "Both"],
)

# Additional Prison Benefits
has_benefits = st.checkbox("Any Additional Prison Benefits?", value=False)
benefits_text = ""
if has_benefits:
    benefits_text = st.text_area("Describe the benefits", placeholder="Explain the additional benefits here")
instructor_discount = 0.10 if has_benefits else 0.0  # 10% off instructor + 61% overhead

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

# -------------------------------
# Helpers
# -------------------------------
def _dev_rate_from_support(s: str) -> float:
    if s == "None":
        return 0.20
    if s in ("Employment on release/RoTL", "Post release"):
        return 0.10
    return 0.00

def _uk_date(d: date) -> str:
    return d.strftime("%d/%m/%Y")

# -------------------------------
# Apply 10% benefit discount (in place)
# -------------------------------
def _apply_benefits_discount_host(df_in: pd.DataFrame, discount: float, original_df: pd.DataFrame) -> pd.DataFrame:
    """Reduces instructor & overhead rows by (1 - discount) and adds explicit reduction rows."""
    if df_in is None or df_in.empty or discount <= 0:
        return df_in

    df = df_in.copy()

    def _num(x):
        try:
            return float(str(x).replace("£", "").replace(",", ""))
        except:
            return 0.0

    def _orig(needle):
        m = original_df["Item"].astype(str).str.contains(needle, case=False, na=False, regex=False)
        return _num(original_df.loc[m, "Amount (£)"].iloc[0]) if m.any() else 0.0

    inst_orig = _orig("Instructor Salary")
    over_orig = _orig("Overheads (61%")
    inst_red = inst_orig * discount
    over_red = over_orig * discount

    for needle in ["Instructor Salary", "Overheads (61%"]:
        m = df["Item"].astype(str).str.contains(needle, case=False, na=False, regex=False)
        if m.any():
            idx = df.index[m][0]
            base = inst_orig if "Instructor" in needle else over_orig
            new_val = base * (1 - discount)
            df.at[idx, "Amount (£)"] = new_val

            red_label = "Benefits Reduction – Instructor (10%)" if "Instructor" in needle else "Benefits Reduction – Overheads (10%)"
            new_row = pd.DataFrame([{"Item": red_label, "Amount (£)": -(inst_red if "Instructor" in needle else over_red)}])
            df = pd.concat([df.iloc[:idx+1], new_row, df.iloc[idx+1:]], ignore_index=True)

    return df

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
                instructor_allocation=recommended_pct,
                lock_overheads=False,
            )
            st.session_state["host_df"] = host_df

    if "host_df" in st.session_state:
        source_df = st.session_state["host_df"].copy()
        df_work = source_df.copy()
        if has_benefits:
            df_work = _apply_benefits_discount_host(df_work, instructor_discount, original_df=source_df)

        def grab(df, needle):
            try:
                m = df["Item"].astype(str).str.contains(needle, case=False, na=False, regex=False)
                if m.any():
                    raw = str(df.loc[m, "Amount (£)"].iloc[-1]).replace("£", "").replace(",", "")
                    return float(raw)
            except Exception:
                pass
            return 0.0

        # Base values
        wages = grab(df_work, "Prisoner Wages")
        inst = grab(df_work, "Instructor Salary")
        overheads = grab(df_work, "Overheads (61%")
        dev_charge = grab(df_work, "Development charge (before") or grab(df_work, "Development charge")
        dev_disc = grab(df_work, "Development Reduction")
        dev_revised = dev_charge - dev_disc
        ben_red_inst = grab(df_work, "Benefits Reduction – Instructor")
        ben_red_over = grab(df_work, "Benefits Reduction – Overheads")
        ben_red_total = ben_red_inst + ben_red_over

        subtotal_ex_vat = wages + inst + overheads + dev_revised + ben_red_total
        vat = subtotal_ex_vat * 0.20
        grand_ex_vat = subtotal_ex_vat
        grand_inc_vat = subtotal_ex_vat + vat

        # Ordered display
        ordered_rows = [
            {"Item": "Prisoner Wages", "Amount (£)": wages},
            {"Item": "Instructor Salary", "Amount (£)": inst},
            {"Item": "Overheads (61%)", "Amount (£)": overheads},
            {"Item": "Development Charge", "Amount (£)": dev_charge},
            {"Item": "Development Discount (if any)", "Amount (£)": -abs(dev_disc)},
            {"Item": "Revised Development Charge", "Amount (£)": dev_revised},
            {"Item": "Additional Benefit Discount (10%)", "Amount (£)": ben_red_total},
            {"Item": "Grand Total (ex VAT)", "Amount (£)": grand_ex_vat},
            {"Item": "Grand Total + VAT", "Amount (£)": grand_inc_vat},
        ]
        df_display = pd.DataFrame(ordered_rows)

        # Colour discounts red
        df_html = df_display.copy()
        df_html["Item"] = df_html["Item"].apply(lambda x: f"<span style='color:red'>{x}</span>" if "Discount" in x else x)
        st.markdown(render_table_html(df_html), unsafe_allow_html=True)

        # ===== Downloads =====
        header_block = build_header_block(
            uk_date=_uk_date(date.today()),
            customer_name=customer_name,
            prison_name=prison_choice,
            region=region
        )

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
            "Auto Instructor Allocation (%)": recommended_pct,
            "Employment Support": employment_support,
            "Contracts Overseen": contracts,
            "Additional Prison Benefits?": "Yes" if has_benefits else "No",
            "Benefits Description": benefits_text,
            "Applied Instructor Discount (%)": 10.0 if has_benefits else 0.0,
            "VAT Rate (%)": 20.0,
        }

        amounts = {
            "Host: Prisoner wages (£/month)": wages,
            "Host: Instructor Salary (£/month)": inst,
            "Host: Overheads 61% (£/month)": overheads,
            "Host: Development charge (£/month)": dev_charge,
            "Host: Development Reduction (£/month)": -abs(dev_disc),
            "Host: Development Revised (£/month)": dev_revised,
            "Host: Additional Benefits Discount (£/month)": ben_red_total,
            "Host: Grand Total (ex VAT £/month)": grand_ex_vat,
            "Host: Grand Total + VAT (£/month)": grand_inc_vat,
        }

        host_csv = export_csv_bytes_rows([{**common, **amounts}])

        c1, c2 = st.columns(2)
        with c1:
            st.download_button("Download CSV (Host)", data=host_csv, file_name="host_quote.csv", mime="text/csv")
        with c2:
            st.download_button(
                "Download PDF-ready HTML (Host)",
                data=export_html(df_display, None, title="Host Quote", header_block=header_block, segregated_df=None),
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
        # ... [Keep your existing Production logic unchanged]
        st.write("Production section unchanged from your current build.")