import streamlit as st
import pandas as pd
from datetime import date

from config61 import CFG
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
from utils61 import (
    inject_govuk_css, sidebar_controls, fmt_currency,
    export_csv_bytes, export_html, render_table_html, adjust_table,
    export_csv_single_row, build_header_block
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

# Recommended instructor allocation
recommended_pct = 0.0
try:
    if workshop_hours > 0 and contracts > 0:
        recommended_pct = min(100.0, round((workshop_hours / 37.5) * (1.0 / contracts) * 100.0, 1))
except Exception:
    recommended_pct = 0.0
if recommended_pct > 0:
    st.info(f"Recommended Instructor allocation: {recommended_pct}% (based on hours open and contracts)")

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

def _dev_rate_from_support(s: str) -> float:
    if s == "None":
        return 0.20
    if s in ("Employment on release/RoTL", "Post release"):
        return 0.10
    return 0.00

def _uk_date(d: date) -> str:
    return d.strftime("%d/%m/%Y")

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
        if customer_covers_supervisors and "Item" in df.columns:
            df = df[~df["Item"].astype(str).str.contains("Instructor Salary", na=False)]

        # Red reductions
        if "Item" in df.columns:
            df_display = df.copy()
            df_display["Item"] = df_display["Item"].apply(
                lambda x: f"<span style='color:red'>{x}</span>" if "Reduction" in str(x) else x
            )
            st.markdown(render_table_html(df_display), unsafe_allow_html=True)
        else:
            st.markdown(render_table_html(df), unsafe_allow_html=True)

        # === Downloads ===
        header_block = build_header_block(
            uk_date=_uk_date(date.today()),
            customer_name=customer_name,
            prison_name=prison_choice,
            region=region
        )

        # Flat one-row CSV (Host)
        common = {
            "Quote Type": "Host",
            "Date": _uk_date(date.today()),
            "Prison Name": prison_choice,
            "Region": region,
            "Customer Name": customer_name,
            "Contract Type": "Host",
            "Workshop Hours / week": workshop_hours,
            "Prisoners Employed": num_prisoners,
            "Prisoner Salary / week": prisoner_salary,
            "Instructors Count": num_supervisors,
            "Customer Provides Instructors": "Yes" if customer_covers_supervisors else "No",
            "Instructor Allocation (%)": instructor_pct,
            "Recommended Allocation (%)": recommended_pct,
            "Lock Overheads to Highest": "Yes" if lock_overheads else "No",
            "Employment Support": employment_support,
            "Contracts Overseen": contracts,
            "VAT Rate (%)": 20.0,
        }
        # Map table amounts by name
        amounts = {}
        for _, r in df.iterrows():
            item = str(r.get("Item", "")).strip()
            val = r.get("Amount (£)")
            try:
                v = float(val)
            except Exception:
                v = None
            if "Prisoner" in item: amounts["Host: Prisoner wages (£/month)"] = v
            elif "Instructor Salary" in item: amounts["Host: Instructor Salary (£/month)"] = v
            elif "Overheads" in item: amounts["Host: Overheads 61% (£/month)"] = v
            elif "Development charge reduction" in item: amounts["Host: Development Reduction (£/month)"] = v
            elif "Revised development charge" in item: amounts["Host: Development Revised (£/month)"] = v
            elif "Development charge" in item: amounts["Host: Development charge (£/month)"] = v
            elif item.lower().startswith("subtotal"): amounts["Host: Subtotal (£/month)"] = v
            elif "VAT" in item: amounts["Host: VAT (£/month)"] = v
            elif "Grand Total" in item: amounts["Host: Grand Total (£/month)"] = v
        host_csv = export_csv_bytes_rows([{**common, **amounts}])

        c1, c2 = st.columns(2)
        with c1:
            st.download_button("Download CSV (Host)", data=host_csv, file_name="host_quote.csv", mime="text/csv")
        with c2:
            st.download_button(
                "Download PDF-ready HTML (Host)",
                data=export_html(df, None, title="Host Quote", header_block=header_block, segregated_df=None),
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
                disp = (name.strip() or f"Item {i+1}") if isinstance(name, str) else f"Item {i+1}"

                required = st.number_input(
                    f"Prisoners required to make 1 item ({disp})",
                    min_value=1, value=1, step=1, key=f"req_{i}"
                )

                unit_choice = st.radio(
                    f"Input unit for production time ({disp})",
                    ["Minutes", "Seconds"],
                    index=0,
                    key=f"mins_unit_{i}",
                    horizontal=True
                )
                if unit_choice == "Minutes":
                    minutes_val = st.number_input(
                        f"How long to make 1 item ({disp}) (minutes)",
                        min_value=0.0, value=10.0, format="%.4f", key=f"mins_val_{i}"
                    )
                    minutes_per = float(minutes_val)
                else:
                    seconds_val = st.number_input(
                        f"How long to make 1 item ({disp}) (seconds)",
                        min_value=0.0, value=30.0, format="%.2f", key=f"secs_val_{i}"
                    )
                    minutes_per = float(seconds_val) / 60.0

                total_assigned_before = sum(int(st.session_state.get(f"assigned_{j}", 0)) for j in range(i))
                remaining = max(0, int(num_prisoners) - total_assigned_before)
                assigned = st.number_input(
                    f"How many prisoners work solely on this item ({disp})",
                    min_value=0, max_value=remaining, value=int(st.session_state.get(f"assigned_{i}", 0)),
                    step=1, key=f"assigned_{i}"
                )

                if assigned > 0 and minutes_per >= 0 and required > 0 and workshop_hours > 0:
                    cap_100 = (assigned * workshop_hours * 60.0) / (minutes_per * required) if minutes_per > 0 else 0.0
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
                        dev_rate=_dev_rate_from_support(employment_support),
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
                        k: (None if r.get(k) is None else (round(float(r.get(k)), 4) if isinstance(r.get(k), (int, float)) else r.get(k)))
                        for k in display_cols
                    } for r in results])

                    st.session_state["prod_df"] = prod_df
                    st.session_state["prod_items"] = items
                    st.session_state["prod_meta"] = {
                        "pricing_mode_key": pricing_mode_key,
                        "targets": targets if pricing_mode_key == "target" else [],
                        "output_pct": int(prisoner_output),
                        "dev_rate": _dev_rate_from_support(employment_support)
                    }

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
                with c5: minutes_per_item = st.number_input("Minutes to make one", min_value=0.0, value=10.0, format="%.4f", key=f"adhoc_mins_{i}")
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
                if ln["mins_per_item"] < 0: errs.append(f"Line {i+1}: Minutes to make one cannot be negative")
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
                )
                if result["feasibility"]["hard_block"]:
                    st.error(result["feasibility"]["reason"])
                else:
                    df, totals = build_adhoc_table(result)
                    st.session_state["prod_df"] = df
                    st.session_state["prod_items"] = None
                    st.session_state["prod_meta"] = None

    # ===== Results + Segregated + Downloads =====
    if "prod_df" in st.session_state and isinstance(st.session_state["prod_df"], pd.DataFrame):
        df = st.session_state["prod_df"].copy()
        if customer_covers_supervisors and "Item" in df.columns:
            df = df[~df["Item"].astype(str).str.contains("Instructor Salary", na=False)]
        st.markdown(render_table_html(df), unsafe_allow_html=True)

        # Build segregated table (Contractual only)
        seg_df = None
        if st.session_state.get("prod_items") is not None:
            items = st.session_state["prod_items"]
            meta = st.session_state["prod_meta"] or {}
            pricing_mode_key = meta.get("pricing_mode_key", "as-is")
            targets = meta.get("targets", [])
            output_pct = meta.get("output_pct", int(prisoner_output))
            dev_rate = meta.get("dev_rate", _dev_rate_from_support(employment_support))
            output_scale2 = float(output_pct) / 100.0

            # Weekly instructor cost
            if not customer_covers_supervisors:
                inst_weekly_total = sum((s / 52.0) * (float(instructor_pct) / 100.0) for s in supervisor_salaries)
            else:
                inst_weekly_total = 0.0

            # Overhead (61%)
            if not customer_covers_supervisors:
                base = sum((s / 52.0) * (float(instructor_pct) / 100.0) for s in supervisor_salaries)
                if lock_overheads and supervisor_salaries:
                    base = (max(supervisor_salaries) / 52.0) * (float(instructor_pct) / 100.0)
                overhead_base_weekly = base
            else:
                # when customer provides instructors we only segregate “share” using the same pattern;
                if lock_overheads and supervisor_salaries:
                    overhead_base_weekly = (max(supervisor_salaries) / 52.0) * (float(instructor_pct) / 100.0)
                else:
                    overhead_base_weekly = 0.0
            overheads_weekly_total = overhead_base_weekly * 0.61
            dev_weekly_total = overheads_weekly_total * dev_rate

            denom = sum(int(it.get("assigned", 0)) * workshop_hours * 60.0 for it in items)
            rows = []
            inst_monthly = inst_weekly_total * 52.0 / 12.0
            monthly_sum_excl_inst = 0.0

            for idx, it in enumerate(items):
                name = (it.get("name") or "").strip() or f"Item {idx+1}"
                mins_per_unit = float(it.get("minutes", 0))
                pris_required = int(it.get("required", 1))
                pris_assigned = int(it.get("assigned", 0))

                if pris_assigned > 0 and mins_per_unit >= 0 and pris_required > 0 and workshop_hours > 0:
                    cap_100 = (pris_assigned * workshop_hours * 60.0) / (mins_per_unit * pris_required) if mins_per_unit > 0 else 0.0
                else:
                    cap_100 = 0.0
                capacity_units = cap_100 * output_scale2

                if pricing_mode_key == "target":
                    tgt = 0
                    if targets and idx < len(targets):
                        try: tgt = int(targets[idx])
                        except Exception: tgt = 0
                    units_for_pricing = float(tgt)
                else:
                    units_for_pricing = capacity_units

                share = ((pris_assigned * workshop_hours * 60.0) / denom) if denom > 0 else 0.0

                prisoner_weekly_item = pris_assigned * prisoner_salary
                overheads_weekly_item = overheads_weekly_total * share
                dev_weekly_item = dev_weekly_total * share

                weekly_excl_inst = prisoner_weekly_item + overheads_weekly_item + dev_weekly_item
                unit_cost_excl_inst = (weekly_excl_inst / units_for_pricing) if units_for_pricing > 0 else None
                monthly_total_excl_inst = (units_for_pricing * unit_cost_excl_inst * 52.0 / 12.0) if unit_cost_excl_inst else None

                monthly_sum_excl_inst += (monthly_total_excl_inst or 0.0)

                rows.append({
                    "Item": name,
                    "Output %": int(output_pct),
                    "Capacity (units/week)": 0 if capacity_units <= 0 else int(round(capacity_units)),
                    "Units/week": 0 if units_for_pricing <= 0 else int(round(units_for_pricing)),
                    "Unit Cost excl Instructor (£)": unit_cost_excl_inst,
                    "Monthly Total excl Instructor ex VAT (£)": monthly_total_excl_inst,
                })

            rows.append({
                "Item": "Instructor Salary (monthly)",
                "Output %": "",
                "Capacity (units/week)": "",
                "Units/week": "",
                "Unit Cost excl Instructor (£)": "",
                "Monthly Total excl Instructor ex VAT (£)": inst_monthly,
            })
            rows.append({
                "Item": "Grand Total (ex VAT)",
                "Output %": "",
                "Capacity (units/week)": "",
                "Units/week": "",
                "Unit Cost excl Instructor (£)": "",
                "Monthly Total excl Instructor ex VAT (£)": monthly_sum_excl_inst + inst_monthly,
            })

            seg_df = pd.DataFrame(rows)

        if seg_df is not None and not seg_df.empty:
            st.markdown("### Segregated Costs")
            st.markdown(render_table_html(seg_df), unsafe_allow_html=True)

        # === Downloads (Production) ===
        header_block = build_header_block(
            uk_date=_uk_date(date.today()),
            customer_name=customer_name,
            prison_name=prison_choice,
            region=region
        )

        c1, c2 = st.columns(2)
        with c1:
            # Single-row CSV including segregated section
            common = {
                "Quote Type": "Production",
                "Date": _uk_date(date.today()),
                "Prison Name": prison_choice,
                "Region": region,
                "Customer Name": customer_name,
                "Contract Type": "Production",
                "Workshop Hours / week": workshop_hours,
                "Prisoners Employed": num_prisoners,
                "Prisoner Salary / week": prisoner_salary,
                "Instructors Count": num_supervisors,
                "Customer Provides Instructors": "Yes" if customer_covers_supervisors else "No",
                "Instructor Allocation (%)": instructor_pct,
                "Recommended Allocation (%)": recommended_pct,
                "Labour Output (%)": prisoner_output,
                "Lock Overheads to Highest": "Yes" if lock_overheads else "No",
                "Employment Support": employment_support,
                "Contracts Overseen": contracts,
                "VAT Rate (%)": 20.0,
            }
            csv_bytes = export_csv_single_row(common, df, seg_df)
            st.download_button(
                "Download CSV (Production)",
                data=csv_bytes,
                file_name="production_quote.csv",
                mime="text/csv"
            )
        with c2:
            st.download_button(
                "Download PDF-ready HTML (Production)",
                data=export_html(None, df, title="Production Quote", header_block=header_block, segregated_df=seg_df),
                file_name="production_quote.html",
                mime="text/html"
            )