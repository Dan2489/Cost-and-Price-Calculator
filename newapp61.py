# newapp61.py
import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import date

from config61 import CFG
from utils61 import inject_govuk_css, sidebar_controls, render_summary_table, fmt_currency, export_doc
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
from host61 import generate_host_quote
from production61 import labour_minutes_budget, calculate_production_contractual, calculate_adhoc

# -----------------------------------------------------------------------------
# Page + CSS
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Cost and Price Calculator", page_icon="💷", layout="centered")
inject_govuk_css()

# -----------------------------------------------------------------------------
# Logo + Title (local logo.png in repo root)
# -----------------------------------------------------------------------------
st.markdown(
    """
    <div style="display:flex; align-items:center; gap:15px; margin-bottom:1rem;">
        <img src="logo.png" style="height:60px;">
        <h2 style="margin:0;">Cost and Price Calculator</h2>
    </div>
    """,
    unsafe_allow_html=True
)

# -----------------------------------------------------------------------------
# CSV helper
# -----------------------------------------------------------------------------
def export_csv_bytes(df: pd.DataFrame) -> BytesIO:
    b = BytesIO()
    df.to_csv(b, index=False)
    b.seek(0)
    return b

# -----------------------------------------------------------------------------
# Main inputs
# -----------------------------------------------------------------------------
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
    ["", "None", "Employment on release/ROTL", "Post release", "Both"],
    index=0
)

# Sidebar – only show for Production
if contract_type == "Production":
    lock_overheads, instructor_pct, prisoner_output = sidebar_controls(
        CFG.global_output_default, float(workshop_hours or 0.0), int(contracts or 1)
    )
else:
    lock_overheads, instructor_pct, prisoner_output = False, 100, 100

# -----------------------------------------------------------------------------
# Development charge rate (20% minus reductions; 0% for Another Government Department)
# -----------------------------------------------------------------------------
def _dev_rate(base: float, support_choice: str, cust_type: str) -> float:
    if cust_type == "Another Government Department":
        return 0.0
    rate = base
    if support_choice == "Employment on release/ROTL": rate -= 0.10
    elif support_choice == "Post release": rate -= 0.10
    elif support_choice == "Both": rate -= 0.20
    return max(rate, 0.0)

dev_rate = _dev_rate(0.20, support, customer_type)

# -----------------------------------------------------------------------------
# Generate
# -----------------------------------------------------------------------------
if st.button("Generate Costs"):
    # Basic validation
    errors = []
    if not prison_choice: errors.append("Select prison")
    if not customer_type: errors.append("Select customer type")
    if not customer_name.strip(): errors.append("Enter customer name")
    if not contract_type: errors.append("Select contract type")
    if workshop_hours <= 0: errors.append("Hours per week must be > 0")
    if num_prisoners < 0: errors.append("Prisoners employed cannot be negative")
    if prisoner_salary < 0: errors.append("Prisoner salary cannot be negative")
    if errors:
        st.error("Fix errors:\n- " + "\n- ".join(errors))
        st.stop()

    meta = {"customer": customer_name, "prison": prison_choice, "region": region or ""}

    if contract_type == "Host":
        # HOST
        host_df, ctx = generate_host_quote(
            num_prisoners=int(num_prisoners),
            prisoner_salary=float(prisoner_salary),
            num_supervisors=int(num_supervisors),
            customer_covers_supervisors=customer_covers_supervisors,
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
        st.download_button("Download CSV (Host)", export_csv_bytes(host_df), "host_quote.csv", "text/csv")
        st.download_button("Download PDF-ready HTML (Host)", export_doc("Host Quote", meta, host_html), "host_quote.html", "text/html")

    elif contract_type == "Production":
        prod_mode = st.radio("Contractual or Ad-hoc?", ["Contractual", "Ad-hoc"], index=0)

        if prod_mode == "Contractual":
            pricing_mode = st.radio("Would you like a price for:", ["Maximum output", "Targeted output"], index=0)
            num_items = st.number_input("Number of items produced?", min_value=1, value=1, step=1)

            # Capacity info
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

            # Run calc
            out = calculate_production_contractual(
                items,
                output_pct=int(prisoner_output),
                workshop_hours=float(workshop_hours),
                prisoner_salary=float(prisoner_salary),
                supervisor_salaries=supervisor_salaries,
                effective_pct=float(instructor_pct),
                customer_covers_supervisors=customer_covers_supervisors,
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

            # Downloads
            prod_df = pd.DataFrame(rows)  # convenience CSV (raw numbers)
            st.download_button("Download CSV (Production – Contractual)", export_csv_bytes(prod_df), "production_contractual.csv", "text/csv")
            st.download_button("Download PDF-ready HTML (Production – Contractual)",
                               export_doc("Production – Contractual Quote", meta, prod_html),
                               "production_contractual.html", "text/html")

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
                customer_covers_supervisors=customer_covers_supervisors,
                region=region,
                customer_type=customer_type,
                dev_rate=float(dev_rate),
                lock_overheads=bool(lock_overheads),
                contracts_overseen=int(contracts),
                today=date.today(),
            )

            if result["feasibility"]["hard_block"]:
                st.error(result["feasibility"]["reason"])
                st.stop()

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

            # Downloads
            adhoc_df = pd.DataFrame(result["per_line"])
            st.download_button("Download CSV (Production – Ad-hoc)", export_csv_bytes(adhoc_df), "production_adhoc.csv", "text/csv")
            st.download_button("Download PDF-ready HTML (Production – Ad-hoc)",
                               export_doc("Production – Ad-hoc Quote", meta, adhoc_html),
                               "production_adhoc.html", "text/html")

# -----------------------------------------------------------------------------
# Reset (clears ALL fields)
# -----------------------------------------------------------------------------
if st.button("Reset Selections"):
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.experimental_rerun()