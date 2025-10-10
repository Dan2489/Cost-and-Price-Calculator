import streamlit as st
import pandas as pd
from datetime import date

from config61 import CFG
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
from utils61 import (
    inject_govuk_css, sidebar_controls, fmt_currency,
    export_csv_bytes, export_html, render_table_html,
    recompute_host_for_allocation, build_prod_comparison
)
from production61 import (
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
# Sidebar (no productivity slider)
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
            # Prefer Subtotal (ex VAT)
            mask_sub = df["Item"].astype(str).str.contains("^Subtotal$", case=False, na=False)
            if mask_sub.any():
                val = pd.to_numeric(df.loc[mask_sub, "Amount (£)"], errors="coerce").dropna()
                if not val.empty:
                    return float(val.iloc[-1])
            # Fallback: sum 'Monthly Total ex VAT' style columns
        for col in ["Monthly Total ex VAT (£)", "Monthly Total (ex VAT £)", "Monthly Total (£)"]:
            if col in df.columns:
                return float(pd.to_numeric(df[col], errors="coerce").fillna(0).sum())
    except Exception:
        pass
    return 0.0

def _recommended_allocation(workshop_hours: float, contracts: int) -> int:
    try:
        base = (float(workshop_hours) / 37.5) * (1.0 / max(1, int(contracts))) * 100.0
        return max(0, min(100, int(round(base))))
    except Exception:
        return 100

def _append_recommendation_blurb():
    rec = _recommended_allocation(workshop_hours, contracts)
    st.caption(
        f"**Instructor allocation recommendation:** {rec}% "
        f"(based on {workshop_hours:.2f} hours/week and {contracts} contract{'s' if contracts!=1 else ''}). "
        f"Use the sidebar to change."
    )

# -------------------------------
# HOST
# -------------------------------
if contract_type == "Host":
    _append_recommendation_blurb()

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

    if "host_df" in st.session_state:
        df = st.session_state["host_df"]
        if customer_covers_supervisors and "Item" in df.columns:
            df = df[~df["Item"].astype(str).str.contains("Instructor Salary", na=False)]

        # Highlight Development Charge reductions in red
        if "Item" in df.columns:
            df_display = df.copy()
            df_display["Item"] = df_display["Item"].apply(
                lambda x: f"<span style='color:red'>{x}</span>" if "Reduction" in str(x) else x
            )
            st.markdown(render_table_html(df_display), unsafe_allow_html=True)
        else:
            st.markdown(render_table_html(df), unsafe_allow_html=True)

        # ---- Allocation comparison block (Host) ----
        st.markdown("### Instructor allocation comparison (Host)")
        rec_pct = _recommended_allocation(workshop_hours, contracts)
        comp_rows = []
        for label, pct in [
            (f"Current ({instructor_pct}%)", instructor_pct),
            (f"Recommended ({rec_pct}%)", rec_pct),
            ("50%", 50),
            ("25%", 25),
        ]:
            df_cmp, total_cmp_ex = recompute_host_for_allocation(
                base_inputs=dict(
                    workshop_hours=workshop_hours,
                    num_prisoners=num_prisoners,
                    prisoner_salary=prisoner_salary,
                    num_supervisors=num_supervisors,
                    customer_covers_supervisors=customer_covers_supervisors,
                    supervisor_salaries=supervisor_salaries,
                    region=region,
                    contracts=contracts,
                    employment_support=employment_support,
                    lock_overheads=lock_overheads,
                ),
                allocation_pct=pct
            )
            comp_rows.append([label, fmt_currency(total_cmp_ex)])
        comp_df_host = pd.DataFrame(comp_rows, columns=["Instructor Allocation", "Monthly Grand Total (ex VAT)"])
        st.markdown(render_table_html(comp_df_host), unsafe_allow_html=True)

        # Downloads
        c1, c2 = st.columns(2)
        with c1:
            st.download_button("Download CSV (Host)", data=export_csv_bytes(df), file_name="host_quote.csv", mime="text/csv")
        with c2:
            st.download_button(
                "Download PDF-ready HTML (Host)",
                data=export_html(
                    df_host=df,
                    df_prod=None,
                    title="Host Quote",
                    extra_note=None,
                    adjusted_df=None,
                    meta=dict(
                        customer=customer_name,
                        prison=prison_choice,
                        region=region,
                        today=date.today()
                    ),
                    comparison={
                        "Host": comp_df_host,
                        "Production_totals": None,
                        "Production_units": None
                    }
                ),
                file_name="host_quote.html",
                mime="text/html"
            )

# -------------------------------
# PRODUCTION
# -------------------------------
if contract_type == "Production":
    _append_recommendation_blurb()

    st.markdown("---")
    st.subheader("Production settings")

    # Labour minutes info
    output_scale = float(prisoner_output) / 100.0
    budget_minutes_raw = labour_minutes_budget(int(num_prisoners), float(workshop_hours))
    budget_minutes_planned = budget_minutes_raw * output_scale
    st.info(f"Available Labour minutes per week @ {prisoner_output}% = **{budget_minutes_planned:,.0f} minutes**.")

    prod_mode = st.radio("Do you want contractual or ad-hoc costs?", ["Contractual", "Ad-hoc"], index=0)

    if prod_mode == "Contractual":
        pricing_mode = st.radio("Price based on:", ["Maximum units from capacity", "Target units per week"], index=0)
        pricing_mode_key = "as-is" if pricing_mode.startswith("Maximum") else "target"

        num_items = st.number_input("Number of items produced?", min_value=1, value=1, step=1, key="num_items_prod")
        items, targets, current_prices = [], [], []

        for i in range(int(num_items)):
            with st.expander(f"Item {i+1} details", expanded=(i == 0)):
                name = st.text_input(f"Item {i+1} Name", key=f"name_{i}")
                disp = (name.strip() or f"Item {i+1}") if isinstance(name, str) else f"Item {i+1}"
                required = st.number_input(
                    f"Prisoners required to make 1 item ({disp})",
                    min_value=1, value=1, step=1, key=f"req_{i}"
                )
                minutes_per = st.number_input(
                    f"How many minutes to make 1 item ({disp})",
                    min_value=0.0, value=10.0, format="%.2f", key=f"mins_{i}",
                    help="Enter minutes as decimals (e.g., 0.5 = 30 seconds)."
                )
                current_unit_price = st.number_input(
                    f"Current price per unit (ex VAT) — optional ({disp})",
                    min_value=0.0, value=0.0, format="%.2f", key=f"curr_{i}"
                )

                total_assigned_before = sum(int(st.session_state.get(f"assigned_{j}", 0)) for j in range(i))
                remaining = max(0, int(num_prisoners) - total_assigned_before)
                assigned = st.number_input(
                    f"How many prisoners work solely on this item ({disp})",
                    min_value=0, max_value=remaining, value=int(st.session_state.get(f"assigned_{i}", 0)),
                    step=1, key=f"assigned_{i}"
                )

                if assigned > 0 and minutes_per > 0 and required > 0 and workshop_hours > 0:
                    cap_100 = (assigned * workshop_hours * 60.0) / (minutes_per * required)
                else:
                    cap_100 = 0.0
                cap_planned = cap_100 * output_scale
                st.caption(f"{disp} capacity @ 100%: **{cap_100:.0f} units/week** · @ {prisoner_output}%: **{cap_planned:.0f}**")

                if pricing_mode_key == "target":
                    tgt_default = int(round(cap_planned)) if cap_planned > 0 else 0
                    tgt = st.number_input(f"Target units per week ({disp})", min_value=0, value=tgt_default, step=1, key=f"target_{i}")
                    targets.append(int(tgt))

                items.append({"name": name, "required": int(required), "minutes": float(minutes_per), "assigned": int(assigned)})
                current_prices.append(float(current_unit_price))

        total_assigned = sum(it["assigned"] for it in items)
        used_minutes_raw = total_assigned * workshop_hours * 60.0
        used_minutes_planned = used_minutes_raw * output_scale
        st.markdown(f"**Planned used Labour minutes @ {prisoner_output}%:** {used_minutes_planned:,.0f}")

        if pricing_mode_key == "as-is" and used_minutes_planned > budget_minutes_planned:
            st.error("Planned used minutes exceed planned available minutes.")
        else:
            if st.button("Generate Production Costs", key="generate_contractual"):
                errs = validate_inputs()
                if errs:
                    st.error("Fix errors:\n- " + "\n- ".join(errs))
                else:
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
                        dev_rate=0.0,
                        pricing_mode=pricing_mode_key,
                        targets=targets if pricing_mode_key == "target" else None,
                        lock_overheads=lock_overheads,
                        employment_support=employment_support,
                    )
                    display_cols = ["Item", "Output %", "Capacity (units/week)", "Units/week",
                                    "Unit Cost (£)", "Unit Price ex VAT (£)", "Unit Price inc VAT (£)",
                                    "Monthly Total ex VAT (£)", "Monthly Total inc VAT (£)"]
                    if pricing_mode_key == "target":
                        display_cols += ["Feasible", "Note"]

                    prod_df = pd.DataFrame([{
                        k: (None if results[idx].get(k) is None else
                            (round(float(results[idx].get(k)), 2) if isinstance(results[idx].get(k), (int, float)) else results[idx].get(k)))
                        for k in display_cols
                    } for idx in range(len(results))])

                    # Attach optional current prices and uplift %
                    if len(current_prices) == len(prod_df):
                        prod_df["Current Price ex VAT (£)"] = [None if p <= 0 else round(p, 2) for p in current_prices]
                        def _uplift(row):
                            curr = row.get("Current Price ex VAT (£)")
                            model = row.get("Unit Price ex VAT (£)")
                            try:
                                if curr is None or float(curr) <= 0:
                                    return ""
                                return round((float(model) - float(curr)) / float(curr) * 100.0, 1)
                            except Exception:
                                return ""
                        prod_df["Uplift vs Current (%)"] = prod_df.apply(_uplift, axis=1)

                    st.session_state["prod_df"] = prod_df

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
                with c5: minutes_per_item = st.number_input(
                    "Minutes to make one", min_value=0.0, value=10.0, format="%.2f", key=f"adhoc_mins_{i}",
                    help="Enter minutes as decimals (e.g., 0.5 = 30 seconds)."
                )
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
                if ln["mins_per_item"] < 0: errs.append(f"Line {i+1}: Minutes to make one must be ≥ 0")
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
                    dev_rate=0.0,
                    today=date.today(),
                    lock_overheads=lock_overheads,
                    employment_support=employment_support,
                )
                if result["feasibility"]["hard_block"]:
                    st.error(result["feasibility"]["reason"])
                else:
                    df, totals = build_adhoc_table(result)
                    st.session_state["prod_df"] = df

    if "prod_df" in st.session_state and isinstance(st.session_state["prod_df"], pd.DataFrame):
        df = st.session_state["prod_df"]
        if customer_covers_supervisors and "Item" in df.columns:
            df = df[~df["Item"].astype(str).str.contains("Instructor Salary", na=False)]
        st.markdown(render_table_html(df), unsafe_allow_html=True)

        # ---- Allocation comparison block (Production) ----
        st.markdown("### Instructor allocation comparison (Production)")
        rec_pct = _recommended_allocation(workshop_hours, contracts)
        comp_totals_df, comp_units_df = build_prod_comparison(
            df=df,
            current_allocation_pct=instructor_pct,
            scenarios=[
                ("Current", instructor_pct),
                ("Recommended", rec_pct),
                ("50%", 50),
                ("25%", 25),
            ]
        )
        st.markdown("#### Scenario totals (ex VAT)")
        st.markdown(render_table_html(comp_totals_df), unsafe_allow_html=True)
        if comp_units_df is not None and not comp_units_df.empty:
            st.markdown("#### Unit prices (ex VAT) and uplift vs current")
            st.markdown(render_table_html(comp_units_df), unsafe_allow_html=True)

        # Downloads
        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "Download CSV (Production)",
                data=export_csv_bytes(df),
                file_name="production_quote.csv",
                mime="text/csv"
            )
        with c2:
            st.download_button(
                "Download PDF-ready HTML (Production)",
                data=export_html(
                    df_host=None,
                    df_prod=df,
                    title="Production Quote",
                    extra_note=None,
                    adjusted_df=None,
                    meta=dict(
                        customer=customer_name,
                        prison=prison_choice,
                        region=region,
                        today=date.today()
                    ),
                    comparison={
                        "Host": None,
                        "Production_totals": comp_totals_df,
                        "Production_units": comp_units_df
                    }
                ),
                file_name="production_quote.html",
                mime="text/html"
            )