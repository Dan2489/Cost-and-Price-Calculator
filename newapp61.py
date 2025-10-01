import streamlit as st
import pandas as pd
from datetime import date
from io import BytesIO

from config61 import CFG
import host61
import production61
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
from utils61 import inject_govuk_css, fmt_currency, export_csv_bytes, export_html


# -------------------------------------------------------------------
# Page config + CSS
# -------------------------------------------------------------------
st.set_page_config(page_title="Cost and Price Calculator", page_icon="💷", layout="centered")
inject_govuk_css()

st.title("Cost and Price Calculator")

# -------------------------------------------------------------------
# Base Inputs
# -------------------------------------------------------------------
prisons_sorted = ["Select"] + sorted(PRISON_TO_REGION.keys())
prison_choice = st.selectbox("Prison Name", prisons_sorted, index=0, key="prison_choice")
region = PRISON_TO_REGION.get(prison_choice, "Select") if prison_choice != "Select" else "Select"

customer_name = st.text_input("Customer Name", key="customer_name")
contract_type = st.selectbox("Contract Type", ["Select", "Host", "Production"], key="contract_type")

workshop_hours = st.number_input("How many hours is the workshop open per week?", min_value=0.0, format="%.2f")
num_prisoners = st.number_input("How many prisoners employed per week?", min_value=0, step=1)
prisoner_salary = st.number_input("Average prisoner salary per week (£)", min_value=0.0, format="%.2f")

num_supervisors = st.number_input("How many instructors?", min_value=0, step=1)

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

# -------------------------------------------------------------------
# Validation
# -------------------------------------------------------------------
def validate_inputs():
    errors = []
    if prison_choice == "Select":
        errors.append("Select prison")
    if region == "Select":
        errors.append("Region could not be derived from prison selection")
    if not str(customer_name).strip():
        errors.append("Enter customer name")
    if contract_type == "Select":
        errors.append("Select contract type")
    if workshop_hours <= 0:
        errors.append("Workshop hours must be greater than zero")
    if num_prisoners < 0:
        errors.append("Prisoners employed cannot be negative")
    if num_supervisors > 0 and len(supervisor_salaries) != num_supervisors:
        errors.append("Choose a title for each instructor")
    return errors


# -------------------------------------------------------------------
# Helpers: extract a safe total from DF (fallback to ctx)
# -------------------------------------------------------------------
def _safe_total_from_df(df: pd.DataFrame, ctx: dict | None = None) -> float:
    try:
        # Host-style table: look for a "Grand Total" row
        if {"Item", "Amount (£)"}.issubset(df.columns):
            mask = df["Item"].astype(str).str.contains("Grand Total", case=False, na=False)
            if mask.any():
                return float(pd.to_numeric(df.loc[mask, "Amount (£)"], errors="coerce").dropna().iloc[-1])
            # else sum the Amount column (last resort)
            return float(pd.to_numeric(df["Amount (£)"], errors="coerce").fillna(0).sum())

        # Production-style table: sum monthly inc VAT column if present
        prod_cols = ["Monthly Total inc VAT (£)", "Monthly Total (inc VAT £)"]
        for c in prod_cols:
            if c in df.columns:
                return float(pd.to_numeric(df[c], errors="coerce").fillna(0).sum())

        # Fallback to ctx if provided
        if ctx and "grand_total" in ctx:
            return float(ctx["grand_total"])
    except Exception:
        pass
    return 0.0


# -------------------------------------------------------------------
# HOST MODE
# -------------------------------------------------------------------
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
            )

            st.markdown(df.to_html(index=False), unsafe_allow_html=True)

            # Productivity slider
            st.markdown("---")
            productivity_adj = st.slider(
                "Adjust for Productivity (%)",
                min_value=50, max_value=100, value=100, step=5,
                help="Scale final totals by expected productivity (e.g. 90% = reduce costs by 10%)"
            )

            base_total = _safe_total_from_df(df, ctx)
            adjusted_total = base_total * (productivity_adj / 100.0)
            st.markdown(f"**Adjusted Grand Total: {fmt_currency(adjusted_total)}**")

            # Export
            extra_note = None
            if productivity_adj < 100:
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


# -------------------------------------------------------------------
# PRODUCTION MODE
# -------------------------------------------------------------------
if contract_type == "Production":
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
            )

            st.markdown(df.to_html(index=False), unsafe_allow_html=True)

            # Productivity slider
            st.markdown("---")
            productivity_adj = st.slider(
                "Adjust for Productivity (%)",
                min_value=50, max_value=100, value=100, step=5,
                help="Scale final totals by expected productivity (e.g. 90% = reduce costs by 10%)"
            )

            base_total = _safe_total_from_df(df, ctx)
            adjusted_total = base_total * (productivity_adj / 100.0)
            st.markdown(f"**Adjusted Grand Total: {fmt_currency(adjusted_total)}**")

            # Export
            extra_note = None
            if productivity_adj < 100:
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