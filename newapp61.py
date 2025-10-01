import streamlit as st
import pandas as pd
from datetime import date
from io import BytesIO

from config61 import CFG
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
from utils61 import (
    inject_govuk_css,
    sidebar_controls,
    fmt_currency,
    render_table_html,
    adjust_table,
    build_html_page,
)
from production61 import (
    labour_minutes_budget,
    calculate_production_contractual,
    calculate_adhoc,
)
import host61


# ──────────────────────────────────────────────
# App setup
# ──────────────────────────────────────────────
st.set_page_config(page_title="Cost and Price Calculator", layout="centered")
inject_govuk_css()


def main():
    st.markdown('<div class="govuk-heading-l">Cost and Price Calculator</div>', unsafe_allow_html=True)

    # Sidebar
    lock_overheads, instructor_pct, prisoner_output = sidebar_controls(
        getattr(CFG, "GLOBAL_OUTPUT_DEFAULT", 100)
    )

    # Base form
    prisons_sorted = list(PRISON_TO_REGION.keys())
    with st.form("contract_form"):
        prison = st.selectbox("Prison Name", options=prisons_sorted)
        customer = st.text_input("Customer Name")
        contract_type = st.selectbox("Contract Type", options=["Host", "Production"])

        workshop_hours = st.number_input("How many hours is the workshop open per week?", min_value=0.0, step=0.25, format="%.2f")
        num_prisoners  = st.number_input("How many prisoners employed per week?", min_value=0, step=1)
        prisoner_salary= st.number_input("Average prisoner salary per week (£)", min_value=0.0, step=0.25)

        num_supervisors = st.number_input("How many instructors?", min_value=0, step=1)

        # ✅ Customer provides instructor(s)?
        customer_covers_supervisors = st.checkbox(
            "Customer provides instructor(s)?",
            value=False,
            key="customer_covers_supervisors"
        )

        # Dynamic titles (only if customer does NOT provide)
        supervisor_salaries = []
        region = PRISON_TO_REGION.get(prison, "National")
        if num_supervisors > 0 and not customer_covers_supervisors:
            titles_for_region = SUPERVISOR_PAY.get(region, [])
            options = [t["title"] for t in titles_for_region]
            for i in range(int(num_supervisors)):
                sel = st.selectbox(f"Instructor {i+1} Title", options, key=f"inst_title_{i}")
                pay = next(t["avg_total"] for t in titles_for_region if t["title"] == sel)
                st.caption(f"{region} — {fmt_currency(pay)}")
                supervisor_salaries.append(float(pay))

        contracts_overseen = st.number_input("How many contracts do they oversee in this workshop?", min_value=1, step=1, value=1)

        employment_support = st.selectbox(
            "What employment support does the customer offer?",
            ["None", "Employment on release/RoTL", "Post release", "Both"],
        )

        submitted = st.form_submit_button("Generate Costs")

    if not submitted:
        return

    region = PRISON_TO_REGION.get(prison, "National")

    # ──────────────────────────────────────────────
    # HOST
    # ──────────────────────────────────────────────
    if contract_type == "Host":
        df, ctx = host61.generate_host_quote(
            workshop_hours=float(workshop_hours),
            area_m2=0.0,                      # unused in 61% method
            usage_key="low",
            num_prisoners=int(num_prisoners),
            prisoner_salary=float(prisoner_salary),
            num_supervisors=int(num_supervisors),
            customer_covers_supervisors=bool(customer_covers_supervisors),  # ✅ now passed in
            supervisor_salaries=supervisor_salaries,
            effective_pct=float(instructor_pct),
            customer_type="Commercial",
            apply_vat=True,
            vat_rate=20.0,
            dev_rate=0.20,
            employment_support=employment_support,
            contracts_overseen=int(contracts_overseen),
            lock_overheads=bool(lock_overheads),
            region=region,
        )

        st.markdown(render_table_html(df), unsafe_allow_html=True)

        # Productivity slider
        st.write("")
        prod = st.slider("Adjust for Productivity (%)", 50, 100, 100, key="host_prod_adj")
        factor = prod / 100.0
        st.subheader("Adjusted Costs (for review only)")
        df_adj = adjust_table(df, factor)
        st.markdown(render_table_html(df_adj, highlight=True), unsafe_allow_html=True)

        # Download
        body = f"""
        <h1>Host Quote</h1>
        <p class="caption">Date: {date.today().strftime('%d/%m/%Y')}<br>
        Customer: {customer}<br>
        Prison: {prison}<br>
        Region: {region}</p>
        {render_table_html(df)}
        <h2>Adjusted Costs (for review only)</h2>
        {render_table_html(df_adj, highlight=True)}
        <p class="caption">Productivity assumptions have been applied. These will be reviewed annually with Commercial.</p>
        """
        html = build_html_page("Host Quote", body)
        st.download_button(
            "Download PDF-ready HTML (Host)",
            data=BytesIO(html.encode("utf-8")),
            file_name="host_quote.html",
            mime="text/html",
        )
        return

    # ──────────────────────────────────────────────
    # PRODUCTION
    # ──────────────────────────────────────────────
    prod_mode = st.radio("Production mode", ["Contractual", "Ad-hoc"], horizontal=True)

    if prod_mode == "Contractual":
        items = st.session_state.get("prod_items", [])
        if not items:
            st.warning("No items found. Please add items, then click Generate Costs.")
            return

        results = calculate_production_contractual(
            items, int(prisoner_output),
            workshop_hours=float(workshop_hours),
            prisoner_salary=float(prisoner_salary),
            supervisor_salaries=supervisor_salaries,
            effective_pct=float(instructor_pct),
            customer_covers_supervisors=bool(customer_covers_supervisors),  # ✅ passed in
            region=region,
            customer_type="Commercial",
            apply_vat=True,
            vat_rate=20.0,
            num_prisoners=int(num_prisoners),
            num_supervisors=int(num_supervisors),
            dev_rate=0.20,
            pricing_mode="as-is",
            targets=None,
            lock_overheads=bool(lock_overheads),
        )
        df = pd.DataFrame(results)
        for col in ("Feasible", "Note"):
            if col in df.columns:
                df.drop(columns=[col], inplace=True)

        st.markdown(render_table_html(df), unsafe_allow_html=True)

        prod = st.slider("Adjust for Productivity (%)", 50, 100, 100, key="prod_contract_adj")
        factor = prod / 100.0
        st.subheader("Adjusted Costs (for review only)")
        df_adj = adjust_table(df, factor)
        st.markdown(render_table_html(df_adj, highlight=True), unsafe_allow_html=True)

        body = f"""
        <h1>Production – Contractual Quote</h1>
        <p class="caption">Date: {date.today().strftime('%d/%m/%Y')}<br>
        Customer: {customer}<br>
        Prison: {prison}<br>
        Region: {region}</p>
        {render_table_html(df)}
        <h2>Adjusted Costs (for review only)</h2>
        {render_table_html(df_adj, highlight=True)}
        <p class="caption">Productivity assumptions have been applied. These will be reviewed annually with Commercial.</p>
        """
        html = build_html_page("Production – Contractual Quote", body)
        st.download_button(
            "Download PDF-ready HTML (Production – Contractual)",
            data=BytesIO(html.encode("utf-8")),
            file_name="production_contractual.html",
            mime="text/html",
        )
        return

    else:
        adhoc_lines = st.session_state.get("adhoc_lines", [])
        if not adhoc_lines:
            st.warning("No ad-hoc lines found. Please add lines, then click Generate Costs.")
            return

        result = calculate_adhoc(
            adhoc_lines, int(prisoner_output),
            workshop_hours=float(workshop_hours),
            num_prisoners=int(num_prisoners),
            prisoner_salary=float(prisoner_salary),
            supervisor_salaries=supervisor_salaries,
            effective_pct=float(instructor_pct),
            customer_covers_supervisors=bool(customer_covers_supervisors),  # ✅ passed in
            customer_type="Commercial",
            apply_vat=True,
            vat_rate=20.0,
            area_m2=0.0,
            usage_key="low",
            dev_rate=0.20,
            today=date.today(),
        )
        df = pd.DataFrame(result["per_line"])
        st.markdown(render_table_html(df), unsafe_allow_html=True)

        prod = st.slider("Adjust for Productivity (%)", 50, 100, 100, key="prod_adhoc_adj")
        factor = prod / 100.0
        st.subheader("Adjusted Costs (for review only)")
        df_adj = adjust_table(df, factor)
        st.markdown(render_table_html(df_adj, highlight=True), unsafe_allow_html=True)

        body = f"""
        <h1>Production – Ad-hoc Quote</h1>
        <p class="caption">Date: {date.today().strftime('%d/%m/%Y')}<br>
        Customer: {customer}<br>
        Prison: {prison}<br>
        Region: {region}</p>
        {render_table_html(df)}
        <h2>Adjusted Costs (for review only)</h2>
        {render_table_html(df_adj, highlight=True)}
        <p class="caption">Productivity assumptions have been applied. These will be reviewed annually with Commercial.</p>
        """
        html = build_html_page("Production – Ad-hoc Quote", body)
        st.download_button(
            "Download PDF-ready HTML (Production – Ad-hoc)",
            data=BytesIO(html.encode("utf-8")),
            file_name="production_adhoc.html",
            mime="text/html",
        )


if __name__ == "__main__":
    main()