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
    build_html_page
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
st.set_page_config(page_title="Cost and Price Calculator", layout="wide")
inject_govuk_css()


def main():
    st.title("Cost and Price Calculator")

    # Sidebar controls
    lock_overheads, instructor_pct, prisoner_output = sidebar_controls(
        CFG.GLOBAL_OUTPUT_DEFAULT
    )

    # Contract form
    with st.form("contract_form"):
        prison = st.selectbox("Prison Name", options=list(PRISON_TO_REGION.keys()))
        customer = st.text_input("Customer Name")
        contract_type = st.selectbox("Contract Type", options=["Host", "Production"])

        workshop_hours = st.number_input("How many hours is the workshop open per week?", min_value=0.0, step=0.5)
        num_prisoners = st.number_input("How many prisoners employed per week?", min_value=0, step=1)
        prisoner_salary = st.number_input("Average prisoner salary per week (£)", min_value=0.0, step=0.5)

        num_supervisors = st.number_input("How many instructors?", min_value=0, step=1)

        # ✅ Restore checkbox
        customer_covers_supervisors = st.checkbox(
            "Customer provides instructor(s)?",
            value=False,
            key="customer_covers_supervisors"
        )

        supervisor_titles, supervisor_salaries = [], []
        if num_supervisors > 0 and not customer_covers_supervisors:
            region = PRISON_TO_REGION.get(prison, "National")
            choices = SUPERVISOR_PAY[region]
            for i in range(num_supervisors):
                title = st.selectbox(
                    f"Instructor {i+1} Title",
                    options=[c["title"] for c in choices],
                    key=f"instr_title_{i}"
                )
                salary = next(c["avg_total"] for c in choices if c["title"] == title)
                st.caption(f"{region} — {fmt_currency(salary)}")
                supervisor_titles.append(title)
                supervisor_salaries.append(salary)

        num_contracts = st.number_input("How many contracts do they oversee in this workshop?", min_value=1, step=1)

        employment_support = st.selectbox(
            "What employment support does the customer offer?",
            options=["None", "Employment on release/RoTL", "Post release", "Both"]
        )

        submitted = st.form_submit_button("Generate Costs")

    if not submitted:
        return

    region = PRISON_TO_REGION.get(prison, "National")

    # ──────────────────────────────────────────────
    # HOST PATH
    # ──────────────────────────────────────────────
    if contract_type == "Host":
        df, ctx = host61.generate_host_quote(
            workshop_hours=workshop_hours,
            num_prisoners=num_prisoners,
            prisoner_salary=prisoner_salary,
            num_supervisors=num_supervisors,
            customer_covers_supervisors=customer_covers_supervisors,
            supervisor_salaries=supervisor_salaries,
            effective_pct=instructor_pct,
            region=region,
            customer_type="Commercial",
            vat_rate=20.0,
            dev_rate=0.2,
            employment_support=employment_support,
            lock_overheads=lock_overheads,
        )

        st.subheader("Host Quote")
        st.dataframe(df, use_container_width=True)

        # Adjust for productivity
        productivity = st.slider("Adjust for Productivity (%)", 50, 100, 100)
        factor = productivity / 100.0
        adjusted_df = adjust_table(df, factor)
        st.subheader("Adjusted Costs (for review only)")
        st.dataframe(adjusted_df, use_container_width=True)

        # Downloads
        html_content = build_html_page("Host Quote", render_table_html(df))
        html_bytes = BytesIO(html_content.encode("utf-8"))
        st.download_button(
            "Download PDF-ready HTML (Host Quote)",
            data=html_bytes,
            file_name="host_quote.html",
            mime="text/html"
        )

    # ──────────────────────────────────────────────
    # PRODUCTION PATH
    # ──────────────────────────────────────────────
    elif contract_type == "Production":
        st.markdown("Select production mode:")
        prod_mode = st.radio("Mode", ["Contractual", "Ad-hoc"], horizontal=True)

        if prod_mode == "Contractual":
            items = []
            st.markdown("### Contractual Production Items")
            with st.form("production_items"):
                num_items = st.number_input("Number of items", min_value=1, step=1)
                for i in range(int(num_items)):
                    name = st.text_input(f"Item {i+1} Name", key=f"name_{i}")
                    minutes = st.number_input(f"Minutes per unit (Item {i+1})", min_value=0.0, step=0.5, key=f"min_{i}")
                    required = st.number_input(f"Prisoners required per unit (Item {i+1})", min_value=1, step=1, key=f"req_{i}")
                    assigned = st.number_input(f"Prisoners assigned (Item {i+1})", min_value=0, step=1, key=f"ass_{i}")
                    items.append({"name": name, "minutes": minutes, "required": required, "assigned": assigned})
                output_pct = st.slider("Output %", 50, 100, prisoner_output)
                submitted_prod = st.form_submit_button("Generate Production Costs")

            if submitted_prod:
                results = calculate_production_contractual(
                    items, output_pct,
                    workshop_hours=workshop_hours,
                    prisoner_salary=prisoner_salary,
                    supervisor_salaries=supervisor_salaries,
                    effective_pct=instructor_pct,
                    customer_covers_supervisors=customer_covers_supervisors,
                    region=region,
                    customer_type="Commercial",
                    apply_vat=True,
                    vat_rate=20.0,
                    num_prisoners=num_prisoners,
                    num_supervisors=num_supervisors,
                    dev_rate=0.2,
                    pricing_mode="as-is",
                )
                df = pd.DataFrame(results)
                st.dataframe(df, use_container_width=True)

                # Adjusted
                productivity = st.slider("Adjust for Productivity (%)", 50, 100, 100, key="prod_adj")
                factor = productivity / 100.0
                adjusted_df = adjust_table(df, factor)
                st.subheader("Adjusted Costs (for review only)")
                st.dataframe(adjusted_df, use_container_width=True)

                # Download
                html_content = build_html_page("Production Contractual Quote", render_table_html(df))
                html_bytes = BytesIO(html_content.encode("utf-8"))
                st.download_button(
                    "Download PDF-ready HTML (Production – Contractual)",
                    data=html_bytes,
                    file_name="production_contractual.html",
                    mime="text/html"
                )

        else:  # Ad-hoc
            st.markdown("### Ad-hoc Production Lines")
            lines = []
            with st.form("adhoc_items"):
                num_lines = st.number_input("Number of lines", min_value=1, step=1)
                for i in range(int(num_lines)):
                    name = st.text_input(f"Line {i+1} Name", key=f"line_name_{i}")
                    units = st.number_input(f"Units (Line {i+1})", min_value=1, step=1, key=f"line_units_{i}")
                    mins_per_item = st.number_input(f"Minutes per unit (Line {i+1})", min_value=0.0, step=0.5, key=f"line_mins_{i}")
                    pris_per_item = st.number_input(f"Prisoners per unit (Line {i+1})", min_value=1, step=1, key=f"line_pris_{i}")
                    deadline = st.date_input(f"Deadline (Line {i+1})", value=date.today(), key=f"line_dead_{i}")
                    lines.append({"name": name, "units": units, "mins_per_item": mins_per_item, "pris_per_item": pris_per_item, "deadline": deadline})
                output_pct = st.slider("Output %", 50, 100, prisoner_output, key="adhoc_out")
                submitted_adhoc = st.form_submit_button("Generate Production Costs")

            if submitted_adhoc:
                results = calculate_adhoc(
                    lines, output_pct,
                    workshop_hours=workshop_hours,
                    num_prisoners=num_prisoners,
                    prisoner_salary=prisoner_salary,
                    supervisor_salaries=supervisor_salaries,
                    effective_pct=instructor_pct,
                    customer_covers_supervisors=customer_covers_supervisors,
                    customer_type="Commercial",
                    apply_vat=True,
                    vat_rate=20.0,
                    area_m2=0.0,
                    usage_key="low",
                    dev_rate=0.2,
                    today=date.today(),
                )
                df = pd.DataFrame(results["per_line"])
                st.dataframe(df, use_container_width=True)

                # Adjusted
                productivity = st.slider("Adjust for Productivity (%)", 50, 100, 100, key="adhoc_adj")
                factor = productivity / 100.0
                adjusted_df = adjust_table(df, factor)
                st.subheader("Adjusted Costs (for review only)")
                st.dataframe(adjusted_df, use_container_width=True)

                # Download
                html_content = build_html_page("Production Ad-hoc Quote", render_table_html(df))
                html_bytes = BytesIO(html_content.encode("utf-8"))
                st.download_button(
                    "Download PDF-ready HTML (Production – Ad-hoc)",
                    data=html_bytes,
                    file_name="production_adhoc.html",
                    mime="text/html"
                )


if __name__ == "__main__":
    main()