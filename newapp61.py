import streamlit as st
import pandas as pd
from datetime import date

from config61 import CFG
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
from utils61 import (
    inject_govuk_css, sidebar_controls, fmt_currency,
    export_csv_bytes, export_html, render_table_html,
    build_flat_rows_for_csv
)
from production61 import (
    labour_minutes_budget,
    calculate_production_contractual,
    calculate_adhoc,
    build_adhoc_table,
    BAND3_COSTS  # to replicate monthly breakdown for comparisons
)
import host61

# -------------------------------
# Page setup
# -------------------------------
st.set_page_config(page_title="Cost and Price Calculator", page_icon="💷", layout="centered")
inject_govuk_css()
st.title("Cost and Price Calculator")

LEGAL_BLOCK = (
    "We are pleased to set out below the terms of our Quotation for the Goods and/or Services you are "
    "currently seeking. We confirm that this Quotation and any subsequent contract entered into as a result "
    "is, and will be, subject exclusively to our Standard Conditions of Sale of Goods and/or Services a copy "
    "of which is available on request. Please note that all prices are exclusive of VAT and carriage costs at "
    "time of order of which the customer shall be additionally liable to pay."
)

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

# Recommended instructor %
rec_pct = 100.0
if workshop_hours > 0 and contracts > 0:
    rec_pct = min(100.0, round((37.5 / (float(workshop_hours) * float(contracts))) * 100.0, 1))
st.caption(f"**Recommended Instructor allocation:** {rec_pct:.1f}% (based on hours open and contracts)")

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
        for col in ["Monthly Total inc VAT (£)", "Monthly Total (inc VAT £)", "Monthly Total (£)", "Monthly Total ex VAT (£)"]:
            if col in df.columns:
                return float(pd.to_numeric(df[col], errors="coerce").fillna(0).sum())
    except Exception:
        pass
    return 0.0

def _meta_lines():
    return [
        f"Date: {date.today().strftime('%d/%m/%Y')}",
        f"Customer: {customer_name or '-'}",
        f"Prison: {prison_choice or '-'}",
        f"Region: {region or '-'}",
    ]

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

    if "host_df" in st.session_state:
        df = st.session_state["host_df"]
        if customer_covers_supervisors:
            df = df[~df["Item"].str.contains("Instructor Salary", na=False)]

        st.markdown(render_table_html(df), unsafe_allow_html=True)

        # --- Build comparison tables for HTML (Host) ---
        # We can reuse df's numbers by scaling instructor % to 100 / rec / 50 / 25
        scenarios = [
            ("100%", 100.0),
            (f"Recommended ({rec_pct:.1f}%)", rec_pct),
            ("50%", 50.0),
            ("25%", 25.0),
        ]

        # To produce monthly breakdown, recompute core components for each scenario
        def _host_components(pct: float):
            # Prisoner wages monthly
            wages_m = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)
            # Instructor monthly (if not covered)
            if customer_covers_supervisors:
                inst_m = 0.0
                # Shadow base when customer covers supervisors
                shadow = BAND3_COSTS.get(region, BAND3_COSTS.get("National", 42247.81))
                overhead_base_w = (shadow / 52.0) * (pct / 100.0)
            else:
                weekly_inst = sum((s / 52.0) * (pct / 100.0) for s in supervisor_salaries)
                inst_m = weekly_inst * (52.0 / 12.0)
                overhead_base_w = weekly_inst
                if lock_overheads and supervisor_salaries:
                    highest = max(supervisor_salaries) / 52.0 * (pct / 100.0)
                    overhead_base_w = highest
            overhead_m = overhead_base_w * 0.61 * (52.0 / 12.0)
            dev_m = 0.0  # host dev shown separately inside host code when relevant; here keep 0 for comparison
            total_m = wages_m + inst_m + overhead_m + dev_m
            return inst_m, overhead_m, dev_m, wages_m, total_m

        comp_month_rows = []
        for label, pct in scenarios:
            inst_m, over_m, dev_m, wages_m, total_m = _host_components(pct)
            comp_month_rows.append({
                "Scenario": label,
                "Instructor Cost (£)": inst_m,
                "Overhead (£)": over_m,
                "Development (£)": dev_m,
                "Prisoner Wages (£)": wages_m,
                "Total Monthly ex VAT (£)": total_m,
                "Current Monthly (£)": "",  # host has no "current unit"
            })
        comp_month_df_host = pd.DataFrame(comp_month_rows)

        # Unit comp table (no "current unit" applicable to host -> leave blank)
        comp_unit_df_host = pd.DataFrame([
            {
                "Scenario": label,
                "Current Unit Price (£)": "",
                "Instructor % to Reach Current": "",
                "New Unit Price (£)": "",
                "Uplift vs Current (%)": ""
            } for label, _ in scenarios
        ])

        # HTML + CSV export
        meta = {
            "Date": date.today().strftime("%d/%m/%Y"),
            "Customer": customer_name,
            "Prison": prison_choice,
            "Region": region,
            "Contract Type": "Host",
        }

        flat_csv_df = build_flat_rows_for_csv(
            meta=meta,
            base_df=df,
            comp_unit_df=comp_unit_df_host,
            comp_month_df=comp_month_df_host
        )

        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "Download CSV (Host)",
                data=export_csv_bytes(flat_csv_df),
                file_name="host_quote.csv",
                mime="text/csv"
            )
        with c2:
            html_doc = export_html(
                df_host=df, df_prod=None,
                title="Host Quote",
                meta_lines=_meta_lines(),
                legal_block=LEGAL_BLOCK,
                comp1_html=render_table_html(comp_unit_df_host, highlight=True),
                comp2_html=render_table_html(comp_month_df_host, highlight=True),
            )
            st.download_button(
                "Download PDF-ready HTML (Host)",
                data=html_doc,
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

    # ---------- Contractual ----------
    if prod_mode == "Contractual":
        pricing_mode = st.radio("Price based on:", ["Maximum units from capacity", "Target units per week"], index=0)
        pricing_mode_key = "as-is" if pricing_mode.startswith("Maximum") else "target"

        num_items = st.number_input("Number of items produced?", min_value=1, value=1, step=1, key="num_items_prod")
        items, targets = [], []
        current_prices = []

        for i in range(int(num_items)):
            with st.expander(f"Item {i+1} details", expanded=(i == 0)):
                name = st.text_input(f"Item {i+1} Name", key=f"name_{i}")
                disp = (name.strip() or f"Item {i+1}") if isinstance(name, str) else f"Item {i+1}"
                required = st.number_input(f"Prisoners required to make 1 item ({disp})", min_value=1, value=1, key=f"req_{i}")

                u = st.radio(f"Input unit for production time ({disp})", ["Minutes", "Seconds"], index=0, key=f"unit_{i}")
                if u == "Minutes":
                    minutes_per = st.number_input(f"How long to make 1 item ({disp}) (minutes)", min_value=0.0, value=1.0, step=0.01, key=f"mins_{i}")
                else:
                    seconds = st.number_input(f"How long to make 1 item ({disp}) (seconds)", min_value=0.0, value=30.0, step=0.5, key=f"secs_{i}")
                    minutes_per = float(seconds) / 60.0

                total_assigned_before = sum(int(st.session_state.get(f"assigned_{j}", 0)) for j in range(i))
                remaining = max(0, int(num_prisoners) - total_assigned_before)
                assigned = st.number_input(
                    f"How many prisoners work solely on this item ({disp})",
                    min_value=0, max_value=remaining, value=int(st.session_state.get(f"assigned_{i}", 0)),
                    step=1, key=f"assigned_{i}"
                )

                cur_price = st.number_input(f"Current price per unit (£) ({disp})", min_value=0.0, value=0.0, step=0.01, key=f"cur_{i}")
                current_prices.append(float(cur_price))

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

                    prod_df = pd.DataFrame([{k: (None if r.get(k) is None else (round(float(r.get(k)), 2) if isinstance(r.get(k), (int, float)) else r.get(k)))
                                             for k in display_cols} for r in results])
                    # Save plus extra context needed for comparisons
                    st.session_state["prod_df"] = prod_df
                    st.session_state["prod_items"] = items
                    st.session_state["prod_targets"] = targets if pricing_mode_key == "target" else None
                    st.session_state["prod_current_prices"] = current_prices
                    st.session_state["prod_mode_key"] = pricing_mode_key

    # ---------- Ad-hoc ----------
    else:
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
                with c5:
                    unit_sel = st.radio("Input unit for production time", ["Minutes", "Seconds"], index=0, key=f"adhoc_unit_{i}")
                    if unit_sel == "Minutes":
                        minutes_per_item = st.number_input("Minutes to make one", min_value=0.0, value=10.0, step=0.01, key=f"adhoc_mins_{i}")
                    else:
                        secs = st.number_input("Seconds to make one", min_value=0.0, value=30.0, step=0.5, key=f"adhoc_secs_{i}")
                        minutes_per_item = float(secs) / 60.0
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
                    st.session_state["prod_items"] = None
                    st.session_state["prod_targets"] = None
                    st.session_state["prod_current_prices"] = None
                    st.session_state["prod_mode_key"] = "adhoc"

    # ---------- Shared after-generation UI ----------
    if "prod_df" in st.session_state and isinstance(st.session_state["prod_df"], pd.DataFrame):
        df = st.session_state["prod_df"]
        if customer_covers_supervisors and "Item" in df.columns:
            df = df[~df["Item"].astype(str).str.contains("Instructor Salary", na=False)]
        st.markdown(render_table_html(df), unsafe_allow_html=True)

        # -------- Comparison tables (Production, contractual only) --------
        comp_unit_df = None
        comp_month_df = None

        if st.session_state.get("prod_mode_key") in ("as-is", "target"):
            # Weighted unit price (new) and current
            try:
                units = pd.to_numeric(df["Units/week"], errors="coerce").fillna(0)
                unit_px = pd.to_numeric(df["Unit Price ex VAT (£)"], errors="coerce").fillna(0)
                new_unit_price = (units * unit_px).sum() / max(1.0, units.sum())
            except Exception:
                new_unit_price = pd.to_numeric(df.get("Unit Price ex VAT (£)"), errors="coerce").fillna(0).mean()

            # Current unit price (weighted by targets if present, else equal weight)
            cur_prices = st.session_state.get("prod_current_prices") or []
            if cur_prices:
                if st.session_state.get("prod_targets"):
                    weights = pd.Series(st.session_state["prod_targets"], dtype="float")
                else:
                    weights = pd.Series([1.0] * len(cur_prices), dtype="float")
                current_unit_price = (weights * pd.Series(cur_prices, dtype="float")).sum() / max(1.0, weights.sum())
            else:
                current_unit_price = None

            def uplift(new_p, cur_p):
                if cur_p is None or cur_p <= 0:
                    return ""
                return round((float(new_p) / float(cur_p) - 1.0) * 100.0, 2)

            scenarios = [
                ("100%", 100.0),
                (f"Recommended ({rec_pct:.1f}%)", rec_pct),
                ("50%", 50.0),
                ("25%", 25.0),
            ]

            # For unit price under different % we change only instructor + overhead components.
            # Approximate by recalculating monthly components and then deriving unit as:
            # (Total Monthly ex VAT / Monthly units)  with monthly units = sum(Units/week) * 52/12
            sum_units_week = pd.to_numeric(df["Units/week"], errors="coerce").fillna(0).sum()
            monthly_units = sum_units_week * (52.0 / 12.0)

            def monthly_components(pct: float):
                # wages
                wages_m = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)
                # instructor + overhead base
                if customer_covers_supervisors:
                    inst_m = 0.0
                    shadow = BAND3_COSTS.get(region, BAND3_COSTS.get("National", 42247.81))
                    overhead_base_w = (shadow / 52.0) * (pct / 100.0)
                else:
                    weekly_inst = sum((s / 52.0) * (pct / 100.0) for s in supervisor_salaries)
                    inst_m = weekly_inst * (52.0 / 12.0)
                    overhead_base_w = weekly_inst
                    if lock_overheads and supervisor_salaries:
                        highest = max(supervisor_salaries) / 52.0 * (pct / 100.0)
                        overhead_base_w = highest
                over_m = overhead_base_w * 0.61 * (52.0 / 12.0)
                dev_m = 0.0  # as per earlier prod settings
                total_m = wages_m + inst_m + over_m + dev_m
                return inst_m, over_m, dev_m, wages_m, total_m

            comp_rows_unit = []
            comp_rows_month = []
            for label, pct in scenarios:
                inst_m, over_m, dev_m, wages_m, total_m = monthly_components(pct)
                if monthly_units > 0:
                    new_unit_p = total_m / monthly_units
                else:
                    new_unit_p = new_unit_price  # fallback

                comp_rows_unit.append({
                    "Scenario": label,
                    "Current Unit Price (£)": "" if current_unit_price is None else current_unit_price,
                    "Instructor % to Reach Current": "" if current_unit_price is None else f"{pct:.1f}%" if abs(new_unit_p - current_unit_price) < 1e-6 else "",
                    "New Unit Price (£)": new_unit_p,
                    "Uplift vs Current (%)": "" if current_unit_price is None else uplift(new_unit_p, current_unit_price),
                })
                comp_rows_month.append({
                    "Scenario": label,
                    "Instructor Cost (£)": inst_m,
                    "Overhead (£)": over_m,
                    "Development (£)": dev_m,
                    "Prisoner Wages (£)": wages_m,
                    "Total Monthly ex VAT (£)": total_m,
                    "Current Monthly (£)": "" if current_unit_price is None else (current_unit_price * sum_units_week * (52.0 / 12.0)),
                })

            comp_unit_df = pd.DataFrame(comp_rows_unit)
            comp_month_df = pd.DataFrame(comp_rows_month)

        # ---- Exports (Production) ----
        meta = {
            "Date": date.today().strftime("%d/%m/%Y"),
            "Customer": customer_name,
            "Prison": prison_choice,
            "Region": region,
            "Contract Type": "Production",
        }

        flat_csv_df = build_flat_rows_for_csv(
            meta=meta,
            base_df=df,
            comp_unit_df=comp_unit_df,
            comp_month_df=comp_month_df
        )

        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "Download CSV (Production)",
                data=export_csv_bytes(flat_csv_df),
                file_name="production_quote.csv",
                mime="text/csv"
            )
        with c2:
            html_doc = export_html(
                df_host=None, df_prod=df,
                title="Production Quote",
                meta_lines=_meta_lines(),
                legal_block=LEGAL_BLOCK,
                comp1_html=None if comp_unit_df is None else render_table_html(comp_unit_df, highlight=True),
                comp2_html=None if comp_month_df is None else render_table_html(comp_month_df, highlight=True),
            )
            st.download_button(
                "Download PDF-ready HTML (Production)",
                data=html_doc,
                file_name="production_quote.html",
                mime="text/html"
            )