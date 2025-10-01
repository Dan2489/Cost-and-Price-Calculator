# newapp61.py

import streamlit as st
import pandas as pd

from config61 import CFG
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
from utils61 import inject_govuk_css, sidebar_controls, fmt_currency, export_doc
import host61
import production61


def _df_to_html_table(df: pd.DataFrame) -> str:
    """Render DataFrame as styled HTML table."""
    cols = list(df.columns)
    thead = "<tr>" + "".join([f"<th>{c}</th>" for c in cols]) + "</tr>"
    body_rows = []
    for _, row in df.iterrows():
        tds = []
        for col in cols:
            val = row[col]
            if isinstance(val, (int, float)) and pd.notna(val):
                if any(x in str(col).lower() for x in ["£", "amount", "price", "cost", "total"]):
                    tds.append(f"<td>{fmt_currency(val)}</td>")
                else:
                    tds.append(f"<td>{float(val):,.2f}</td>")
            else:
                tds.append(f"<td>{val}</td>")
        body_rows.append("<tr>" + "".join(tds) + "</tr>")
    return f"<div class='results-table'><table>{thead}{''.join(body_rows)}</table></div>"


def _dev_rate_from_support(s: str) -> float:
    """Development charge logic: starts 20%; -10% for each support; 'Both' -> 0%"""
    if s == "None":
        return 0.20
    if s in ("Employment on release/RoTL", "Post release"):
        return 0.10
    if s == "Both":
        return 0.00
    return 0.20


def main():
    inject_govuk_css()

    # ---- Header with Logo ----
    st.markdown(
        """
        <div style="display:flex; align-items:center; gap:20px; margin-bottom:1rem;">
          <img src="https://raw.githubusercontent.com/Dan2489/Cost-and-Price-Calculator/main/logo.png" style="height:80px;">
          <h2 style="margin:0;">Cost and Price Calculator</h2>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- Sidebar Controls ----
    lock_overheads, instructor_pct, prisoner_output = sidebar_controls(CFG.GLOBAL_OUTPUT_DEFAULT)

    # ---- Form ----
    with st.form("cost_form"):
        prison_name = st.selectbox("Prison Name", list(PRISON_TO_REGION.keys()))
        customer_name = st.text_input("Customer Name")
        contract_type = st.selectbox("Contract Type", ["Host", "Production"])

        workshop_hours = st.number_input("How many hours is the workshop open per week?", min_value=0.0, step=0.5)
        num_prisoners = st.number_input("How many prisoners employed per week?", min_value=0, step=1)
        prisoner_salary = st.number_input("Average prisoner salary per week (£)", min_value=0.0, step=0.5)

        num_instructors = st.number_input("How many instructors?", min_value=0, step=1)

        supervisor_titles, supervisor_salaries = [], []
        region = PRISON_TO_REGION.get(prison_name, "National")
        roles = SUPERVISOR_PAY.get(region, [])

        for i in range(int(num_instructors)):
            title_choice = st.selectbox(
                f"Instructor {i+1} Title",
                [r["title"] for r in roles],
                key=f"title_{i}",
            )
            salary = next((r["avg_total"] for r in roles if r["title"] == title_choice), 0)
            supervisor_titles.append(title_choice)
            supervisor_salaries.append(salary)
            st.caption(f"{region} — £{salary:,.0f}")

        num_contracts = st.number_input("How many contracts do they oversee in this workshop?", min_value=1, step=1)

        emp_support = st.selectbox(
            "What employment support does the customer offer?",
            ["None", "Employment on release/RoTL", "Post release", "Both"],
        )

        submitted = st.form_submit_button("Generate Costs", use_container_width=True)

    # ---- Logic ----
    if submitted:
        meta = {"customer": customer_name, "prison": prison_name, "region": region}

        if contract_type == "Host":
            dev_rate = _dev_rate_from_support(emp_support)

            host_df, _ctx = host61.generate_host_quote(
                workshop_hours=workshop_hours,
                num_prisoners=num_prisoners,
                prisoner_salary=prisoner_salary,
                num_supervisors=num_instructors,
                supervisor_salaries=supervisor_salaries,
                effective_pct=float(instructor_pct),
                customer_covers_supervisors=False,
                region=region,
                customer_type="Commercial",
                apply_vat=True,
                vat_rate=20.0,
                dev_rate=dev_rate,
                contracts_overseen=int(num_contracts),
                lock_overheads=bool(lock_overheads),
                emp_support=emp_support,
            )

            st.subheader("Host Quote")
            st.markdown(_df_to_html_table(host_df), unsafe_allow_html=True)

            html_bytes = export_doc("Host Quote", meta, host_df.to_html(index=False))
            st.download_button(
                "Download PDF-ready HTML (Host)",
                data=html_bytes,
                file_name="host_quote.html",
                mime="text/html",
            )

        else:  # Production
            prod_df = production61.calculate_production_costs(
                workshop_hours=workshop_hours,
                num_prisoners=num_prisoners,
                prisoner_salary=prisoner_salary,
                supervisor_salaries=supervisor_salaries,
                effective_pct=float(instructor_pct),
                region=region,
                customer_type="Commercial",
                apply_vat=True,
                vat_rate=20.0,
                lock_overheads=bool(lock_overheads),
                prisoner_output=int(prisoner_output),
                emp_support=emp_support,
                num_contracts=int(num_contracts),
            )

            st.subheader("Production Quote")
            st.markdown(_df_to_html_table(prod_df), unsafe_allow_html=True)

            html_bytes = export_doc("Production Quote", meta, prod_df.to_html(index=False))
            st.download_button(
                "Download PDF-ready HTML (Production)",
                data=html_bytes,
                file_name="production_quote.html",
                mime="text/html",
            )

    # ---- Reset ----
    if st.button("Reset Selections"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        try:
            st.rerun()
        except Exception:
            st.experimental_rerun()


if __name__ == "__main__":
    main()