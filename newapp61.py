import streamlit as st
import pandas as pd
from datetime import date

from config61 import CFG
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
from utils61 import (
    inject_govuk_css, sidebar_controls, fmt_currency,
    export_csv_bytes, export_html, render_table_html
)
from production61 import (
    BAND3_COSTS,
    labour_minutes_budget,
    calculate_production_contractual,
    calculate_adhoc,
    build_adhoc_table,
)
import host61

# -------------------------------
# Page setup
# -------------------------------
st.set_page_config(page_title="Cost and Price Calculator", page_icon="💷", layout="centered")
inject_govuk_css()
st.title("Cost and Price Calculator")

# -------------------------------
# Sidebar
# -------------------------------
lock_overheads, instructor_pct, prisoner_output = sidebar_controls(CFG.GLOBAL_OUTPUT_DEFAULT)

# -------------------------------
# Base inputs
# -------------------------------
prisons_sorted = ["Select"] + sorted(PRISON_TO_REGION.keys())
prison_choice = st.selectbox("Prison Name", prisons_sorted, index=0, key="prison_choice")
region = PRISON_TO_REGION.get(prison_choice, "Select") if prison_choice != "Select" else "Select"
st.session_state["region"] = region

customer_name = st.text_input("Customer Name", key="customer_name")
contract_type = st.selectbox("Contract Type", ["Select", "Host", "Production"], key="contract_type")

workshop_hours = st.number_input("How many hours is the workshop open per week?", min_value=0.0, format="%.2f")
num_prisoners = st.number_input("How many prisoners employed per week?", min_value=0, step=1)
prisoner_salary = st.number_input("Average prisoner salary per week (£)", min_value=0.0, format="%.2f")

# Instructor inputs
num_supervisors = st.number_input("How many Instructors?", min_value=1, step=1)
customer_covers_supervisors = st.checkbox("Customer provides Instructor(s)?", value=False)

supervisor_salaries = []
if num_supervisors > 0 and region != "Select" and not customer_covers_supervisors:
    titles_for_region = SUPERVISOR_PAY.get(region, [])
    for i in range(int(num_supervisors)):
        options = [t["title"] for t in titles_for_region]
        sel = st.selectbox(f"Instructor {i+1} Title", options, key=f"inst_title_{i}")
        pay = next(t["avg_total"] for t in titles_for_region if t["title"] == sel)
        st.caption(f"{region} — £{pay:,.0f}")
        supervisor_salaries.append(float(pay))

contracts = st.number_input("How many contracts do they oversee in this workshop?", min_value=1, value=1)

# Recommendation (display only)
try:
    recommended_pct = round((workshop_hours / 37.5) * (1 / contracts) * 100, 1) if contracts and workshop_hours >= 0 else 0.0
except Exception:
    recommended_pct = 0.0
st.caption(f"**Recommended Instructor allocation:** {recommended_pct}% (based on hours open and contracts)")

employment_support = st.selectbox(
    "What employment support does the customer offer?",
    ["None", "Employment on release/RoTL", "Post release", "Both"],
)

# -------------------------------
# Validation
# -------------------------------
def validate_inputs():
    errors = []
    if prison_choice == "Select": errors.append("Select prison")
    if region == "Select": errors.append("Region could not be derived from prison selection")
    if not str(customer_name).strip(): errors.append("Enter customer name")
    if contract_type == "Select": errors.append("Select contract type")
    if workshop_hours <= 0: errors.append("Workshop hours must be greater than zero")
    if num_prisoners < 0: errors.append("Prisoners employed cannot be negative")
    if not customer_covers_supervisors and num_supervisors > 0 and len(supervisor_salaries) != num_supervisors:
        errors.append("Choose a title for each instructor")
    return errors

# -------------------------------
# Helpers
# -------------------------------
def _get_base_total(df: pd.DataFrame) -> float:
    try:
        if {"Item", "Amount (£)"}.issubset(df.columns):
            mask = df["Item"].astype(str).str.contains("Grand Total", case=False, na=False)
            if mask.any():
                val = pd.to_numeric(df.loc[mask, "Amount (£)"], errors="coerce").dropna()
                if not val.empty:
                    return float(val.iloc[-1])
        for col in ["Monthly Total inc VAT (£)", "Monthly Total (inc VAT £)", "Monthly Total (£)"]:
            if col in df.columns:
                return float(pd.to_numeric(df[col], errors="coerce").fillna(0).sum())
    except Exception:
        pass
    return 0.0

def _uk_date(d: date) -> str:
    return d.strftime("%d/%m/%Y")

def _dev_rate_from_support(s: str) -> float:
    # Base 20%, minus 10% for each support; floor at 0
    base = 0.20
    if s == "Employment on release/RoTL": base -= 0.10
    elif s == "Post release": base -= 0.10
    elif s == "Both": base -= 0.20
    return max(0.0, base)

# -------------------------------
# HOST
# -------------------------------
if contract_type == "Host":
    if st.button("Generate Host Costs"):
        errs = validate_inputs()
        if errs:
            st.error("Fix errors:\n- " + "\n- ".join(errs))
        else:
            host_df, ctx = host61.generate_host_quote(
                workshop_hours=workshop_hours,
                num_prisoners=num_prisoners,
                prisoner_salary=prisoner_salary,
                num_supervisors=num_supervisors,
                customer_covers_supervisors=customer_covers_supervisors,
                supervisor_salaries=supervisor_salaries,
                region=region,
                contracts=contracts,
                employment_support=employment_support,
                instructor_allocation=instructor_pct,
                lock_overheads=lock_overheads,
            )
            st.session_state["host_df"] = host_df
            st.session_state["host_ctx"] = ctx

    if "host_df" in st.session_state:
        df = st.session_state["host_df"]
        # Hide Instructor Salary line from view if customer supplies instructor(s)
        if customer_covers_supervisors and "Item" in df.columns:
            df_display = df[~df["Item"].astype(str).str.contains("Instructor Salary", na=False)].copy()
        else:
            df_display = df.copy()

        st.markdown(render_table_html(df_display), unsafe_allow_html=True)

        # Downloads
        header_kwargs = dict(
            prison_name=prison_choice,
            region=region,
            customer_name=customer_name,
            uk_date=_uk_date(date.today()),
        )

        # CSV (flat)
        rows = []
        row = {
            "Date": _uk_date(date.today()),
            "Customer": customer_name,
            "Prison": prison_choice,
            "Region": region,
            "Contract Type": "Host",
            "Hours/week": workshop_hours,
            "Prisoners": num_prisoners,
            "Prisoner salary/week (£)": prisoner_salary,
            "Instructors": num_supervisors,
            "Customer provides Instructors": "Yes" if customer_covers_supervisors else "No",
            "Instructor allocation (%)": instructor_pct,
            "Recommended allocation (%)": recommended_pct,
            "Contracts overseen": contracts,
            "Employment support": employment_support,
            "Lock overheads": "Yes" if lock_overheads else "No",
        }
        def _grab(name):
            try:
                v = df.loc[df["Item"] == name, "Amount (£)"].values
                return float(v[0]) if len(v) else None
            except Exception:
                return None
        row.update({
            "Instructor Salary (£/month)": _grab("Instructor Salary"),
            "Overheads 61% (£/month)": _grab("Overheads (61%)"),
            "Development charge (£/month)": _grab("Development charge"),
            "Reduction for support (£/month)": _grab("Reduction for support"),
            "Revised development charge (£/month)": _grab("Revised development charge"),
            "Subtotal (£/month)": _grab("Subtotal"),
            "VAT (20%) (£/month)": _grab("VAT (20.0%)"),
            "Grand Total (£/month)": _grab("Grand Total (£/month)"),
        })
        rows.append(row)
        csv_host = pd.DataFrame(rows)

        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "Download CSV (Host)",
                data=export_csv_bytes(csv_host),
                file_name="host_quote.csv",
                mime="text/csv"
            )
        with c2:
            st.download_button(
                "Download PDF-ready HTML (Host)",
                data=export_html(df_display, None, title="Host Quote", **header_kwargs),
                file_name="host_quote.html",
                mime="text/html"
            )

# -------------------------------
# PRODUCTION
# -------------------------------
if contract_type == "Production":
    st.markdown("---")
    st.subheader("Production settings")

    output_scale = float(prisoner_output) / 100.0
    budget_minutes_raw = labour_minutes_budget(int(num_prisoners), float(workshop_hours))
    budget_minutes_planned = budget_minutes_raw * output_scale
    st.info(f"Available Labour minutes per week @ {prisoner_output}% = **{budget_minutes_planned:,.0f} minutes**.")

    prod_mode = st.radio("Do you want contractual or ad-hoc costs?", ["Contractual", "Ad-hoc"], index=0)

    if prod_mode == "Contractual":
        pricing_mode = st.radio("Price based on:", ["Maximum units from capacity", "Target units per week"], index=0)
        pricing_mode_key = "as-is" if pricing_mode.startswith("Maximum") else "target"

        num_items = st.number_input("Number of items produced?", min_value=1, value=1, step=1, key="num_items_prod")
        items, targets = [], []

        for i in range(int(num_items)):
            with st.expander(f"Item {i+1} details", expanded=(i == 0)):
                name = st.text_input(f"Item {i+1} Name", key=f"name_{i}")
                label = (name.strip() or f"Item {i+1}") if isinstance(name, str) else f"Item {i+1}"

                required = st.number_input(
                    f"Prisoners required to make 1 item ({label})",
                    min_value=1, value=1, step=1, key=f"req_{i}"
                )

                # Minutes/Seconds input
                unit = st.radio(
                    f"Input unit for production time ({label})",
                    ["Minutes", "Seconds"], index=0, key=f"time_unit_{i}", horizontal=True
                )
                time_value = st.number_input(
                    f"How long to make 1 item ({label}) ({unit.lower()})",
                    min_value=0.0, value=0.10 if unit == "Minutes" else 6.0,
                    format="%.2f", key=f"time_val_{i}"
                )
                minutes_per = (time_value if unit == "Minutes" else time_value / 60.0)

                total_assigned_before = sum(int(st.session_state.get(f"assigned_{j}", 0)) for j in range(i))
                remaining = max(0, int(num_prisoners) - total_assigned_before)
                assigned = st.number_input(
                    f"How many prisoners work solely on this item ({label})",
                    min_value=0, max_value=remaining, value=int(st.session_state.get(f"assigned_{i}", 0)),
                    step=1, key=f"assigned_{i}"
                )

                # Optional current price per unit (ex VAT)
                current_price = st.number_input(
                    f"Current price per unit (£) ({label})", min_value=0.0, value=0.0, format="%.2f", key=f"curr_price_{i}"
                )

                # Capacity preview
                if assigned > 0 and minutes_per > 0 and required > 0 and workshop_hours > 0:
                    cap_100 = (assigned * workshop_hours * 60.0) / (minutes_per * required)
                else:
                    cap_100 = 0.0
                cap_planned = cap_100 * output_scale
                st.caption(f"{label} capacity @ 100%: **{cap_100:.0f} units/week** · @ {prisoner_output}%: **{cap_planned:.0f}**")

                if pricing_mode_key == "target":
                    tgt_default = int(round(cap_planned)) if cap_planned > 0 else 0
                    tgt = st.number_input(f"Target units per week ({label})", min_value=0, value=tgt_default, step=1, key=f"target_{i}")
                    targets.append(int(tgt))

                items.append({
                    "name": name,
                    "required": int(required),
                    "minutes": float(minutes_per),
                    "assigned": int(assigned),
                    "current_price": float(current_price),
                })

        total_assigned = sum(it["assigned"] for it in items)
        used_minutes_raw = total_assigned * workshop_hours * 60.0
        used_minutes_planned = used_minutes_raw * output_scale
        st.markdown(f"**Planned used Labour minutes @ {prisoner_output}%:** {used_minutes_planned:,.0f}")

        if pricing_mode_key == "as-is" and used_minutes_planned > budget_minutes_planned:
            st.error("Planned used minutes exceed planned available minutes.")
        else:
            if st.button("Generate Production Costs", key="generate_contractual"):
                errs = validate_inputs()
                for i, it in enumerate(items):
                    if it["minutes"] <= 0:
                        errs.append(f"Item {i+1}: Time per item must be > 0")
                if errs:
                    st.error("Fix errors:\n- " + "\n- ".join(errs))
                else:
                    # === 1) Combined view (the standard one) ===
                    results = calculate_production_contractual(
                        items, int(prisoner_output),
                        workshop_hours=float(workshop_hours),
                        prisoner_salary=float(prisoner_salary),
                        supervisor_salaries=supervisor_salaries,
                        effective_pct=float(instructor_pct),
                        customer_covers_supervisors=customer_covers_supervisors,
                        region=region,
                        customer_type="Commercial",
                        apply_vat=True, vat_rate=20.0,
                        num_prisoners=int(num_prisoners),
                        num_supervisors=int(num_supervisors),
                        dev_rate=_dev_rate_from_support(employment_support),
                        pricing_mode=pricing_mode_key,
                        targets=targets if pricing_mode_key == "target" else None,
                        lock_overheads=lock_overheads,
                        employment_support=employment_support,
                        recommended_allocation=recommended_pct,
                    )

                    display_cols = ["Item", "Output %", "Capacity (units/week)", "Units/week",
                                    "Unit Cost (£)", "Unit Price ex VAT (£)", "Unit Price inc VAT (£)",
                                    "Monthly Total ex VAT (£)", "Monthly Total inc VAT (£)"]
                    if pricing_mode_key == "target":
                        display_cols += ["Feasible", "Note"]

                    prod_df_combined = pd.DataFrame([{
                        k: (None if r.get(k) is None else (round(float(r.get(k)), 2) if isinstance(r.get(k), (int, float)) else r.get(k)))
                        for k in display_cols
                    } for r in results])

                    # === 2) Segregated view (exclude instructor from per-item unit price) ===
                    # Instructor weekly total (per workshop; divide by contracts)
                    if customer_covers_supervisors:
                        inst_weekly_total = 0.0
                    else:
                        inst_weekly_total = sum((s / 52.0) * (float(instructor_pct) / 100.0) for s in supervisor_salaries) / float(contracts)

                    # Overhead base uses instructor (or shadow if customer provides), with lock option
                    if customer_covers_supervisors:
                        shadow = BAND3_COSTS.get(region, 42247.81)
                        overhead_base_weekly = (shadow / 52.0) * (float(instructor_pct) / 100.0)
                    else:
                        if lock_overheads and supervisor_salaries:
                            base = max(supervisor_salaries)
                            overhead_base_weekly = (base / 52.0) * (float(instructor_pct) / 100.0)
                        else:
                            overhead_base_weekly = inst_weekly_total

                    overheads_weekly_total = overhead_base_weekly * 0.61
                    dev_weekly_total = overheads_weekly_total * _dev_rate_from_support(employment_support)

                    denom = sum(int(it.get("assigned", 0)) * float(workshop_hours) * 60.0 for it in items)
                    output_scale = float(prisoner_output) / 100.0

                    rows = []
                    for idx, it in enumerate(items):
                        name = (it.get("name") or "").strip() or f"Item {idx+1}"
                        mins_per_unit = float(it.get("minutes", 0))
                        pris_required = int(it.get("required", 1))
                        pris_assigned = int(it.get("assigned", 0))

                        # capacity and chosen units
                        if pris_assigned > 0 and mins_per_unit > 0 and pris_required > 0 and workshop_hours > 0:
                            cap_100 = (pris_assigned * float(workshop_hours) * 60.0) / (mins_per_unit * pris_required)
                        else:
                            cap_100 = 0.0
                        capacity_units = cap_100 * output_scale

                        if pricing_mode_key == "target":
                            tgt = int(targets[idx]) if (targets and idx < len(targets)) else 0
                            units_for_pricing = float(tgt)
                        else:
                            units_for_pricing = capacity_units

                        share = ((pris_assigned * float(workshop_hours) * 60.0) / denom) if denom > 0 else 0.0

                        prisoner_weekly_item = pris_assigned * float(prisoner_salary)
                        overheads_weekly_item = overheads_weekly_total * share
                        dev_weekly_item = dev_weekly_total * share

                        weekly_cost_excl_inst = prisoner_weekly_item + overheads_weekly_item + dev_weekly_item
                        unit_cost_excl_inst = (weekly_cost_excl_inst / units_for_pricing) if units_for_pricing > 0 else None
                        unit_price_ex_vat = unit_cost_excl_inst
                        unit_price_inc_vat = (unit_price_ex_vat * 1.20) if unit_price_ex_vat is not None else None

                        monthly_total_ex_vat = (units_for_pricing * unit_price_ex_vat * 52 / 12) if unit_price_ex_vat else None
                        monthly_total_inc_vat = (units_for_pricing * unit_price_inc_vat * 52 / 12) if unit_price_inc_vat else None

                        rows.append({
                            "Item": name,
                            "Output %": int(prisoner_output),
                            "Capacity (units/week)": 0 if capacity_units <= 0 else int(round(capacity_units)),
                            "Units/week": 0 if units_for_pricing <= 0 else int(round(units_for_pricing)),
                            "Unit Cost (£)": unit_cost_excl_inst,
                            "Unit Price ex VAT (£)": unit_price_ex_vat,
                            "Unit Price inc VAT (£)": unit_price_inc_vat,
                            "Monthly Total ex VAT (£)": monthly_total_ex_vat,
                            "Monthly Total inc VAT (£)": monthly_total_inc_vat,
                        })

                    prod_df_segregated = pd.DataFrame(rows)
                    monthly_inst_total = (inst_weekly_total * 52.0 / 12.0) if inst_weekly_total else 0.0

                    # Save both for display/exports
                    st.session_state["prod_df_combined"] = prod_df_combined
                    st.session_state["prod_df_segregated"] = prod_df_segregated
                    st.session_state["prod_monthly_inst"] = monthly_inst_total

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

                unit = st.radio("Input time unit", ["Minutes", "Seconds"], index=0, key=f"adhoc_unit_{i}", horizontal=True)
                time_value = st.number_input("Time to make one (per selected unit)", min_value=0.0, value=0.10 if unit=="Minutes" else 6.0, format="%.2f", key=f"adhoc_time_{i}")
                minutes_per_item = time_value if unit == "Minutes" else (time_value / 60.0)

                lines.append({
                    "name": (item_name.strip() or f"Item {i+1}") if isinstance(item_name, str) else f"Item {i+1}",
                    "units": int(units_requested),
                    "deadline": deadline,
                    "pris_per_item": int(pris_per_item),
                    "mins_per_item": float(minutes_per_item),
                })

        if st.button("Generate Ad-hoc Costs", key="generate_adhoc"):
            errs = validate_inputs()
            if workshop_hours <= 0: errs.append("Hours per week must be > 0 for Ad-hoc")
            for i, ln in enumerate(lines):
                if ln["units"] <= 0: errs.append(f"Line {i+1}: Units requested must be > 0")
                if ln["pris_per_item"] <= 0: errs.append(f"Line {i+1}: Prisoners to make one must be > 0")
                if ln["mins_per_item"] <= 0: errs.append(f"Line {i+1}: Minutes to make one must be > 0")
            if errs:
                st.error("Fix errors:\n- " + "\n- ".join(errs))
            else:
                result = calculate_adhoc(
                    lines, int(prisoner_output),
                    workshop_hours=float(workshop_hours),
                    num_prisoners=int(num_prisoners),
                    prisoner_salary=float(prisoner_salary),
                    supervisor_salaries=supervisor_salaries,
                    effective_pct=float(instructor_pct),
                    customer_covers_supervisors=customer_covers_supervisors,
                    region=region,
                    customer_type="Commercial",
                    apply_vat=True, vat_rate=20.0,
                    dev_rate=_dev_rate_from_support(employment_support),
                    today=date.today(),
                    lock_overheads=lock_overheads,
                    employment_support=employment_support,
                    recommended_allocation=recommended_pct,
                )
                if result["feasibility"]["hard_block"]:
                    st.error(result["feasibility"]["reason"])
                else:
                    df, totals = build_adhoc_table(result)
                    # For Ad-hoc we keep a single table (combined logic)
                    st.session_state["prod_df_combined"] = df
                    st.session_state["prod_df_segregated"] = None
                    st.session_state["prod_monthly_inst"] = None

    # Common Production display + downloads (both views)
    if "prod_df_combined" in st.session_state and isinstance(st.session_state["prod_df_combined"], pd.DataFrame):
        df_combined = st.session_state["prod_df_combined"]
        df_segregated = st.session_state.get("prod_df_segregated")
        monthly_inst = st.session_state.get("prod_monthly_inst")

        st.markdown("### Production – Combined Costs")
        st.markdown(render_table_html(df_combined), unsafe_allow_html=True)

        if isinstance(df_segregated, pd.DataFrame):
            st.markdown("### Production – Instructor Segregated")
            if monthly_inst is not None:
                st.info(f"Monthly Instructor Salary (segregated): **{fmt_currency(monthly_inst)}**")
            st.markdown(render_table_html(df_segregated, highlight=True), unsafe_allow_html=True)

        # Downloads
        header_kwargs = dict(
            prison_name=prison_choice,
            region=region,
            customer_name=customer_name,
            uk_date=_uk_date(date.today()),
        )

        # CSV — flatten both (add a View column)
        common = {
            "Date": _uk_date(date.today()),
            "Customer": customer_name,
            "Prison": prison_choice,
            "Region": region,
            "Contract Type": "Production",
            "Hours/week": workshop_hours,
            "Prisoners": num_prisoners,
            "Prisoner salary/week (£)": prisoner_salary,
            "Instructors": num_supervisors,
            "Customer provides Instructors": "Yes" if customer_covers_supervisors else "No",
            "Instructor allocation (%)": instructor_pct,
            "Recommended allocation (%)": recommended_pct,
            "Contracts overseen": contracts,
            "Employment support": employment_support,
            "Lock overheads": "Yes" if lock_overheads else "No",
            "Output %": prisoner_output,
        }
        rows = []
        # Combined rows
        if "Item" in df_combined.columns:
            for _, r in df_combined.iterrows():
                rows.append({
                    **common,
                    "View": "Combined",
                    "Item": r.get("Item"),
                    "Capacity (units/week)": r.get("Capacity (units/week)"),
                    "Units/week": r.get("Units/week"),
                    "Unit Cost (ex VAT £)": r.get("Unit Cost (£)"),
                    "Unit Price (ex VAT £)": r.get("Unit Price ex VAT (£)"),
                    "Unit Price (inc VAT £)": r.get("Unit Price inc VAT (£)"),
                    "Monthly Total (ex VAT £)": r.get("Monthly Total ex VAT (£)"),
                    "Monthly Total (inc VAT £)": r.get("Monthly Total inc VAT (£)"),
                })
        # Segregated rows (if any)
        if isinstance(df_segregated, pd.DataFrame) and "Item" in df_segregated.columns:
            for _, r in df_segregated.iterrows():
                rows.append({
                    **common,
                    "View": "Segregated",
                    "Item": r.get("Item"),
                    "Capacity (units/week)": r.get("Capacity (units/week)"),
                    "Units/week": r.get("Units/week"),
                    "Unit Cost (ex VAT £)": r.get("Unit Cost (£)"),
                    "Unit Price (ex VAT £)": r.get("Unit Price ex VAT (£)"),
                    "Unit Price (inc VAT £)": r.get("Unit Price inc VAT (£)"),
                    "Monthly Total (ex VAT £)": r.get("Monthly Total ex VAT (£)"),
                    "Monthly Total (inc VAT £)": r.get("Monthly Total inc VAT (£)"),
                    "Monthly Instructor Salary (£)": monthly_inst,
                })
        csv_prod = pd.DataFrame(rows)

        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "Download CSV (Production)",
                data=export_csv_bytes(csv_prod),
                file_name="production_quote.csv",
                mime="text/csv"
            )
        with c2:
            st.download_button(
                "Download PDF-ready HTML (Production)",
                data=export_html(
                    None, df_combined, title="Production Quote", **header_kwargs,
                    df_prod_segregated=df_segregated, monthly_instructor_salary=monthly_inst
                ),
                file_name="production_quote.html",
                mime="text/html"
            )