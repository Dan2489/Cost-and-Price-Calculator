import streamlit as st
import pandas as pd

from config61 import CFG
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
import host61
import production61
from utils61 import (
    inject_govuk_css,
    sidebar_controls,
    fmt_currency,
    export_csv_bytes,
    export_html,
    render_table_html,
)

# -------------------------------
# Page config + global CSS
# -------------------------------
st.set_page_config(page_title="Cost and Price Calculator", page_icon="💷", layout="centered")
inject_govuk_css()

st.title("Cost and Price Calculator")

# -------------------------------
# Sidebar (unchanged baseline)
# -------------------------------
lock_overheads, instructor_pct, prisoner_output = sidebar_controls(CFG.GLOBAL_OUTPUT_DEFAULT)

# -------------------------------
# Base inputs (unchanged baseline)
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

num_supervisors = st.number_input("How many instructors?", min_value=0, step=1)

# Dynamic instructor titles (unchanged behaviour)
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

# -------------------------------
# Validation (unchanged baseline)
# -------------------------------
def validate_inputs():
    errors = []
    if prison_choice == "Select": errors.append("Select prison")
    if region == "Select": errors.append("Region could not be derived from prison selection")
    if not str(customer_name).strip(): errors.append("Enter customer name")
    if contract_type == "Select": errors.append("Select contract type")
    if workshop_hours <= 0: errors.append("Workshop hours must be greater than zero")
    if num_prisoners < 0: errors.append("Prisoners employed cannot be negative")
    if num_supervisors > 0 and len(supervisor_salaries) != num_supervisors:
        errors.append("Choose a title for each instructor")
    return errors

# -------------------------------
# Helpers
# -------------------------------
def _get_base_total(df: pd.DataFrame) -> float:
    """
    Safely find a total in either Host or Production tables.
    Host: look for 'Grand Total' row in Amount (£)
    Production: sum any monthly inc VAT total columns.
    """
    try:
        if {"Item", "Amount (£)"}.issubset(df.columns):
            mask = df["Item"].astype(str).str.contains("Grand Total", case=False, na=False)
            if mask.any():
                val = pd.to_numeric(df.loc[mask, "Amount (£)"], errors="coerce").dropna()
                if not val.empty:
                    return float(val.iloc[-1])
        for col in ["Monthly Total inc VAT (£)", "Monthly Total (inc VAT £)", "Monthly Total (£)"]:
            if col in df.columns:
                return float(pd.to_numeric(df[col], errors="coerce").fillna(0).sum())
    except Exception:
        pass
    return 0.0

# -------------------------------
# HOST
# -------------------------------
if contract_type == "Host":
    if st.button("Generate Host Costs"):
        errs = validate_inputs()
        if errs:
            st.error("Fix errors:\n- " + "\n- ".join(errs))
        else:
            df, ctx = host61.generate_host_quote(
                workshop_hours=workshop_hours,
                num_prisoners=num_prisoners,
                prisoner_salary=prisoner_salary,
                num_supervisors=num_supervisors,
                supervisor_salaries=supervisor_salaries,
                region=region,
                contracts=contracts,
                employment_support=employment_support,
                instructor_allocation=instructor_pct,
                lock_overheads=lock_overheads,
            )
            st.session_state["host_df"] = df
            st.session_state["host_ctx"] = ctx

    if "host_df" in st.session_state:
        df = st.session_state["host_df"]
        st.markdown(render_table_html(df), unsafe_allow_html=True)

        # Productivity slider (UI-only) — does not recalc, just scales displayed total & export note
        st.markdown("---")
        prod_host = st.slider(
            "Adjust for Productivity (%)",
            min_value=50, max_value=100, value=100, step=5,
            key="prod_adj_host",
            help="Scale the displayed total by expected productivity (e.g. 90% = reduce by 10%)."
        )
        base_total = _get_base_total(df)
        adjusted_total = base_total * (prod_host / 100.0)
        st.markdown(f"**Adjusted Grand Total: {fmt_currency(adjusted_total)}**")

        extra_note = None
        if prod_host < 100:
            extra_note = (
                f"<p><strong>Adjusted Grand Total:</strong> {fmt_currency(adjusted_total)}</p>"
                "<p><em>Productivity assumptions have been applied. "
                "These will be reviewed annually with Commercial.</em></p>"
            )

        c1, c2 = st.columns(2)
        with c1:
            st.download_button("Download CSV (Host)", data=export_csv_bytes(df),
                               file_name="host_quote.csv", mime="text/csv")
        with c2:
            st.download_button("Download PDF-ready HTML (Host)",
                               data=export_html(df, None, title="Host Quote", extra_note=extra_note),
                               file_name="host_quote.html", mime="text/html")

# -------------------------------
# PRODUCTION (restored baseline)
# -------------------------------
if contract_type == "Production":
    # Full production workflow is implemented in production61; we pass baseline inputs only.
    # The module is responsible for rendering its item forms (Contractual/Ad-hoc),
    # performing validation/capacity checks, and returning the summary DataFrame + ctx.
    if st.button("Generate Production Costs"):
        errs = validate_inputs()
        if errs:
            st.error("Fix errors:\n- " + "\n- ".join(errs))
        else:
            df, ctx = production61.generate_production_quote(
                workshop_hours=workshop_hours,
                num_prisoners=num_prisoners,
                prisoner_salary=prisoner_salary,
                num_supervisors=num_supervisors,
                supervisor_salaries=supervisor_salaries,
                region=region,
                contracts=contracts,
                employment_support=employment_support,
                instructor_allocation=instructor_pct,
                lock_overheads=lock_overheads,
                prisoner_output=prisoner_output,
            )
            st.session_state["prod_df"] = df
            st.session_state["prod_ctx"] = ctx

    if "prod_df" in st.session_state:
        df = st.session_state["prod_df"]
        st.markdown(render_table_html(df), unsafe_allow_html=True)

        # Productivity slider (UI-only)
        st.markdown("---")
        prod_prod = st.slider(
            "Adjust for Productivity (%)",
            min_value=50, max_value=100, value=100, step=5,
            key="prod_adj_prod",
            help="Scale the displayed total by expected productivity (e.g. 90% = reduce by 10%)."
        )
        base_total = _get_base_total(df)
        adjusted_total = base_total * (prod_prod / 100.0)
        st.markdown(f"**Adjusted Grand Total: {fmt_currency(adjusted_total)}**")

        extra_note = None
        if prod_prod < 100:
            extra_note = (
                f"<p><strong>Adjusted Grand Total:</strong> {fmt_currency(adjusted_total)}</p>"
                "<p><em>Productivity assumptions have been applied. "
                "These will be reviewed annually with Commercial.</em></p>"
            )

        c1, c2 = st.columns(2)
        with c1:
            st.download_button("Download CSV (Production)", data=export_csv_bytes(df),
                               file_name="production_quote.csv", mime="text/csv")
        with c2:
            st.download_button("Download PDF-ready HTML (Production)",
                               data=export_html(None, df, title="Production Quote", extra_note=extra_note),
                               file_name="production_quote.html", mime="text/html")