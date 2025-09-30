# newapp61.py
import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import date

from config61 import CFG
from utils61 import inject_govuk_css, fmt_currency, recommended_instructor_allocation, render_summary_table, sidebar_controls
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
from host61 import generate_host_quote
from production61 import labour_minutes_budget, calculate_production_contractual

# -----------------------------------------------------------------------------
# Page + CSS
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Cost and Price Calculator", page_icon="💷", layout="centered")
inject_govuk_css()
st.markdown("## Cost and Price Calculator")

# -----------------------------------------------------------------------------
# Sidebar (3 controls)
# -----------------------------------------------------------------------------
lock_overheads, instructor_pct, prisoner_output = sidebar_controls(CFG.global_output_default)

# -----------------------------------------------------------------------------
# Export helpers (CSV + PDF-ready HTML)
# -----------------------------------------------------------------------------
def export_csv_bytes(df: pd.DataFrame) -> BytesIO:
    b = BytesIO()
    df.to_csv(b, index=False)
    b.seek(0)
    return b

def export_html(title: str, meta: dict, body_html: str) -> BytesIO:
    css = """
      <style>
        body{font-family:Arial,Helvetica,sans-serif;color:#0b0c0c;}
        table{width:100%;border-collapse:collapse;margin:12px 0;}
        th,td{border-bottom:1px solid #b1b4b6;padding:8px;text-align:left;}
        th{background:#f3f2f1;} td.neg{color:#d4351c;} tr.total td{font-weight:700;}
        h1,h2,h3{margin:0.2rem 0;}
      </style>
    """
    header_html = f"<h2>{title}</h2>"
    meta_html = (
        f"<p>Date: {date.today().isoformat()}<br/>"
        f"Customer: {meta.get('customer','')}<br/>"
        f"Prison: {meta.get('prison','')}<br/>"
        f"Region: {meta.get('region','')}</p>"
    )
    html_doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8" /><title>{title}</title>{css}</head>
<body>{header_html}{meta_html}{body_html}</body></html>"""
    b = BytesIO(html_doc.encode("utf-8"))
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

# Instructor titles (dynamic)
supervisor_salaries = []
if region and num_supervisors > 0:
    titles_for_region = SUPERVISOR_PAY.get(region, [])
    if not titles_for_region:
        st.warning("Select a prison to derive the Region before assigning instructor titles.")
    else:
        for i in range(int(num_supervisors)):
            sel = st.selectbox(f"Instructor {i+1} Title", [t["title"] for t in titles_for_region], key=f"inst_title_{i}")
            pay = next(t["avg_total"] for t in titles_for_region if t["title"] == sel)
            st.caption(f"Region: {region} — Salary: £{pay:,.2f}")
            supervisor_salaries.append(float(pay))

contracts = st.number_input("How many contracts do they oversee in this workshop?", min_value=1, value=1, step=1)

# Instructor allocation recommendation (as per your formula: 37.5 / hours / contracts)
if workshop_hours > 0 and contracts > 0:
    rec = round((37.5 / float(workshop_hours)) * (1 / float(contracts)) * 100.0, 1)
    st.info(f"Recommended instructor allocation: **{rec}%**")
else:
    rec = 0.0

support = st.selectbox(
    "What employment support does the customer offer?",
    ["", "None", "Employment on release/ROTL", "Post release", "Both"],
    index=0
)

# -----------------------------------------------------------------------------
# Production inputs (items)
# -----------------------------------------------------------------------------
prod_mode = None
pricing_mode = None
items, targets = [], None

if contract_type == "Production":
    prod_mode = st.radio("Contractual or Ad-hoc?", ["Contractual", "Ad-hoc"], index=0)
    if prod_mode == "Contractual":
        pricing_mode = st.radio("Would you like a price for:", ["Maximum output", "Targeted output"], index=0)
        num_items = st.number_input("Number of items produced?", min_value=1, value=1, step=1)

        # Capacity info
        available_100 = labour_minutes_budget(int(num_prisoners), float(workshop_hours))
        available_planned = available_100 * (float(prisoner_output) / 100.0)
        st.markdown(f"**Available labour minutes/week @ 100%:** {available_100:,.0f} · "
                    f"@ {prisoner_output}%:** {available_planned:,.0f}**")

        running_assigned = 0
        for i in range(int(num_items)):
            with st.expander(f"Item {i+1} details", expanded=(i == 0)):
                name = st.text_input(f"Item {i+1} Name", key=f"name_{i}")
                required = st.number_input("Prisoners required to make 1 item", min_value=1, value=1, step=1, key=f"req_{i}")
                minutes_per = st.number_input("Minutes to make 1 item", min_value=1.0, value=10.0, format="%.2f", key=f"mins_{i}")

                # Validation: do not allow assigning beyond total prisoners
                remaining = max(0, int(num_prisoners) - running_assigned)
                assigned = st.number_input("Prisoners assigned solely to this item",
                                           min_value=0, max_value=remaining, value=0, step=1, key=f"assigned_{i}")
                running_assigned += int(assigned)

                items.append({"name": name, "required": int(required), "minutes": float(minutes_per), "assigned": int(assigned)})

        if pricing_mode == "Targeted output":
            targets = []
            for i in range(int(num_items)):
                tgt = st.number_input(f"Target units/week for Item {i+1}", min_value=0, value=0, step=1, key=f"tgt_{i}")
                targets.append(int(tgt))

# -----------------------------------------------------------------------------
# Development charge rate
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
    errors = []
    if not prison_choice: errors.append("Select prison")
    if not region: errors.append("Region not derived from prison")
    if not customer_type: errors.append("Select customer type")
    if not contract_type: errors.append("Select contract type")
    if contract_type == "Production" and workshop_hours <= 0: errors.append("Hours per week must be > 0 (Production)")

    if errors:
        st.error("Fix errors:\n- " + "\n- ".join(errors))
    else:
        # ------------------------ HOST ------------------------
        if contract_type == "Host":
            host_df, ctx = generate_host_quote(
                num_prisoners=int(num_prisoners),
                prisoner_salary=float(prisoner_salary),
                num_supervisors=int(num_supervisors),
                customer_covers_supervisors=(int(num_supervisors) == 0),
                supervisor_salaries=supervisor_salaries,
                effective_pct=float(instructor_pct),
                region=region,
                customer_type=customer_type,
                dev_rate=float(dev_rate),
                contracts_overseen=int(contracts),
                lock_overheads=bool(lock_overheads),
            )
            st.subheader("Host Monthly Costs")

            # Render GOV.UK style table with red reductions
            host_html = render_summary_table(ctx["rows"], dev_reduction=True)
            st.markdown(host_html, unsafe_allow_html=True)

            # Downloads
            c1, c2 = st.columns(2)
            with c1:
                st.download_button("Download CSV (Host)", data=export_csv_bytes(host_df), file_name="host_quote.csv", mime="text/csv")
            with c2:
                html_file = export_html(
                    "Host Quote",
                    {"customer": customer_name, "prison": prison_choice, "region": region},
                    host_html
                )
                st.download_button("Download PDF-ready HTML (Host)", data=html_file, file_name="host_quote.html", mime="text/html")

        # --------------------- PRODUCTION ---------------------
        elif contract_type == "Production":
            if prod_mode == "Contractual":
                out = calculate_production_contractual(
                    items,
                    output_pct=int(prisoner_output),
                    workshop_hours=float(workshop_hours),
                    prisoner_salary=float(prisoner_salary),
                    supervisor_salaries=supervisor_salaries,
                    effective_pct=float(instructor_pct),
                    customer_covers_supervisors=(int(num_supervisors) == 0),
                    region=region,
                    customer_type=customer_type,
                    dev_rate=float(dev_rate),
                    pricing_mode=("target" if pricing_mode == "Targeted output" else "as-is"),
                    targets=targets,
                    lock_overheads=bool(lock_overheads),
                    num_prisoners=int(num_prisoners),
                    contracts_overseen=int(contracts),
                )

                # Minutes summary (cannot exceed)
                mins = out["minutes"]
                st.markdown(
                    f"**Available minutes/week @ 100%:** {mins['available_100']:,.0f} · "
                    f"@ {prisoner_output}%:** {mins['available_planned']:,.0f}** · "
                    f"**Planned usage:** {mins['used_planned']:,.0f}"
                )
                if mins["used_planned"] - mins["available_planned"] > 1e-6:
                    st.error("Planned minutes exceed available minutes. Reduce targets or assignments, or increase hours/prisoners/output%.")
                    st.stop()

                # Display table (formatted)
                df = out["df"]
                money_cols = [c for c in df.columns if "£" in c]
                st.subheader("Production (Contractual)")
                st.table(df.style.format({c: fmt_currency for c in money_cols}))

                # Totals
                total_ex = df["Monthly Total ex VAT (£)"].fillna(0).sum() if "Monthly Total ex VAT (£)" in df else 0.0
                total_inc = df["Monthly Total inc VAT (£)"].fillna(0).sum() if "Monthly Total inc VAT (£)" in df else 0.0
                st.markdown(f"**Total monthly (ex VAT): {fmt_currency(total_ex)}**")
                st.markdown(f"**Total monthly (inc VAT): {fmt_currency(total_inc)}**")

                # Downloads
                c1, c2 = st.columns(2)
                with c1:
                    st.download_button("Download CSV (Production)", data=export_csv_bytes(df), file_name="production_quote.csv", mime="text/csv")
                with c2:
                    # Build simple HTML table from df
                    df2 = df.copy()
                    for c in money_cols:
                        df2[c] = df2[c].apply(fmt_currency)
                    table_html = df2.to_html(index=False, escape=False)
                    html_file = export_html(
                        "Production Quote",
                        {"customer": customer_name, "prison": prison_choice, "region": region},
                        table_html
                    )
                    st.download_button("Download PDF-ready HTML (Production)", data=html_file, file_name="production_quote.html", mime="text/html")
            else:
                st.info("Ad-hoc pricing can be added if required.")