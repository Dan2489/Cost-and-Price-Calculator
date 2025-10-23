import streamlit as st
import pandas as pd
from datetime import date
import math

from config61 import CFG
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
from utils61 import (
    inject_govuk_css, sidebar_controls, fmt_currency,
    export_csv_bytes, export_html, render_table_html, adjust_table,
    export_csv_single_row, export_csv_bytes_rows, build_header_block
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
# Sidebar (simplified): only labour output slider
# -------------------------------
prisoner_output = sidebar_controls(CFG.GLOBAL_OUTPUT_DEFAULT)

# -------------------------------
# Helpers
# -------------------------------
def _dev_rate_from_support(s: str) -> float:
    # Base policy: None = 20%, RoTL/Post = 10%, Both = 0%
    if s == "None":
        return 0.20
    if s in ("Employment on release/RoTL", "Post release"):
        return 0.10
    return 0.00

def _uk_date(d: date) -> str:
    return d.strftime("%d/%m/%Y")

def _grab_amount(df: pd.DataFrame, needle: str) -> float:
    """Pulls a numeric amount from 'Amount (£)' where 'Item' contains needle (case-insensitive)."""
    try:
        m = df["Item"].astype(str).str.contains(needle, case=False, na=False)
        if m.any():
            raw = str(df.loc[m, "Amount (£)"].iloc[-1]).replace("£", "").replace(",", "")
            return float(raw)
    except Exception:
        pass
    return 0.0

def _fmt_or_dash(x, places=2):
    if x is None:
        return "—"
    try:
        return fmt_currency(round(float(x), places))
    except Exception:
        return "—"

def _safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

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
num_supervisors = st.number_input(
    "How many instructors are required when the contract is at full capacity.",
    min_value=1, step=1
)
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

# Contracts: hide input when customer provides instructors (assume 1)
if not customer_covers_supervisors:
    contracts = st.number_input("How many contracts do they oversee in this workshop?", min_value=1, value=1)
else:
    contracts = 1

employment_support = st.selectbox(
    "What employment support does the customer offer?",
    ["None", "Employment on release/RoTL", "Post release", "Both"],
)

# Additional benefits question (after employment support)
additional_benefits = st.checkbox("Any additional prison benefits that you feel warrant a further reduction?", value=False)
benefits_desc = ""
if additional_benefits:
    benefits_desc = st.text_area("Describe the benefits (optional)", value="")

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
# HOST
# -------------------------------
if contract_type == "Host":
    if st.button("Generate Host Costs", type="primary"):
        errs = validate_inputs()
        if errs:
            st.error("Fix errors:\n- " + "\n- ".join(errs))
        else:
            # NOTE: we pass only the knobs host61 expects; development logic is adjusted below to ensure
            # development is calculated on instructor + overheads, and discounts shown.
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
            )

            # --- Post-process so that:
            #  1) rename "Instructor Salary" -> "Instructor Cost"
            #  2) recompute Development on (Instructor + Overheads)
            #  3) compute development discount (20% baseline)
            #  4) additional benefits discount (10% of instructor) only if Employment Support == "Both" and checkbox ticked
            df = host_df.copy()

            # Rename for display consistency
            if "Item" in df.columns:
                df["Item"] = df["Item"].replace(
                    {"Instructor Salary": "Instructor Cost"}, regex=False
                )

            # Extract current instructor & overheads
            inst_amt = _grab_amount(df, "Instructor Cost")
            if inst_amt == 0:
                # if customer provides instructors, still shadow overheads should be based on highest title IF any listed
                if customer_covers_supervisors and supervisor_salaries:
                    inst_amt = (max(supervisor_salaries) / 12.0) * (workshop_hours / 37.5) / max(1, int(contracts))
            over_amt = _grab_amount(df, "Overheads")

            # Compute dev rate and baseline discount from 20%
            applied_rate = _dev_rate_from_support(employment_support)
            base_rate = 0.20
            dev_before = (inst_amt + over_amt) * base_rate
            dev_revised = (inst_amt + over_amt) * applied_rate
            dev_discount = max(0.0, dev_before - dev_revised)

            # Additional benefits discount (10% of instructor) only when Support == Both and user ticked
            benefits_discount = 0.0
            if employment_support == "Both" and additional_benefits:
                benefits_discount = 0.10 * inst_amt

            # Rebuild the summary table in order with corrected labels & numbers
            rows = []
            # Prisoner wages (if present in original)
            pris_amt = _grab_amount(df, "Prisoner Wages")
            if pris_amt:
                rows.append(["Prisoner wages", fmt_currency(pris_amt)])

            rows.append(["Instructor Cost", fmt_currency(inst_amt)])
            rows.append(["Overheads", fmt_currency(over_amt)])
            rows.append(["Development charge (on Instructor+Overheads @ 20%)", fmt_currency(dev_before)])
            if dev_discount > 0:
                rows.append(["Development discount", f"<span style='color:red'>- {fmt_currency(dev_discount)}</span>"])
            rows.append(["Revised development charge", fmt_currency(dev_revised)])
            if benefits_discount > 0:
                rows.append(["Additional benefit discount", f"<span style='color:red'>- {fmt_currency(benefits_discount)}</span>"])

            # Compute totals (ex VAT)
            subtotal = pris_amt + inst_amt + over_amt + dev_revised - dev_discount - benefits_discount
            rows.append(["Grand Total (ex VAT)", f"<b>{fmt_currency(subtotal)}</b>"])
            vat = subtotal * 0.20
            rows.append(["VAT (20%)", fmt_currency(vat)])
            rows.append(["Grand Total + VAT", f"<b>{fmt_currency(subtotal + vat)}</b>"])

            summ_df = pd.DataFrame(rows, columns=["Item", "Amount (£)"])
            st.session_state["host_df"] = summ_df

            # Keep a copy for CSV extraction with proper ordering
            st.session_state["host_breakdown_source"] = {
                "prisoner_wages": pris_amt,
                "instructor": inst_amt,
                "overheads": over_amt,
                "dev_before": dev_before,
                "dev_discount": dev_discount,
                "dev_revised": dev_revised,
                "benefits_discount": benefits_discount,
                "subtotal": subtotal,
                "vat": vat,
                "grand": subtotal + vat,
            }

    if "host_df" in st.session_state:
        df = st.session_state["host_df"].copy()

        # Colour reductions red already embedded via HTML in Amount column
        st.markdown(render_table_html(df), unsafe_allow_html=True)

        # === Downloads ===
        header_block = build_header_block(
            uk_date=_uk_date(date.today()),
            customer_name=customer_name,
            prison_name=prison_choice,
            region=region
        )

        # Host CSV (flat single row)
        src = st.session_state.get("host_breakdown_source", {})
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
            "Employment Support": employment_support,
            "Contracts Overseen": contracts,
            "VAT Rate (%)": 20.0,
            "Additional Benefits": "Yes" if additional_benefits else "No",
            "Additional Benefits (desc)": benefits_desc,
        }
        amounts = {
            "Host: Prisoner wages (£/month)": _safe_float(src.get("prisoner_wages", 0)),
            "Host: Instructor Cost (£/month)": _safe_float(src.get("instructor", 0)),
            "Host: Overheads (£/month)": _safe_float(src.get("overheads", 0)),
            "Host: Development charge (before discount) (£/month)": _safe_float(src.get("dev_before", 0)),
            "Host: Development discount (£/month)": _safe_float(src.get("dev_discount", 0)),
            "Host: Development (revised) (£/month)": _safe_float(src.get("dev_revised", 0)),
            "Host: Additional benefit discount (£/month)": _safe_float(src.get("benefits_discount", 0)),
            "Host: Grand Total ex VAT (£/month)": _safe_float(src.get("subtotal", 0)),
            "Host: VAT (£/month)": _safe_float(src.get("vat", 0)),
            "Host: Grand Total inc VAT (£/month)": _safe_float(src.get("grand", 0)),
        }
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
            if st.button("Generate Production Costs", type="primary", key="generate_contractual"):
                errs = validate_inputs()
                if errs:
                    st.error("Fix errors:\n- " + "\n- ".join(errs))
                else:
                    # For Production, customers do NOT provide instructors => False
                    results = calculate_production_contractual(
                        items, int(prisoner_output),
                        workshop_hours=float(workshop_hours),
                        prisoner_salary=float(prisoner_salary),
                        supervisor_salaries=supervisor_salaries,
                        customer_covers_supervisors=False,
                        region=region,
                        customer_type="Commercial",
                        apply_vat=True, vat_rate=20.0,
                        num_prisoners=int(num_prisoners),
                        num_supervisors=int(num_supervisors),
                        pricing_mode=pricing_mode_key,
                        targets=targets if pricing_mode_key == "target" else None,
                        employment_support=employment_support,
                        contracts=int(contracts),
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

        if st.button("Generate Ad-hoc Costs", type="primary", key="generate_adhoc"):
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
                    customer_covers_supervisors=False,  # For Production, customers can't provide instructor
                    region=region,
                    customer_type="Commercial",
                    apply_vat=True, vat_rate=20.0,
                    today=date.today(),
                    employment_support=employment_support,
                    contracts=int(contracts),
                )
                if result["feasibility"]["hard_block"]:
                    st.error(result["feasibility"]["reason"])
                else:
                    df, totals = build_adhoc_table(result)
                    st.session_state["prod_df"] = df
                    st.session_state["prod_items"] = None
                    st.session_state["prod_meta"] = None

    # ===== Results + Production Summary + Downloads =====
    if "prod_df" in st.session_state and isinstance(st.session_state["prod_df"], pd.DataFrame):
        df = st.session_state["prod_df"].copy()
        st.markdown(render_table_html(df), unsafe_allow_html=True)

        # Build Production Summary (contractual only)
        seg_df = None
        if st.session_state.get("prod_items") is not None:
            items = st.session_state["prod_items"]
            meta = st.session_state["prod_meta"] or {}
            pricing_mode_key = meta.get("pricing_mode_key", "as-is")
            targets = meta.get("targets", [])
            output_pct = meta.get("output_pct", int(prisoner_output))
            dev_rate = _dev_rate_from_support(employment_support)
            output_scale2 = float(output_pct) / 100.0

            # Weekly instructor cost (scaled by hours and contracts)
            inst_weekly_total = sum(
                (s / 52.0) * (float(workshop_hours) / 37.5) / max(1, int(contracts)) for s in supervisor_salaries
            )
            # Overheads (61% of instructor)
            overheads_weekly_total = inst_weekly_total * 0.61

            # Development: on (Instructor + Overheads)
            base_rate = 0.20
            dev_before_weekly = (inst_weekly_total + overheads_weekly_total) * base_rate
            dev_revised_weekly = (inst_weekly_total + overheads_weekly_total) * dev_rate
            dev_discount_weekly = max(0.0, dev_before_weekly - dev_revised_weekly)

            # Additional benefits (only if support == Both and box ticked) — 10% of instructor
            benefits_disc_weekly = 0.0
            if employment_support == "Both" and additional_benefits:
                benefits_disc_weekly = 0.10 * inst_weekly_total

            # Convert above to monthly
            inst_monthly = inst_weekly_total * 52.0 / 12.0
            overheads_monthly = overheads_weekly_total * 52.0 / 12.0
            dev_before_m = dev_before_weekly * 52.0 / 12.0
            dev_discount_m = dev_discount_weekly * 52.0 / 12.0
            dev_revised_m = dev_revised_weekly * 52.0 / 12.0
            benefits_disc_m = benefits_disc_weekly * 52.0 / 12.0

            # Prisoner wages (weekly & monthly) per item, to build prisoner-only unit cost
            denom_minutes = sum(int(it.get("assigned", 0)) * workshop_hours * 60.0 for it in items)
            total_monthly_prisoner_wages = 0.0
            unit_cost_prisoner_only = None
            units_for_pricing_total = 0.0

            for idx, it in enumerate(items):
                pris_assigned = int(it.get("assigned", 0))
                mins_per_unit = float(it.get("minutes", 0))
                pris_required = int(it.get("required", 1))

                # Units/week by scenario
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

                units_for_pricing_total += max(0.0, units_for_pricing)

                # Prisoner wages for this item
                prisoner_weekly_item = pris_assigned * prisoner_salary
                total_monthly_prisoner_wages += prisoner_weekly_item * 52.0 / 12.0

            # Prisoner-only unit cost (monthly wages / monthly units), if we have units
            monthly_units = units_for_pricing_total * (52.0 / 12.0)
            if monthly_units > 0:
                unit_cost_prisoner_only = total_monthly_prisoner_wages / monthly_units

            # Non-prisoner monthly cost to cover
            non_prisoner_monthly = inst_monthly + overheads_monthly + dev_revised_m - dev_discount_m - benefits_disc_m

            # Units needed to cover non-prisoner cost (using prisoner-only unit cost)
            if unit_cost_prisoner_only and unit_cost_prisoner_only > 0:
                units_to_cover = math.ceil(non_prisoner_monthly / unit_cost_prisoner_only)
            else:
                units_to_cover = None

            rows = []
            rows.append(["Instructor Cost (monthly)", fmt_currency(inst_monthly)])
            rows.append(["Overheads (monthly)", fmt_currency(overheads_monthly)])
            rows.append(["Development charge (before discount)", fmt_currency(dev_before_m)])
            if dev_discount_m > 0:
                rows.append(["Development discount", f"<span style='color:red'>- {fmt_currency(dev_discount_m)}</span>"])
            rows.append(["Revised development charge", fmt_currency(dev_revised_m)])
            if benefits_disc_m > 0:
                rows.append(["Additional benefit discount", f"<span style='color:red'>- {fmt_currency(benefits_disc_m)}</span>"])
            rows.append(["Unit cost (prisoner wages only)", _fmt_or_dash(unit_cost_prisoner_only)])
            rows.append(["Units to cover non-prisoner costs (monthly)", f"{int(units_to_cover):,}" if units_to_cover else "—"])

            seg_df = pd.DataFrame(rows, columns=["Item", "Amount (£)"])

        if seg_df is not None and not seg_df.empty:
            st.markdown("### Production Summary (Contractual)")
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
            # One-row CSV including production summary
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
                "Customer Provides Instructors": "No",  # enforced for Production
                "Labour Output (%)": prisoner_output,
                "Employment Support": employment_support,
                "Contracts Overseen": contracts,
                "VAT Rate (%)": 20.0,
                "Additional Benefits": "Yes" if additional_benefits else "No",
                "Additional Benefits (desc)": benefits_desc,
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