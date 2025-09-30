# newapp61.py
# UI shell for the Cost and Price Calculator (Instructor-only model).
# - Host and Production (Contractual + Ad-hoc) with downloads (CSV + HTML).
# - VAT: always 20% (no checkbox); always show ex VAT and inc VAT prices.
# - Development charge does not apply to Another Government Department.
# - Overheads = 61% of instructor wage after % allocation (or Band 3 shadow if customer provides).
# - Sidebar: lock overheads to highest instructor cost + instructor % allocation slider (moved here by request).

from io import BytesIO
from datetime import date
import pandas as pd
import streamlit as st

from config61 import CFG
from utils61 import inject_govuk_css, PRISON_TO_REGION, SUPERVISOR_PAY, draw_sidebar
from production61 import (
    labour_minutes_budget,
    calculate_production_contractual,
    calculate_adhoc,
)
from host61 import generate_host_quote

# ----------------------------------------------------------------------------- 
# Page config + CSS
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Cost and Price Calculator", page_icon="💷", layout="centered")
inject_govuk_css()

# ----------------------------------------------------------------------------- 
# Header (no logo, unchanged aesthetic)
# -----------------------------------------------------------------------------
st.markdown("## Cost and Price Calculator")

# ----------------------------------------------------------------------------- 
# Helpers: formatting + HTML export (unchanged aesthetic)
# -----------------------------------------------------------------------------
def _currency(v) -> str:
    try:
        return f"£{float(v):,.2f}"
    except Exception:
        return ""

def render_host_df_to_html(host_df: pd.DataFrame) -> str:
    rows_html = []
    for _, row in host_df.iterrows():
        item = str(row["Item"])
        val = row["Amount (£)"]
        neg_cls = ""
        try:
            neg_cls = " class='neg'" if float(val) < 0 else ""
        except Exception:
            pass
        grand_cls = " class='grand'" if "Grand Total" in item else ""
        rows_html.append(f"<tr{grand_cls}><td>{item}</td><td{neg_cls}>{_currency(val)}</td></tr>")
    header = "<tr><th>Item</th><th>Amount (£)</th></tr>"
    return f"<table>{header}{''.join(rows_html)}</table>"

def render_generic_df_to_html(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    thead = "<tr>" + "".join([f"<th>{c}</th>" for c in cols]) + "</tr>"
    body_rows = []
    for _, row in df.iterrows():
        tds = []
        for col in cols:
            val = row[col]
            if isinstance(val, (int, float)) and pd.notna(val):
                # numeric formatting
                if "£" in col:
                    tds.append(f"<td>{_currency(val)}</td>")
                else:
                    tds.append(f"<td>{float(val):,.2f}</td>")
            else:
                tds.append(f"<td>{val}</td>")
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
        parts += ["<h3>Host Costs</h3>", render_host_df_to_html(host_df)]
    if prod_df is not None:
        section_title = "Ad-hoc Items" if "Ad-hoc" in str(title) else "Production Items"
        parts += [f"<h3>{section_title}</h3>", render_generic_df_to_html(prod_df)]
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
# Base inputs (utilities/workshop-size removed; aesthetics intact elsewhere)
# -----------------------------------------------------------------------------
prisons_sorted = ["Select"] + sorted(PRISON_TO_REGION.keys())  # no "HMP" prefixes
prison_choice = st.selectbox("Prison Name", prisons_sorted, index=0, key="prison_choice")
region = PRISON_TO_REGION.get(prison_choice, "Select") if prison_choice != "Select" else "Select"
st.session_state["region"] = region

customer_type = st.selectbox("I want to quote for", ["Select", "Commercial", "Another Government Department"], key="customer_type")
customer_name = st.text_input("Customer Name", key="customer_name")
workshop_mode = st.selectbox("Contract type?", ["Select", "Host", "Production"], key="workshop_mode")

# ---------------- Sidebar: overheads lock + instructor allocation slider -----
# Keep your familiar sidebar container & styling; add only these controls.
draw_sidebar()  # provides the "lock_overheads" checkbox (no mutation needed)
lock_overheads = st.session_state.get("lock_overheads", False)

st.sidebar.markdown("---")
st.sidebar.subheader("Instructor Time Allocation")
# Recommended % (same logic, just displayed in sidebar)
contracts = st.sidebar.number_input("How many contracts do these instructors oversee?", min_value=1, value=1, key="contracts")
workshop_hours_sidebar = st.sidebar.number_input("Hours open per week (for recommendation only)", min_value=0.0, value=float(st.session_state.get("workshop_hours", 0.0)) if "workshop_hours" in st.session_state else 0.0, format="%.2f", key="hours_for_reco")
recommended_pct = round((float(workshop_hours_sidebar or 0.0) / 37.5) * (1 / contracts) * 100, 1) if contracts else 0.0
st.sidebar.info(f"Recommended: {recommended_pct}%")
chosen_pct = st.sidebar.slider("Adjust instructor % allocation", 0, 100, int(recommended_pct))
if chosen_pct < int(round(recommended_pct)):
    st.sidebar.warning("You selected less than recommended — using the recommended % for pricing.")
    effective_pct = int(round(recommended_pct))
else:
    effective_pct = int(chosen_pct)

# ---------------- Main staffing inputs ---------------------------------------
workshop_hours = st.number_input("How many hours per week is the workshop open?", min_value=0.0, format="%.2f", key="workshop_hours")
num_prisoners   = st.number_input("How many prisoners employed?", min_value=0, step=1, key="num_prisoners")
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
            options = [t["title"] for t in titles_for_region]  # Band 3 / Band 4 only
            sel = st.selectbox(f"Instructor {i+1} title", options, key=f"inst_title_{i}")
            pay = next(t["avg_total"] for t in titles_for_region if t["title"] == sel)
            st.caption(f"Avg Total for {region}: **£{pay:,.0f}** per year")
            supervisor_salaries.append(float(pay))

# Development charge (Commercial only; unchanged)
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
# Validation (removed area/usage checks; rest unchanged)
# -----------------------------------------------------------------------------
def validate_inputs():
    errors = []
    if prison_choice == "Select": errors.append("Select prison")
    if region == "Select": errors.append("Region could not be derived from prison selection")
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
# HOST (uses instructor-only model in host61.py; aesthetics preserved)
# -----------------------------------------------------------------------------
def run_host():
    errors_top = validate_inputs()
    if st.button("Generate Costs"):
        if errors_top:
            st.error("Fix errors:\n- " + "\n- ".join(errors_top)); return
        host_df, _ctx = generate_host_quote(
            workshop_hours=float(workshop_hours),
            num_prisoners=int(num_prisoners),
            prisoner_salary=float(prisoner_salary),
            num_supervisors=int(num_supervisors),
            customer_covers_supervisors=bool(customer_covers_supervisors),
            supervisor_salaries=supervisor_salaries,
            effective_pct=float(effective_pct),
            customer_type=customer_type,
            apply_vat=True,          # VAT always on
            vat_rate=20.0,           # 20%
            region=region,
            lock_overheads=bool(lock_overheads),
            dev_rate=float(dev_rate),
        )
        # Styled like before
        st.markdown(render_host_df_to_html(host_df), unsafe_allow_html=True)
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
# PRODUCTION (Contractual + Ad-hoc). Aesthetics preserved; utilities removed
# -----------------------------------------------------------------------------
def run_production():
    errors_top = validate_inputs()
    if errors_top:
        st.error("Fix errors before production:\n- " + "\n- ".join(errors_top)); return

    st.markdown("---")
    st.subheader("Production settings")

    planned_output_pct = st.slider(
        "Planned Output (%)", min_value=0, max_value=100, value=CFG.GLOBAL_OUTPUT_DEFAULT,
        help="Scales both planned available and planned used labour minutes."
    )
    output_scale = float(planned_output_pct) / 100.0

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
            help="Maximum units uses the capacity your assignments can produce at the chosen Output%. Target lets you enter desired units/week."
        )
        pricing_mode = "as-is" if pricing_mode_label.startswith("Maximum") else "target"

        # Planned minutes (info)
        budget_minutes_raw = labour_minutes_budget(int(num_prisoners), float(workshop_hours))
        budget_minutes_planned = budget_minutes_raw * output_scale
        st.markdown(f"**Planned available Labour minutes @ {planned_output_pct}%:** {budget_minutes_planned:,.0f}")

        # Items
        num_items = st.number_input("Number of items produced?", min_value=1, value=1, step=1, key="num_items_prod")
        items, targets = [], []
        for i in range(int(num_items)):
            with st.expander(f"Item {i+1} details", expanded=(i == 0)):
                name = st.text_input(f"Item {i+1} Name", key=f"name_{i}")
                disp = (name.strip() or f"Item {i+1}") if isinstance(name, str) else f"Item {i+1}"
                required = st.number_input(f"Prisoners required to make 1 item ({disp})", min_value=1, value=1, step=1, key=f"req_{i}")
                minutes_per = st.number_input(f"How many minutes to make 1 item ({disp})", min_value=1.0, value=10.0, format="%.2f", key=f"mins_{i}")

                total_assigned_before = sum(int(st.session_state.get(f"assigned_{j}", 0)) for j in range(i))
                remaining = max(0, int(num_prisoners) - total_assigned_before)
                assigned = st.number_input(
                    f"How many prisoners work solely on this item ({disp})",
                    min_value=0, max_value=remaining, value=int(st.session_state.get(f"assigned_{i}", 0)),
                    step=1, key=f"assigned_{i}"
                )

                # Capacity preview
                if assigned > 0 and minutes_per > 0 and required > 0 and workshop_hours > 0:
                    cap_100 = (assigned * workshop_hours * 60.0) / (minutes_per * required)
                else:
                    cap_100 = 0.0
                cap_planned = cap_100 * output_scale
                st.markdown(f"{disp} capacity @ 100%: **{cap_100:.0f} units/week** · @ {planned_output_pct}%: **{cap_planned:.0f}**")

                # Target input — ONLY when pricing_mode == "target"
                if pricing_mode == "target":
                    tgt_default = int(round(cap_planned)) if cap_planned > 0 else 0
                    tgt = st.number_input(f"Target units per week ({disp})", min_value=0, value=tgt_default, step=1, key=f"target_{i}")
                    targets.append(int(tgt))

                items.append({"name": name, "required": int(required), "minutes": float(minutes_per), "assigned": int(assigned)})

        total_assigned = sum(it["assigned"] for it in items)
        if total_assigned > int(num_prisoners):
            st.error(f"Prisoners assigned across items ({total_assigned}) exceed total prisoners ({int(num_prisoners)})."); return

        used_minutes_raw = total_assigned * workshop_hours * 60.0
        used_minutes_planned = used_minutes_raw * output_scale
        st.markdown(f"**Planned used Labour minutes @ {planned_output_pct}%:** {used_minutes_planned:,.0f}")

        if pricing_mode == "as-is" and used_minutes_planned > budget_minutes_planned:
            st.error("Planned used minutes exceed planned available minutes. Adjust assignments, add prisoners, increase hours, or lower Output%."); return

        # === Always apply VAT 20% in calculations ===
        results = calculate_production_contractual(
            items, planned_output_pct,
            workshop_hours=float(workshop_hours),
            prisoner_salary=float(prisoner_salary),
            supervisor_salaries=supervisor_salaries,
            effective_pct=float(effective_pct),
            customer_covers_supervisors=bool(customer_covers_supervisors),
            customer_type=customer_type,
            apply_vat=True,          # force VAT on
            vat_rate=20.0,           # 20%
            num_prisoners=int(num_prisoners),
            num_supervisors=int(num_supervisors),
            lock_overheads=bool(lock_overheads),
            region=region,
            dev_rate=float(dev_rate),
            pricing_mode=pricing_mode,
            targets=targets if pricing_mode == "target" else None,
        )

        # Build display — always show ex VAT and inc VAT + Monthly totals; hide target-only cols in max mode
        display_cols = ["Item", "Output %", "Capacity (units/week)", "Units/week",
                        "Unit Cost (£)", "Unit Price ex VAT (£)", "Unit Price inc VAT (£)",
                        "Monthly Total ex VAT (£)", "Monthly Total inc VAT (£)"]
        if pricing_mode == "target":
            display_cols += ["Feasible", "Note"]  # only in target mode

        prod_df = pd.DataFrame([{
            k: (None if r.get(k) is None else (round(float(r.get(k)), 2) if isinstance(r.get(k), (int, float)) else r.get(k)))
            for k in display_cols
        } for r in results])

        st.markdown(render_generic_df_to_html(prod_df), unsafe_allow_html=True)
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
                with c2: units_requested = st.number_input("Units requested", min_value=1, value=100, step=1, key="adhoc_units_{i}")
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
                lines, planned_output_pct,
                workshop_hours=float(workshop_hours),
                num_prisoners=int(num_prisoners),
                prisoner_salary=float(prisoner_salary),
                supervisor_salaries=supervisor_salaries,
                effective_pct=float(effective_pct),
                customer_covers_supervisors=bool(customer_covers_supervisors),
                customer_type=customer_type,
                apply_vat=True,       # VAT on
                vat_rate=20.0,        # 20%
                lock_overheads=bool(lock_overheads),
                region=region,
                today=date.today(),
                dev_rate=float(dev_rate),
            )
            if result.get("feasibility", {}).get("hard_block"):
                st.error(result["feasibility"]["reason"]); return

            # Table with BOTH ex VAT and inc VAT columns (aesthetic preserved)
            col_headers = ["Item", "Units",
                           "Unit Cost (ex VAT £)", "Unit Cost (inc VAT £)",
                           "Line Total (ex VAT £)", "Line Total (inc VAT £)"]
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
# -----------------------------------------------------------------------------
if workshop_mode == "Host":
    run_host()
elif workshop_mode == "Production":
    run_production()

# ----------------------------------------------------------------------------- 
# Reset
# -----------------------------------------------------------------------------
st.markdown('\n', unsafe_allow_html=True)
if st.button("Reset Selections", key="reset_app_footer"):
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    try:
        st.rerun()
    except Exception:
        st.experimental_rerun()
st.markdown('\n', unsafe_allow_html=True)