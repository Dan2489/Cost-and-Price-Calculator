# newapp61.py
import streamlit as st
import pandas as pd
from datetime import date

from config61 import CFG
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
from utils61 import inject_govuk_css, sidebar_controls, fmt_currency, render_summary_table, export_doc
from production61 import labour_minutes_budget, calculate_production_contractual, calculate_adhoc
from host61 import generate_host_quote

def main():
    st.set_page_config(page_title="Cost and Price Calculator", page_icon="💷", layout="centered")
    inject_govuk_css()
    st.markdown("## Cost and Price Calculator")

    # -----------------------
    # Base inputs
    # -----------------------
    prison_choice = st.selectbox("Prison Name", [""] + sorted(PRISON_TO_REGION.keys()), index=0)
    region = PRISON_TO_REGION.get(prison_choice) if prison_choice else None

    customer_type = st.selectbox("I want to quote for", ["", "Commercial", "Another Government Department"], index=0)
    customer_name = st.text_input("Customer Name", "")
    contract_type = st.selectbox("Contract Type", ["", "Host", "Production"], index=0)

    workshop_hours = st.number_input("How many hours is the workshop open per week?", min_value=0.0, step=0.5, format="%.2f")
    num_prisoners = st.number_input("How many prisoners employed per week?", min_value=0, step=1)
    prisoner_salary = st.number_input("Average prisoner salary per week (£)", min_value=0.0, step=1.0, format="%.2f")

    num_supervisors = st.number_input("How many instructors?", min_value=0, step=1)
    customer_covers_supervisors = st.checkbox("Customer provides instructor(s)?", value=False)

    # Instructor titles (dynamic)
    supervisor_salaries = []
    if region and num_supervisors > 0 and not customer_covers_supervisors:
        titles_for_region = SUPERVISOR_PAY.get(region, [])
        for i in range(int(num_supervisors)):
            sel = st.selectbox(f"Instructor {i+1} Title", [t["title"] for t in titles_for_region], key=f"inst_title_{i}")
            pay = next(t["avg_total"] for t in titles_for_region if t["title"] == sel)
            st.caption(f"Region: {region} — Salary: £{pay:,.2f}")
            supervisor_salaries.append(float(pay))

    contracts = st.number_input("How many contracts do they oversee in this workshop?", min_value=1, value=1, step=1)

    support = st.selectbox(
        "What employment support does the customer offer?",
        ["", "None", "Employment on release/RoTL", "Post release", "Both"],
        index=0
    )

    # -----------------------
    # Sidebar controls
    # -----------------------
    recomm_pct = None
    try:
        recomm_pct = min(100, int(round((float(workshop_hours or 0) / 37.5) * (1 / max(1, int(contracts))) * 100)))
    except Exception:
        recomm_pct = None

    show_output = (contract_type == "Production")
    lock_overheads, instructor_pct, prisoner_output = sidebar_controls(
        CFG.GLOBAL_OUTPUT_DEFAULT, show_output_slider=show_output, rec_pct=recomm_pct
    )

    if recomm_pct is not None:
        st.info(f"Instructor allocation currently set to {instructor_pct}%. Recommended value: {recomm_pct}% (adjust in sidebar if required).")

    # Dev rate
    if customer_type == "Another Government Department":
        dev_rate = 0.0
    elif support == "None":
        dev_rate = 0.20
    elif support in ("Employment on release/RoTL", "Post release"):
        dev_rate = 0.10
    elif support == "Both":
        dev_rate = 0.00
    else:
        dev_rate = 0.20

    meta = {"customer": customer_name, "prison": prison_choice, "region": region or ""}

    # -----------------------
    # HOST
    # -----------------------
    if contract_type == "Host":
        if st.button("Generate Costs"):
            host_df, ctx = generate_host_quote(
                num_prisoners=int(num_prisoners),
                prisoner_salary=float(prisoner_salary),
                num_supervisors=int(num_supervisors),
                customer_covers_supervisors=bool(customer_covers_supervisors),
                supervisor_salaries=supervisor_salaries,
                effective_pct=float(instructor_pct),
                region=region,
                customer_type=customer_type,
                dev_rate=float(dev_rate),
                contracts_overseen=int(contracts),
                lock_overheads=bool(lock_overheads),
            )
            st.subheader("Host Monthly Costs")
            host_html = render_summary_table(ctx["rows"], dev_reduction=True)
            st.markdown(host_html, unsafe_allow_html=True)
            st.download_button(
                "Download PDF-ready HTML (Host)",
                data=export_doc("Host Quote", meta, host_html),
                file_name="host_quote.html", mime="text/html"
            )

    # -----------------------
    # PRODUCTION
    # -----------------------
    elif contract_type == "Production":
        prod_mode = st.radio("Contractual or Ad-hoc?", ["Contractual", "Ad-hoc"], index=0)

        # -------- Contractual --------
        if prod_mode == "Contractual":
            pricing_mode = st.radio("Would you like a price for:", ["Maximum output", "Targeted output"], index=0)
            num_items = st.number_input("Number of items produced?", min_value=1, value=1, step=1)

            available_100 = labour_minutes_budget(int(num_prisoners), float(workshop_hours))
            available_planned = available_100 * (float(prisoner_output) / 100.0)
            st.markdown(f"Available Labour minutes per week @ {prisoner_output}% output = {available_planned:,.0f} minutes")
            st.caption("Unit costs are based on 100% labour output. Adjust labour output in the sidebar if necessary.")

            items, targets = [], None
            running_assigned = 0
            for i in range(int(num_items)):
                with st.expander(f"Item {i+1} details", expanded=(i == 0)):
                    name = st.text_input(f"Item {i+1} Name", key=f"name_{i}")
                    required = st.number_input("Prisoners required to make 1 item", min_value=1, value=1, step=1, key=f"req_{i}")
                    minutes_per = st.number_input("Minutes to make 1 item", min_value=1.0, value=10.0, format="%.2f", key=f"mins_{i}")
                    remaining = max(0, int(num_prisoners) - running_assigned)
                    assigned = st.number_input(
                        "Prisoners assigned solely to this item",
                        min_value=0, max_value=remaining, value=0, step=1, key=f"assigned_{i}"
                    )
                    running_assigned += int(assigned)
                    items.append({"name": name, "required": int(required), "minutes": float(minutes_per), "assigned": int(assigned)})

            if pricing_mode == "Targeted output":
                targets = []
                for i in range(int(num_items)):
                    tgt = st.number_input(f"Target units/week for Item {i+1}", min_value=0, value=0, step=1, key=f"tgt_{i}")
                    targets.append(int(tgt))

            if st.button("Generate Production Costs"):
                out = calculate_production_contractual(
                    items,
                    output_pct=int(prisoner_output),
                    workshop_hours=float(workshop_hours),
                    prisoner_salary=float(prisoner_salary),
                    supervisor_salaries=supervisor_salaries,
                    effective_pct=float(instructor_pct),
                    customer_covers_supervisors=bool(customer_covers_supervisors),
                    region=region,
                    customer_type=customer_type,
                    dev_rate=float(dev_rate),
                    pricing_mode=("target" if pricing_mode == "Targeted output" else "as-is"),
                    targets=targets,
                    lock_overheads=bool(lock_overheads),
                    num_prisoners=int(num_prisoners),
                    contracts_overseen=int(contracts),
                )

                st.subheader("Production (Contractual)")
                df = pd.DataFrame(out["per_item"])

                # Hide Feasible/Note when max output (both app and export)
                if pricing_mode == "Maximum output":
                    df = df.drop(columns=["Feasible", "Note"], errors="ignore")
                    exported_html = _df_to_html_table(df)
                else:
                    exported_html = _df_to_html_table(df)

                st.markdown(exported_html, unsafe_allow_html=True)
                st.download_button(
                    "Download PDF-ready HTML (Production – Contractual)",
                    data=export_doc("Production – Contractual Quote", meta, exported_html),
                    file_name="production_contractual.html", mime="text/html"
                )

        # -------- Ad-hoc --------
        else:
            num_lines = st.number_input("How many product lines are needed?", min_value=1, value=1, step=1)
            adhoc_lines = []
            for i in range(int(num_lines)):
                with st.expander(f"Product line {i+1}", expanded=(i == 0)):
                    c1, c2, c3 = st.columns([2, 1, 1])
                    with c1:
                        item_name = st.text_input("Item name", key=f"adhoc_name_{i}")
                    with c2:
                        units_requested = st.number_input("Units requested", min_value=1, value=100, step=1, key=f"adhoc_units_{i}")
                    with c3:
                        deadline = st.date_input("Deadline", value=date.today(), key=f"adhoc_deadline_{i}")
                    c4, c5 = st.columns([1, 1])
                    with c4:
                        pris_per_item = st.number_input("Prisoners to make one", min_value=1, value=1, step=1, key=f"adhoc_pris_req_{i}")
                    with c5:
                        minutes_per_item = st.number_input("Minutes to make one", min_value=1.0, value=10.0, format="%.2f", key=f"adhoc_mins_{i}")
                    adhoc_lines.append({
                        "name": (item_name.strip() or f"Item {i+1}") if isinstance(item_name, str) else f"Item {i+1}",
                        "units": int(units_requested),
                        "deadline": deadline,
                        "pris_per_item": int(pris_per_item),
                        "mins_per_item": float(minutes_per_item),
                    })

            if st.button("Generate Production Costs"):
                result = calculate_adhoc(
                    adhoc_lines,
                    output_pct=int(prisoner_output),
                    workshop_hours=float(workshop_hours),
                    num_prisoners=int(num_prisoners),
                    prisoner_salary=float(prisoner_salary),
                    supervisor_salaries=supervisor_salaries,
                    effective_pct=float(instructor_pct),
                    customer_covers_supervisors=bool(customer_covers_supervisors),
                    region=region,
                    customer_type=customer_type,
                    dev_rate=float(dev_rate),
                    lock_overheads=bool(lock_overheads),
                    contracts_overseen=int(contracts),
                    today=date.today(),
                )
                st.subheader("Production (Ad-hoc)")
                df = pd.DataFrame(result["per_line"])
                html_table = _df_to_html_table(df)

                # Add grand totals under the table
                totals_html = f"""
                <div class='results-table'>
                  <table>
                    <tr><th>Grand Total ex VAT (£)</th><th>Grand Total inc VAT (£)</th></tr>
                    <tr class='total'><td>{fmt_currency(result['totals']['ex_vat'])}</td><td>{fmt_currency(result['totals']['inc_vat'])}</td></tr>
                  </table>
                </div>
                """
                combined_html = html_table + totals_html

                st.markdown(combined_html, unsafe_allow_html=True)

                # Feasibility advice (separate box, already UK date in production61)
                if result["feasibility"]["advice"]:
                    if result["feasibility"]["hard_block"]:
                        st.error(result["feasibility"]["advice"])
                    else:
                        st.info(result["feasibility"]["advice"])

                st.download_button(
                    "Download PDF-ready HTML (Production – Ad-hoc)",
                    data=export_doc("Production – Ad-hoc Quote", meta, combined_html),
                    file_name="production_adhoc.html", mime="text/html"
                )

    # -----------------------
    # Reset
    # -----------------------
    if st.button("Reset Selections"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        try:
            st.rerun()
        except Exception:
            st.experimental_rerun()

def _df_to_html_table(df: pd.DataFrame) -> str:
    """
    Render a DataFrame to a bordered, left-aligned HTML table.
    - Currency formatting for numeric columns that look like money.
    - Booleans shown as Yes/No.
    - Feasible/Note are treated as non-currency text.
    """
    money_like_cols = {
        "Unit Cost (£)", "Unit Price ex VAT (£)", "Unit Price inc VAT (£)",
        "Monthly Total ex VAT (£)", "Monthly Total inc VAT (£)",
        "Unit Cost ex VAT (£)", "Unit Cost inc VAT (£)",
        "Total ex VAT (£)", "Total inc VAT (£)"
    }
    non_money_cols = {"Feasible", "Note"}

    cols = list(df.columns)
    thead = "<tr>" + "".join([f"<th>{c}</th>" for c in cols]) + "</tr>"
    body_rows = []
    for _, row in df.iterrows():
        tds = []
        for col in cols:
            val = row[col]
            if col == "Feasible":
                if val is None:
                    tds.append("<td></td>")
                else:
                    tds.append(f"<td>{'Yes' if bool(val) else 'No'}</td>")
            elif col == "Note":
                tds.append(f"<td>{'' if val is None else str(val)}</td>")
            elif isinstance(val, (int, float)) and pd.notna(val):
                if col in money_like_cols:
                    tds.append(f"<td>{fmt_currency(val)}</td>")
                else:
                    # For numeric non-money (e.g., Units/week) render as integer where appropriate
                    if float(val).is_integer():
                        tds.append(f"<td>{int(val)}</td>")
                    else:
                        tds.append(f"<td>{val:,.2f}</td>")
            else:
                tds.append(f"<td>{'' if val is None else val}</td>")
        body_rows.append("<tr>" + "".join(tds) + "</tr>")
    return f"<div class='results-table'><table>{thead}{''.join(body_rows)}</table></div>"

if __name__ == "__main__":
    main()