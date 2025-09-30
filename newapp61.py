from io import BytesIO
from datetime import date
import pandas as pd
import streamlit as st

from config61 import CFG
from utils61 import inject_govuk_css, PRISON_TO_REGION, SUPERVISOR_PAY, draw_sidebar
from host61 import generate_host_quote
from production61 import labour_minutes_budget, calculate_production_contractual, calculate_adhoc

# -----------------------------------------------------------------------------
# Page config + CSS
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Cost and Price Calculator", page_icon="💷", layout="centered")
inject_govuk_css()

# -----------------------------------------------------------------------------
# Header
# -----------------------------------------------------------------------------
st.markdown("## Cost and Price Calculator")

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _currency(v) -> str:
    try:
        return f"£{float(v):,.2f}"
    except Exception:
        return ""

def render_df_to_html(df: pd.DataFrame, money_cols: list[str]) -> str:
    cols = list(df.columns)
    thead = "<tr>" + "".join([f"<th>{c}</th>" for c in cols]) + "</tr>"
    body_rows = []
    for _, row in df.iterrows():
        tds = []
        for col in cols:
            val = row[col]
            if col in money_cols and val is not None and pd.notna(val):
                tds.append(f"<td>{_currency(val)}</td>")
            else:
                tds.append(f"<td>{val if val is not None else ''}</td>")
        body_rows.append("<tr>" + "".join(tds) + "</tr>")
    return f"<table>{thead}{''.join(body_rows)}</table>"

def export_csv_bytes(df: pd.DataFrame) -> BytesIO:
    b = BytesIO()
    df.to_csv(b, index=False)
    b.seek(0)
    return b

def export_html(host_df: pd.DataFrame | None,
                prod_df: pd.DataFrame | None,
                title: str = "Quote") -> BytesIO:
    css = """
      <style>
        body{font-family:Arial,Helvetica,sans-serif;color:#0b0c0c;}
        table{width:100%;border-collapse:collapse;margin:12px 0;}
        th,td{border-bottom:1px solid #b1b4b6;padding:8px;text-align:left;}
        th{background:#f3f2f1;} td.neg{color:#d4351c;} tr.grand td{font-weight:700;}
        h1,h2,h3{margin:0.2rem 0;}
      </style>
    """
    header_html = f"<h2>{title}</h2>"
    meta = (f"<p>Date: {date.today().isoformat()}<br/>"
            f"Customer: {st.session_state.get('customer_name','')}<br/>"
            f"Prison: {st.session_state.get('prison_choice','')}<br/>"
            f"Region: {st.session_state.get('region','')}</p>")
    parts = [css, header_html, meta]
    if host_df is not None:
        parts += ["<h3>Host Costs</h3>", render_df_to_html(host_df, ["Amount (£)"])]
    if prod_df is not None:
        section_title = "Ad-hoc Items" if "Ad-hoc" in str(title) else "Production Items"
        parts += [f"<h3>{section_title}</h3>", render_df_to_html(prod_df, prod_df.columns[1:].tolist())]
    parts.append("<p>Prices are indicative and may change based on final scope and site conditions.</p>")

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>{title}</title>
</head>
<body>
{''.join(parts)}
</body>
</html>"""
    b = BytesIO(html_doc.encode("utf-8"))
    b.seek(0)
    return b

# -----------------------------------------------------------------------------
# Sidebar controls
# -----------------------------------------------------------------------------
draw_sidebar()
planned_output_pct = float(st.session_state.get("planned_output_pct", CFG.GLOBAL_OUTPUT_DEFAULT))
effective_pct = float(st.session_state.get("chosen_pct", 100))

# -----------------------------------------------------------------------------
# Base inputs
# -----------------------------------------------------------------------------
prisons_sorted = ["Select"] + sorted(PRISON_TO_REGION.keys())
prison_choice = st.selectbox("Prison Name", prisons_sorted, index=0, key="prison_choice")
region = PRISON_TO_REGION.get(prison_choice, "National") if prison_choice != "Select" else "National"
st.session_state["region"] = region

customer_type = st.selectbox("I want to quote for", ["Select", "Commercial", "Another Government Department"], key="customer_type")
customer_name = st.text_input("Customer Name", key="customer_name")
workshop_mode = st.selectbox("Contract type?", ["Select", "Host", "Production"], key="workshop_mode")

workshop_hours = st.number_input("How many hours per week is the workshop open?", min_value=0.0, format="%.2f", key="workshop_hours")
num_prisoners = st.number_input("How many prisoners employed?", min_value=0, step=1, key="num_prisoners")
prisoner_salary = st.number_input("Prisoner salary per week (£)", min_value=0.0, format="%.2f", key="prisoner_salary")

num_supervisors = st.number_input("How many instructors?", min_value=0, step=1, key="num_supervisors")
customer_covers_supervisors = st.checkbox("Customer provides instructor(s)?", key="customer_covers_supervisors")

supervisor_salaries = []
if not customer_covers_supervisors:
    titles_for_region = SUPERVISOR_PAY.get(region, [])
    if region == "Select" or not titles_for_region:
        st.warning("Select a prison to derive the Region before assigning instructor titles.")
    else:
        for i in range(int(num_supervisors)):
            options = [t["title"] for t in titles_for_region]
            sel = st.selectbox(f"Instructor {i+1} title", options, key=f"inst_title_{i}")
            pay = next(t["avg_total"] for t in titles_for_region if t["title"] == sel)
            st.caption(f"Avg Total for {region}: **£{pay:,.0f}** per year")
            supervisor_salaries.append(float(pay))

contracts = st.number_input("How many contracts do these instructors oversee?", min_value=1, value=1, key="contracts")
recommended_pct = round((workshop_hours / 37.5) * (1 / contracts) * 100, 1) if contracts and workshop_hours >= 0 else 0
st.subheader("Instructor Time Allocation (recommended %)")
st.info(f"Recommended: {recommended_pct}%")

# Development charge %
dev_rate = 0.0
if customer_type == "Commercial":
    support = st.selectbox(
        "Customer employment support?",
        ["None", "Employment on release/RoTL", "Post release", "Both"],
        help="Affects development charge (on overheads). 'Both' reduces dev charge to 0%."
    )
    if support == "None":
        dev_rate = 0.20
    elif support in ("Employment on release/RoTL", "Post release"):
        dev_rate = 0.10
    else:
        dev_rate = 0.00

# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------
def validate_inputs():
    errors = []
    if prison_choice == "Select": errors.append("Select prison")
    if customer_type == "Select": errors.append("Select customer type")
    if not str(customer_name).strip(): errors.append("Enter customer name")
    if workshop_mode == "Select": errors.append("Select contract type")
    if workshop_mode == "Production" and workshop_hours <= 0: errors.append("Hours per week must be > 0 (Production)")
    if prisoner_salary < 0: errors.append("Prisoner salary per week cannot be negative")
    if num_prisoners < 0: errors.append("Prisoners employed cannot be negative")
    if not customer_covers_supervisors:
        if num_supervisors <= 0: errors.append("Enter number of instructors (>0) or tick 'Customer provides instructor(s)'")
        if region == "Select": errors.append("Select a prison/region to populate instructor titles")
        if len(supervisor_salaries) != int(num_supervisors): errors.append("Choose a title for each instructor")
        if any(s <= 0 for s in supervisor_salaries): errors.append("Instructor Avg Total must be > 0")
    return errors

# -----------------------------------------------------------------------------
# HOST
# -----------------------------------------------------------------------------
def run_host():
    errors_top = validate_inputs()
    if st.button("Generate Costs"):
        if errors_top:
            st.error("Fix errors:\n- " + "\n- ".join(errors_top)); return
        host_df, _ctx = generate_host_quote(
            num_prisoners=int(num_prisoners),
            prisoner_salary=float(prisoner_salary),
            num_supervisors=int(num_supervisors),
            customer_covers_supervisors=bool(customer_covers_supervisors),
            supervisor_salaries=supervisor_salaries,
            effective_pct=float(effective_pct),
            region=region,
            customer_type=customer_type,
            vat_rate=20.0,
            dev_rate=float(dev_rate),
        )
        st.markdown(render_df_to_html(host_df, ["Amount (£)"]), unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.download_button("Download CSV (Host)", data=export_csv_bytes(host_df), file_name="host_quote.csv", mime="text/csv")
        with c2:
            st.download_button(
                "Download PDF-ready HTML (Host)",
                data=export_html(host_df, None, title="Host Quote"),
                file_name="host_quote.html", mime="text/html"
            )

# -----------------------------------------------------------------------------
# PRODUCTION
# -----------------------------------------------------------------------------
def run_production():
    errors_top = validate_inputs()
    if errors_top:
        st.error("Fix errors before production:\n- " + "\n- ".join(errors_top)); return

    prod_type = st.radio(
        "Do you want ad-hoc costs with a deadline, or contractual work?",
        ["Contractual work", "Ad-hoc costs (multiple lines) with deadlines"],
        index=0, key="prod_type"
    )

    if prod_type == "Contractual work":
        pricing_mode_label = st.radio(
            "Price based on:",
            ["Maximum units from capacity", "Target units per week"],
            index=0,
        )
        pricing_mode = "as-is" if pricing_mode_label.startswith("Maximum") else "target"

        budget_minutes_raw = labour_minutes_budget(int(num_prisoners), float(workshop_hours))
        budget_minutes_planned = budget_minutes_raw * (planned_output_pct / 100.0)
        st.markdown(f"**Planned available Labour minutes @ {planned_output_pct}%:** {budget_minutes_planned:,.0f}")

        num_items = st.number_input("Number of items produced?", min_value=1, value=1, step=1, key="num_items_prod")
        items, targets = [], []
        for i in range(int(num_items)):
            with st.expander(f"Item {i+1} details", expanded=(i == 0)):
                name = st.text_input(f"Item {i+1} Name", key=f"name_{i}")
                disp = (name.strip() or f"Item {i+1}") if isinstance(name, str) else f"Item {i+1}"
                required = st.number_input(f"Prisoners required to make 1 item ({disp})", min_value=1, value=1, step=1, key=f"req_{i}")
                minutes_per = st.number_input(f"Minutes to make 1 item ({disp})", min_value=1.0, value=10.0, format="%.2f", key=f"mins_{i}")
                assigned = st.number_input(
                    f"How many prisoners work solely on this item ({disp})",
                    min_value=0, max_value=int(num_prisoners),
                    value=int(st.session_state.get(f"assigned_{i}", 0)),
                    step=1, key=f"assigned_{i}"
                )
                if pricing_mode == "target":
                    tgt_default = 0
                    tgt = st.number_input(f"Target units per week ({disp})", min_value=0, value=tgt_default, step=1, key=f"target_{i}")
                    targets.append(int(tgt))
                items.append({"name": name, "required": int(required), "minutes": float(minutes_per), "assigned": int(assigned)})

        results = calculate_production_contractual(
            items, int(planned_output_pct),
            workshop_hours=float(workshop_hours),
            prisoner_salary=float(prisoner_salary),
            supervisor_salaries=supervisor_salaries,
            effective_pct=float(effective_pct),
            customer_covers_supervisors=bool(customer_covers_supervisors),
            region=region,
            customer_type=customer_type,
            vat_rate=20.0,
            dev_rate=float(dev_rate),
            pricing_mode=pricing_mode,
            targets=targets if pricing_mode == "target" else None,
        )

        display_cols = ["Item", "Output %", "Capacity (units/week)", "Units/week",
                        "Unit Cost (£)", "Unit Price ex VAT (£)", "Unit Price inc VAT (£)", "Monthly Total (£)"]
        if pricing_mode == "target":
            display_cols += ["Feasible", "Note"]

        prod_df = pd.DataFrame([{k: r.get(k) for k in display_cols} for r in results])

        st.markdown(render_df_to_html(prod_df, display_cols[4:]), unsafe_allow_html=True)
        d1, d2 = st.columns(2)
        with d1:
            st.download_button("Download CSV (Production)", data=export_csv_bytes(prod_df), file_name="production_quote.csv", mime="text/csv")
        with d2:
            st.download_button(
                "Download PDF-ready HTML (Production)",
                data=export_html(None, prod_df, title="Production Quote"),
                file_name="production_quote.html", mime="text/html"
            )

    else:  # Ad-hoc
        num_lines = st.number_input("How many product lines are needed?", min_value=1, value=1, step=1, key="adhoc_num_lines")
        lines = []
        for i in range(int(num_lines)):
            with st.expander(f"Product line {i+1}", expanded=(i == 0)):
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1: item_name = st.text_input("Item name", key=f"adhoc_name_{i}")
                with c2: units_requested = st.number_input("Units requested", min_value=1, value=100, step=1, key=f"adhoc_units_{i}")
                with c3: deadline = st.date_input("Deadline", value=date.today(), key=f"adhoc_deadline_{i}")
                c4, c5 = st.columns([1, 1])
                with c4: pris_per_item = st.number_input("Prisoners to make one", min_value=1, value=1, step=1, key=f"adhoc_pris_req_{i}")
                with c5: minutes_per_item = st.number_input("Minutes to make one", min_value=1.0, value=10.0, format="%.2f", key=f"adhoc_mins_{i}")
                lines.append({
                    "name": (item_name.strip() or f"Item {i+1}") if isinstance(item_name, str) else f"Item {i+1}",
                    "units": int(units_requested),
                    "deadline": deadline,
                    "pris_per_item": int(pris_per_item),
                    "mins_per_item": float(minutes_per_item),
                })

        if st.button("Calculate Ad-hoc Cost", key="calc_adhoc"):
            errs = validate_inputs()
            if workshop_hours <= 0: errs.append("Hours per week must be > 0 for Ad-hoc")
            for i, ln in enumerate(lines):
                if ln["units"] <= 0: errs.append(f"Line {i+1}: Units requested must be > 0")
                if ln["pris_per_item"] <= 0: errs.append(f"Line {i+1}: Prisoners to make one must be > 0")
                if ln["mins_per_item"] <= 0: errs.append(f"Line {i+1}: Minutes to make one must be > 0")
            if errs:
                st.error("Fix errors:\n- " + "\n- ".join(errs)); return

            result = calculate_adhoc(
                lines, int(planned_output_pct),
                workshop_hours=float(workshop_hours),
                num_prisoners=int(num_prisoners),
                prisoner_salary=float(prisoner_salary),
                supervisor_salaries=supervisor_salaries,
                effective_pct=float(effective_pct),
                customer_covers_supervisors=bool(customer_covers_supervisors),
                region=region,
                customer_type=customer_type,
                vat_rate=20.0,
                dev_rate=float(dev_rate),
                today=date.today(),
            )
            if result["feasibility"]["hard_block"]:
                st.error(result["feasibility"]["reason"]); return

            col_headers = ["Item", "Units", "Unit Cost (ex VAT £)", "Unit Cost (inc VAT £)", "Line Total (ex VAT £)", "Line Total (inc VAT £)"]
            data_rows = []
            for p in result["per_line"]:
                data_rows.append([
                    p["name"], f"{p['units']:,}",
                    f"{p['unit_cost_ex_vat']:.2f}", f"{p['unit_cost_inc_vat']:.2f}",
                    f"{p['line_total_ex_vat']:.2f}", f"{p['line_total_inc_vat']:.2f}",
                ])
            table_html = ["<table><tr>"] + [f"<th>{h}</th>" for h in col_headers] + ["</tr>"]
            for r in data_rows:
                table_html.append("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>")
            table_html.append("</table>")
            st.markdown("".join(table_html), unsafe_allow_html=True)

            totals = result["totals"]
            st.markdown(f"**Total Job Cost (ex VAT): £{totals['ex_vat']:,.2f}**")
            st.markdown(f"**Total Job Cost (inc VAT): £{totals['inc_vat']:,.2f}**")

# -----------------------------------------------------------------------------
# MAIN
# --------------
if __name__ == "__main__":
    if workshop_mode == "Host":
        run_host()
    elif workshop_mode == "Production":
        run_production()
    else:
        st.info("Select a contract type above to begin.")