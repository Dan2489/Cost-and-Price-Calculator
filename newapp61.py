# newapp61.py
import streamlit as st
import pandas as pd
from datetime import date

from config61 import CFG
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
from utils61 import inject_govuk_css, sidebar_controls, fmt_currency, render_summary_table, export_doc
from production61 import labour_minutes_budget, calculate_production_contractual, calculate_adhoc
from host61 import generate_host_quote

def _df_to_html_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    thead = "<tr>" + "".join([f"<th>{c}</th>" for c in cols]) + "</tr>"
    body_rows = []
    for _, row in df.iterrows():
        tds = []
        for col in cols:
            val = row[col]
            if isinstance(val, (int, float)) and pd.notna(val):
                tds.append(f"<td>{fmt_currency(val)}</td>")
            else:
                tds.append(f"<td>{val}</td>")
        body_rows.append("<tr>" + "".join(tds) + "</tr>")
    return f"<div class='results-table'><table>{thead}{''.join(body_rows)}</table></div>"

def _dev_rate_from_support(s: str, customer_type: str) -> float:
    if customer_type == "Another Government Department":
        return 0.0
    # Starts 20%; -10% each for RoTL and Post-release; Both -> 0
    if s == "None": return 0.20
    if s in ("Employment on release/ROTL", "Employment on release/RoTL"): return 0.10
    if s == "Post release": return 0.10
    if s == "Both": return 0.00
    return 0.20

def main():
    st.set_page_config(page_title="Cost and Price Calculator", page_icon="💷", layout="centered")
    inject_govuk_css()
    st.markdown("## Cost and Price Calculator")

    # Base inputs
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

    # Sidebar – only show labour output slider in Production
    recomm_pct = min(100, int(round((workshop_hours / 37.5) * (1 / max(1, int(contracts))) * 100))) if workshop_hours and contracts else None
    show_output = (contract_type == "Production")
    lock_overheads, instructor_pct, prisoner_output = sidebar_controls(
        CFG.GLOBAL_OUTPUT_DEFAULT, show_output_slider=show_output, rec_pct=recomm_pct
    )

    dev_rate = _dev_rate_from_support(support, customer_type)

    # Generate
    if st.button("Generate Costs"):
        # Validation
        errors = []
        if not prison_choice: errors.append("Select prison")
        if not customer_type: errors.append("Select customer type")
        if not customer_name.strip(): errors.append("Enter customer name")
        if not contract_type: errors.append("Select contract type")
        if workshop_hours <= 0: errors.append("Hours per week must be > 0")
        if num_prisoners < 0: errors.append("Prisoners employed cannot be negative")
        if prisoner_salary < 0: errors.append("Prisoner salary cannot be negative")
        if not region: errors.append("Region could not be derived from prison selection")
        if errors:
            st.error("Fix errors:\n- " + "\n- ".join(errors))
            st.stop()

        meta = {"customer": customer_name, "prison": prison_choice, "region": region or ""}

        if contract_type == "Host":
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

            # Downloads
            st.download_button("Download PDF-ready HTML (Host)", data=export_doc("Host Quote", meta, host_html),
                               file_name="host_quote.html", mime="text/html")

        elif contract_type == "Production":
            prod_mode = st.radio("Contractual or Ad-hoc?", ["Contractual", "Ad-hoc"], index=0)

            if prod_mode == "Contractual":
                pricing_mode = st.radio("Would you like a price for:", ["Maximum output", "Targeted output"], index=0)
                num_items = st.number_input("Number of items produced?", min_value=1, value=1, step=1)

                # Minutes info
                available_100 = labour_minutes_budget(int(num_prisoners), float(workshop_hours))
                available_planned = available_100 * (float(prisoner_output) / 100.0)
                st.markdown(f"Available Labour minutes per week @ {prisoner_output}% output = {available_planned:,.0f} minutes")

                # Items
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

                # Build table
                rows = out["per_item"]
                thead = (
                    "<tr><th>Item</th><th>Output %</th><th>Capacity (units/week)</th>"
                    "<th>Units/week</th><th>Unit Cost (£)</th><th>Unit Price ex VAT (£)</th>"
                    "<th>Unit Price inc VAT (£)</th><th>Monthly Total ex VAT (£)</th><th>Monthly Total inc VAT (£)</th></tr>"
                )
                body = []
                total_ex, total_inc = 0.0, 0.0
                for r in rows:
                    unit_cost = fmt_currency(r.get("Unit Cost (£)")) if r.get("Unit Cost (£)") else ""
                    unit_px_ex = fmt_currency(r.get("Unit Price ex VAT (£)")) if r.get("Unit Price ex VAT (£)") else ""
                    unit_px_in = fmt_currency(r.get("Unit Price inc VAT (£)")) if r.get("Unit Price inc VAT (£)") else ""
                    m_ex = r.get("Monthly Total ex VAT (£)") or 0.0
                    m_in = r.get("Monthly Total inc VAT (£)") or 0.0
                    total_ex += m_ex; total_inc += m_in
                    m_ex_s = fmt_currency(m_ex) if m_ex else ""
                    m_in_s = fmt_currency(m_in) if m_in else ""
                    body.append(
                        f"<tr><td>{r.get('Item','')}</td><td>{int(r.get('Output %',0))}</td>"
                        f"<td>{int(r.get('Capacity (units/week)',0))}</td><td>{int(r.get('Units/week',0))}</td>"
                        f"<td>{unit_cost}</td><td>{unit_px_ex}</td><td>{unit_px_in}</td>"
                        f"<td>{m_ex_s}</td><td>{m_in_s}</td></tr>"
                    )
                tfoot = (
                    f"<tr class='total'><td colspan='7'>Grand Total (monthly, ex VAT)</td><td colspan='2'>{fmt_currency(total_ex)}</td></tr>"
                    f"<tr class='total'><td colspan='7'>Grand Total (monthly, inc VAT)</td><td colspan='2'>{fmt_currency(total_inc)}</td></tr>"
                )
                prod_html = f"<div class='results-table'><table>{thead}{''.join(body)}{tfoot}</table></div>"

                st.subheader("Production (Contractual)")
                st.markdown(prod_html, unsafe_allow_html=True)

                # Export
                st.download_button("Download PDF-ready HTML (Production – Contractual)",
                                   data=export_doc("Production – Contractual Quote", meta, prod_html),
                                   file_name="production_contractual.html", mime="text/html")

            else:
                # Ad-hoc
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

                if result["feasibility"]["hard_block"]:
                    st.error(result["feasibility"]["reason"])
                else:
                    thead = (
                        "<tr><th>Item</th><th>Units</th><th>Unit Cost (ex VAT £)</th>"
                        "<th>Unit Cost (inc VAT £)</th><th>Line Total (ex VAT £)</th>"
                        "<th>Line Total (inc VAT £)</th><th>Working days available</th>"
                        "<th>Working days needed (alone)</th></tr>"
                    )
                    body = []
                    for p in result["per_line"]:
                        body.append(
                            f"<tr><td>{p['name']}</td><td>{p['units']:,}</td>"
                            f"<td>{fmt_currency(p['unit_cost_ex_vat'])}</td>"
                            f"<td>{fmt_currency(p['unit_cost_inc_vat'])}</td>"
                            f"<td>{fmt_currency(p['line_total_ex_vat'])}</td>"
                            f"<td>{fmt_currency(p['line_total_inc_vat'])}</td>"
                            f"<td>{p['wd_available']}</td><td>{p['wd_needed_line_alone']}</td></tr>"
                        )
                    tfoot = (
                        f"<tr class='total'><td colspan='4'>Total Job Cost (ex VAT)</td><td colspan='4'>{fmt_currency(result['totals']['ex_vat'])}</td></tr>"
                        f"<tr class='total'><td colspan='4'>Total Job Cost (inc VAT)</td><td colspan='4'>{fmt_currency(result['totals']['inc_vat'])}</td></tr>"
                    )
                    adhoc_html = f"<div class='results-table'><table>{thead}{''.join(body)}{tfoot}</table></div>"

                    st.subheader("Production (Ad-hoc)")
                    st.markdown(adhoc_html, unsafe_allow_html=True)

                    st.download_button("Download PDF-ready HTML (Production – Ad-hoc)",
                                       data=export_doc("Production – Ad-hoc Quote", meta, adhoc_html),
                                       file_name="production_adhoc.html", mime="text/html")

    # Reset
    if st.button("Reset Selections"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        try:
            st.rerun()
        except Exception:
            st.experimental_rerun()

if __name__ == "__main__":
    main()