import streamlit as st
import pandas as pd
from datetime import date

from config61 import CFG
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
from utils61 import (
    inject_govuk_css, sidebar_controls, fmt_currency,
    export_csv_flat, export_html, render_table_html, adjust_table
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

# Recommended allocation (shown, not forced)
try:
    recommended_pct = max(1, min(100, round((workshop_hours / 37.5) * (1 / contracts) * 100, 1)))
except Exception:
    recommended_pct = 100.0
st.caption(f"Recommended Instructor allocation: **{recommended_pct}%** (based on hours open and contracts)")

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


# Build meta for exports
def _build_meta(common_contract_type: str) -> dict:
    return {
        "prison_name": prison_choice,
        "region": region,
        "customer_name": customer_name,
        "date": date.today().strftime("%d %B %Y"),
        "contract_type": common_contract_type,
        "employment_support": employment_support,
        "workshop_hours": workshop_hours,
        "num_prisoners": num_prisoners,
        "prisoner_salary": prisoner_salary,
        "num_supervisors": num_supervisors,
        "customer_covers_supervisors": customer_covers_supervisors,
        "instructor_allocation": instructor_pct,
        "recommended_allocation": recommended_pct,
        "contracts": contracts,
        "lock_overheads": lock_overheads,
        "prisoner_output_percent": prisoner_output,
    }


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
        df = st.session_state["host_df"].copy()
        if customer_covers_supervisors:
            df = df[~df["Item"].astype(str).str.contains("Instructor Salary", na=False)]

        # Highlight reductions in red (in-app)
        if "Item" in df.columns:
            df_display = df.copy()
            df_display["Item"] = df_display["Item"].apply(
                lambda x: f"<span style='color:red'>{x}</span>" if "Reduction" in str(x) else x
            )
            st.markdown(render_table_html(df_display), unsafe_allow_html=True)
        else:
            st.markdown(render_table_html(df), unsafe_allow_html=True)

        # Downloads
        meta = _build_meta("Host")
        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "Download CSV (Host - Flat)",
                data=export_csv_flat(meta, df, None, None),
                file_name="host_flat_export.csv",
                mime="text/csv"
            )
        with c2:
            st.download_button(
                "Download PDF-ready HTML (Host)",
                data=export_html(df, None, title="Host Quote", meta=meta),
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

        for i in range(int(num_items)):
            with st.expander(f"Item {i+1} details", expanded=(i == 0)):
                name = st.text_input(f"Item {i+1} Name", key=f"name_{i}")
                disp = (name.strip() or f"Item {i+1}") if isinstance(name, str) else f"Item {i+1}"

                required = st.number_input(
                    f"Prisoners required to make 1 item ({disp})",
                    min_value=1, value=1, step=1, key=f"req_{i}"
                )

                # Minutes / Seconds input
                unit_choice = st.radio(
                    f"Input unit for production time ({disp})",
                    ["Minutes", "Seconds"], index=0, key=f"time_unit_{i}", horizontal=True
                )
                if unit_choice == "Minutes":
                    time_val = st.number_input(
                        f"How long to make 1 item ({disp}) (minutes)",
                        min_value=0.0, value=1.0, format="%.2f", key=f"mins_{i}"
                    )
                    minutes_per = float(time_val)
                else:
                    secs_val = st.number_input(
                        f"How long to make 1 item ({disp}) (seconds)",
                        min_value=0.0, value=30.0, format="%.0f", key=f"secs_{i}"
                    )
                    minutes_per = float(secs_val) / 60.0

                total_assigned_before = sum(int(st.session_state.get(f"assigned_{j}", 0)) for j in range(i))
                remaining = max(0, int(num_prisoners) - total_assigned_before)
                assigned = st.number_input(
                    f"How many prisoners work solely on this item ({disp})",
                    min_value=0, max_value=remaining, value=int(st.session_state.get(f"assigned_{i}", 0)),
                    step=1, key=f"assigned_{i}"
                )

                # Optional: current price per unit (ex VAT) for comparison
                current_price = st.number_input(
                    f"Current price per unit (£) ({disp})", min_value=0.0, value=0.0, format="%.2f", key=f"cur_price_{i}"
                )

                # Capacity preview
                if assigned > 0 and minutes_per > 0 and required > 0 and workshop_hours > 0:
                    cap_100 = (assigned * workshop_hours * 60.0) / (minutes_per * required)
                else:
                    cap_100 = 0.0
                cap_planned = cap_100 * output_scale
                st.caption(f"{disp} capacity @ 100%: **{cap_100:.0f} units/week** · @ {prisoner_output}%: **{cap_planned:.0f}**")

                # Target input — ONLY when pricing_mode == "target"
                if pricing_mode_key == "target":
                    tgt_default = int(round(cap_planned)) if cap_planned > 0 else 0
                    tgt = st.number_input(
                        f"Target units per week ({disp})", min_value=0, value=tgt_default, step=1, key=f"target_{i}"
                    )
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
                if errs:
                    st.error("Fix errors:\n- " + "\n- ".join(errs))
                else:
                    # Main (combined) pricing
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

                    display_cols = [
                        "Item", "Output %", "Capacity (units/week)", "Units/week",
                        "Unit Cost (£)", "Unit Price ex VAT (£)", "Unit Price inc VAT (£)",
                        "Monthly Total ex VAT (£)", "Monthly Total inc VAT (£)"
                    ]
                    if pricing_mode_key == "target":
                        display_cols += ["Feasible", "Note"]

                    df_main = pd.DataFrame([{
                        k: (None if r.get(k) is None else (round(float(r.get(k)), 2)
                            if isinstance(r.get(k), (int, float)) else r.get(k)))
                        for k in display_cols
                    } for r in results])

                    # Segregated view (separate instructor salary monthly + unit cost from overhead+prisoner+dev)
                    # We ask production61.calculate_production_contractual to include these keys in each result:
                    #   "Instructor Monthly (£)", "Unit Cost (no instructor) (£)", "Units/week"
                    seg_cols = [
                        "Item", "Output %", "Capacity (units/week)", "Units/week",
                        "Unit Cost (no instructor) (£)", "Instructor Monthly (£)",
                        "Monthly Total ex VAT (£)", "Monthly Total inc VAT (£)"
                    ]
                    df_segr = pd.DataFrame([{
                        k: (None if r.get(k) is None else (round(float(r.get(k)), 2)
                            if isinstance(r.get(k), (int, float)) else r.get(k)))
                        for k in seg_cols
                    } for r in results])

                    # Store for rendering + export
                    st.session_state["prod_df_combined"] = df_main
                    st.session_state["prod_df_segregated"] = df_segr

    # ---------- Ad-hoc ----------
    else:
        num_lines = st.number_input("How many product lines are needed?", min_value=1, value=1, step=1, key="adhoc_num_lines")
        lines = []
        for i in range(int(num_lines)):
            with st.expander(f"Product line {i+1}", expanded=(i == 0)):
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    item_name = st.text_input("Item name", key=f"adhoc_name_{i}")
                with c2:
                    units_requested = st.number_input("Units requested", min_value=1, value=100, step=1, key=f"adhoc_units_{i}")
                with c3:
                    deadline = st.date_input("Deadline", value=date.today(), key=f"adhoc_deadline_{i}")

                # Minutes / Seconds input for ad-hoc
                c4, c5, c6 = st.columns([1, 1, 1])
                with c4:
                    pris_per_item = st.number_input("Prisoners to make one", min_value=1, value=1, step=1, key=f"adhoc_pris_req_{i}")
                with c5:
                    unit_choice = st.radio(
                        "Input unit", ["Minutes", "Seconds"], index=0, key=f"adhoc_unit_{i}", horizontal=True
                    )
                with c6:
                    if unit_choice == "Minutes":
                        time_val = st.number_input("Time per item (minutes)", min_value=0.0, value=1.0, format="%.2f", key=f"adhoc_mins_{i}")
                        minutes_per_item = float(time_val)
                    else:
                        secs_val = st.number_input("Time per item (seconds)", min_value=0.0, value=30.0, format="%.0f", key=f"adhoc_secs_{i}")
                        minutes_per_item = float(secs_val) / 60.0

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
                    st.session_state["prod_df_combined"] = df
                    st.session_state["prod_df_segregated"] = None

    # -------- Render + downloads for Production --------
    if "prod_df_combined" in st.session_state and isinstance(st.session_state["prod_df_combined"], pd.DataFrame):
        df_main = st.session_state["prod_df_combined"]
        df_segr = st.session_state.get("prod_df_segregated")

        st.markdown("### Production — Summary")
        st.markdown(render_table_html(df_main), unsafe_allow_html=True)

        if df_segr is not None and not df_segr.empty:
            st.markdown("### Production — Segregated View")
            st.markdown(render_table_html(df_segr), unsafe_allow_html=True)

        # Downloads
        meta = _build_meta("Production")
        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "Download CSV (Production - Flat)",
                data=export_csv_flat(meta, None, df_main, df_segr),
                file_name="production_flat_export.csv",
                mime="text/csv"
            )
        with c2:
            st.download_button(
                "Download PDF-ready HTML (Production)",
                data=export_html(None, df_main, title="Production Quote", meta=meta, df_prod_segregated=df_segr),
                file_name="production_quote.html",
                mime="text/html"
            )