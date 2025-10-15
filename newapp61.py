# newapp61.py
import streamlit as st
import pandas as pd
from datetime import date

from config61 import CFG
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
from utils61 import (
    inject_govuk_css, sidebar_controls, export_csv_bytes_rows,
    export_html, render_table_html, build_header_block
)
from production61 import (
    labour_minutes_budget, calculate_production_contractual,
    calculate_adhoc, build_adhoc_table,
)
import host61

st.set_page_config(page_title="Cost and Price Calculator", page_icon="💷", layout="centered")
inject_govuk_css()
st.title("Cost and Price Calculator")

lock_overheads, instructor_pct_unused, prisoner_output = sidebar_controls(CFG.GLOBAL_OUTPUT_DEFAULT)

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
if num_supervisors > 0 and region != "Select":
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

benefits_yes = st.checkbox("Any additional prison benefits that you feel warrant a further reduction?", value=False)
benefits_desc = st.text_area("Describe the benefits", placeholder="Explain the additional prison benefits…") if benefits_yes else ""

def _uk_date(d: date) -> str: return d.strftime("%d/%m/%Y")

def validate_inputs():
    errs = []
    if prison_choice == "Select": errs.append("Select prison")
    if region == "Select": errs.append("Region could not be derived from prison selection")
    if not str(customer_name).strip(): errs.append("Enter customer name")
    if contract_type == "Select": errs.append("Select contract type")
    if workshop_hours <= 0: errs.append("Workshop hours must be greater than zero")
    if num_prisoners < 0: errs.append("Prisoners employed cannot be negative")
    if not customer_covers_supervisors and num_supervisors > 0 and len(supervisor_salaries) != num_supervisors:
        errs.append("Choose a title for each instructor")
    return errs

if contract_type == "Host":
    if st.button("Generate Host Costs"):
        errs = validate_inputs()
        if errs:
            st.error("Fix errors:\n- " + "\n- ".join(errs))
        else:
            host_df, ctx = host61.generate_host_quote(
                workshop_hours=workshop_hours, num_prisoners=num_prisoners,
                prisoner_salary=prisoner_salary, num_supervisors=num_supervisors,
                customer_covers_supervisors=customer_covers_supervisors, supervisor_salaries=supervisor_salaries,
                region=region, contracts=contracts, employment_support=employment_support,
                lock_overheads=lock_overheads, benefits_yes=benefits_yes,
                benefits_desc=benefits_desc if benefits_yes else None, benefits_discount_pc=10.0,
            )
            st.session_state["host_df"] = host_df
            st.session_state["benefits_desc"] = benefits_desc if benefits_yes else ""

    if "host_df" in st.session_state:
        df = st.session_state["host_df"].copy()
        st.markdown(render_table_html(df), unsafe_allow_html=True)

        header_block = build_header_block(
            uk_date=_uk_date(date.today()), customer_name=customer_name,
            prison_name=prison_choice, region=region,
            benefits_desc=st.session_state.get("benefits_desc", "") or None
        )

        source_df = df.copy()
        rows = [{"Item": r["Item"], "Amount (£)"]: r["Amount (£)"] for _, r in source_df.iterrows()]

        host_csv = export_csv_bytes_rows([{
            "Quote Type": "Host", "Date": _uk_date(date.today()),
            "Prison Name": prison_choice, "Region": region, "Customer Name": customer_name,
            "Contract Type": "Host", "Workshop Hours / week": workshop_hours,
            "Prisoners Employed": num_prisoners, "Prisoner Salary / week": prisoner_salary,
            "Instructors Count": num_supervisors,
            "Customer Provides Instructors": "Yes" if customer_covers_supervisors else "No",
            "Contracts Overseen": contracts, "Employment Support": employment_support,
            **{r["Item"]: r["Amount (£)"] for _, r in source_df.iterrows()}
        }])

        c1, c2 = st.columns(2)
        with c1:
            st.download_button("Download CSV (Host)", data=host_csv, file_name="host_quote.csv", mime="text/csv")
        with c2:
            st.download_button(
                "Download PDF-ready HTML (Host)",
                data=export_html(df, None, title="Host Quote", header_block=header_block,
                                 segregated_df=None, notes=(st.session_state.get("benefits_desc") or None)),
                file_name="host_quote.html", mime="text/html"
            )

# Production section left as before (unchanged calculations/UI you already had)
# If you need me to re-include the full production block here again, say the word and I’ll paste it verbatim.