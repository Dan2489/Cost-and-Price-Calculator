import streamlit as st
import pandas as pd
from datetime import date

from config61 import CFG
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
from utils61 import (
    inject_govuk_css, sidebar_controls, fmt_currency,
    export_csv_bytes, export_html, render_table_html, adjust_table,
    export_csv_single_row, export_csv_bytes_rows, build_header_block,
    build_host_summary_block
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
# Sidebar (now ONLY labour output slider)
# -------------------------------
prisoner_output = sidebar_controls(CFG.GLOBAL_OUTPUT_DEFAULT)

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
num_supervisors = st.number_input("How many instructors are required at full contract capacity.", min_value=1, step=1)
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

# Additional benefits (optional 10% discount off instructor salary)
benefits_yes = st.checkbox("Any additional prison benefits that you feel warrant a further reduction?")
benefits_desc = ""
if benefits_yes:
    benefits_desc = st.text_area("Describe the benefits", key="benefits_desc", placeholder="e.g. onsite storage, free utilities, etc.")

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

def _grab_amount(df: pd.DataFrame, needle: str) -> float:
    """Get numeric Amount (£) for the last row whose Item contains `needle` (case-insensitive)."""
    try:
        m = df["Item"].astype(str).str.contains(needle, case=False, na=False, regex=False)
        if m.any():
            raw = str(df.loc[m, "Amount (£)"].iloc[-1]).replace("£", "").replace(",", "")
            return float(raw)
    except Exception:
        pass
    return 0.0

def _replace_amount(df: pd.DataFrame, exact_item_label: str, new_value: float) -> None:
    """Replace Amount (£) where Item equals exact label; if missing, append a new row."""
    m = df["Item"].astype(str) == exact_item_label
    if m.any():
        df.loc[m, "Amount (£)"] = round(new_value, 2)
    else:
        df.loc[len(df)] = [exact_item_label, round(new_value, 2)]

def _remove_zero_rows(df: pd.DataFrame, labels: list[str]) -> None:
    """Remove rows (by exact label) whose Amount is zero or nearly zero."""
    for lbl in labels:
        m = df["Item"].astype(str) == lbl
        if m.any():
            try:
                v = float(str(df.loc[m, "Amount (£)"].iloc[-1]).replace("£", "").replace(",", ""))
            except Exception:
                v = 0.0
            if abs(v) < 0.005:
                df.drop(df.index[m], inplace=True)

def _rebuild_host_totals(df: pd.DataFrame) -> None:
    """Recalculate Subtotal, VAT, Grand Total (using 20% VAT) from the visible rows above."""
    # Sum everything except VAT/Grand/Subtotal rows
    ignore = ["Subtotal", "VAT", "Grand Total"]
    body = df[~df["Item"].astype(str).str.startswith(tuple(ignore))]
    try:
        subtotal = pd.to_numeric(body["Amount (£)"], errors="coerce").fillna(0).sum()
    except Exception:
        subtotal = 0.0
    vat = subtotal * 0.20
    grand = subtotal + vat
    _replace_amount(df, "Subtotal", subtotal)
    _replace_amount(df, "VAT", vat)
    _replace_amount(df, "Grand Total", grand)

# Apply workshop-hours/contracts apportionment and optional 10% benefits discount to Instructor cost,
# and refresh Overheads (61%) + Development lines accordingly.
def _apply_host_instructor_and_discounts(df_in: pd.DataFrame,
                                         supervisor_salaries: list[float],
                                         customer_covers: bool,
                                         workshop_hours: float,
                                         contracts: int,
                                         employment_support: str,
                                         benefits_yes: bool) -> pd.DataFrame:
    df = df_in.copy()

    # Base instructor weekly cost from titles if NOT customer-provided; else shadow = 0 for host
    if customer_covers or not supervisor_salaries:
        inst_weekly_full = 0.0
    else:
        # Full-week cost (100% time); apportion by workshop hours vs 37.5 and split over #contracts
        weekly_per_title = [(s / 52.0) for s in supervisor_salaries]
        inst_weekly_full = sum(weekly_per_title) * max(0.0, min(1.0, workshop_hours / 37.5)) * (1.0 / max(1, int(contracts)))

    # Benefits discount is 10% of instructor (applied only if there is an instructor base)
    benefits_discount_weekly = (inst_weekly_full * 0.10) if (benefits_yes and inst_weekly_full > 0) else 0.0
    inst_weekly_net = inst_weekly_full - benefits_discount_weekly

    # Monthly instructor
    inst_monthly_net = inst_weekly_net * 52.0 / 12.0
    benefits_discount_monthly = benefits_discount_weekly * 52.0 / 12.0

    # Overheads (61% of instructor)
    overheads_monthly = inst_monthly_net * 0.61

    # Development charge from employment support
    dev_rate = _dev_rate_from_support(employment_support)
    dev_monthly_before = overheads_monthly * dev_rate

    # Development reduction row may already exist (if Host model has an automatic reduction),
    # we keep the same semantic: show Reduction (negative), then Revised development = before + reduction.
    # If there is no “Reduction” in the source, we leave it as 0.
    existing_reduction = _grab_amount(df_in, "Reduction")
    dev_revised = max(0.0, dev_monthly_before + existing_reduction)  # reduction is negative if present

    # Write rows (replace or add). Also ensure labels are exactly as per the summary requirement.
    _replace_amount(df, "Prisoner Wages", _grab_amount(df_in, "Prisoner Wages"))
    _replace_amount(df, "Instructor Salary", inst_monthly_net)
    _replace_amount(df, "Overheads", overheads_monthly)
    _replace_amount(df, "Development charge", dev_monthly_before)
    _replace_amount(df, "Development Reduction", existing_reduction)  # red if negative; 0 if none
    _replace_amount(df, "Revised development charge", dev_revised)
    _replace_amount(df, "Additional benefits reduction", -benefits_discount_monthly)  # display as negative

    # Remove zero/NA rows that should be hidden if not applicable
    _remove_zero_rows(df, [
        "Development Reduction",
        "Revised development charge",
        "Additional benefits reduction"
    ])

    # Rebuild totals
    _rebuild_host_totals(df)
    return df

# -------------------------------
# HOST
# -------------------------------
if contract_type == "Host":
    if st.button("Generate Host Costs"):
        errs = validate_inputs()
        if errs:
            st.error("Fix errors:\n- " + "\n- ".join(errs))
        else:
            # First build a base Host quote using the library (keeps consistency with historical calc)
            host_df_raw, ctx = host61.generate_host_quote(
                workshop_hours=workshop_hours,
                num_prisoners=num_prisoners,
                prisoner_salary=prisoner_salary,
                num_supervisors=num_supervisors,
                customer_covers_supervisors=customer_covers_supervisors,
                supervisor_salaries=supervisor_salaries,
                region=region,
                contracts=contracts,
                employment_support=employment_support,
                # instructor_allocation & lock_overheads removed from UI; we now enforce hours/contracts logic here
                instructor_allocation=100.0,
                lock_overheads=False,
            )
            # Now overwrite the instructor/overheads/dev lines to the new policy + benefits
            host_df = _apply_host_instructor_and_discounts(
                host_df_raw,
                supervisor_salaries=supervisor_salaries,
                customer_covers=customer_covers_supervisors,
                workshop_hours=float(workshop_hours),
                contracts=int(contracts),
                employment_support=employment_support,
                benefits_yes=benefits_yes,
            )
            st.session_state["host_df"] = host_df
            st.session_state["host_df_source"] = host_df_raw  # keep original if needed
            st.session_state["benefits_desc"] = benefits_desc

    if "host_df" in st.session_state:
        df = st.session_state["host_df"].copy()

        # Colour reductions
        if "Item" in df.columns:
            df_display = df.copy()
            def _red_if_reduction(label, val):
                if any(k in str(label) for k in ["Reduction"]):
                    return f"<span style='color:#d4351c'>{fmt_currency(val)}</span>"
                return fmt_currency(val)

            df_display["Amount (£)"] = [
                _red_if_reduction(lbl, val) for lbl, val in zip(df_display["Item"], df_display["Amount (£)"])
            ]
            st.markdown(render_table_html(df_display), unsafe_allow_html=True)
        else:
            st.markdown(render_table_html(df), unsafe_allow_html=True)

        # === Downloads ===
        header_block = build_header_block(
            uk_date=_uk_date(date.today()),
            customer_name=customer_name,
            prison_name=prison_choice,
            region=region,
            benefits_desc=(st.session_state.get("benefits_desc") or "")
        )

        # Single flat CSV row (inputs + results)
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
            "Additional Benefits": "Yes" if benefits_yes else "No",
            "Additional Benefits Description": st.session_state.get("benefits_desc") or "",
        }

        # Extract mapped amounts
        amounts = {}
        for _, r in df.iterrows():
            item = str(r.get("Item", "")).strip()
            try:
                val = float(str(r.get("Amount (£)")).replace("£", "").replace(",", ""))
            except Exception:
                val = None
            if item:
                amounts[f"Host: {item} (£/month)"] = val

        host_csv = export_csv_bytes_rows([{**common, **amounts}])

        c1, c2 = st.columns(2)
        with c1:
            st.download_button("Download CSV (Host)", data=host_csv, file_name="host_quote.csv", mime="text/csv")
        with c2:
            # HTML with header block and (for host) a summary list at top
            summary_html = build_host_summary_block(df)
            st.download_button(
                "Download PDF-ready HTML (Host)",
                data=export_html(df_host=df, df_prod=None, title="Host Quote",
                                 header_block=header_block, segregated_df=None,
                                 prepend_html=summary_html),
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
                        effective_pct=100.0,  # no instructor slider, use full apportion via hours/contracts within lib
                        customer_covers_supervisors=customer_covers_supervisors,
                        region=region,
                        customer_type="Commercial",
                        apply_vat=True, vat_rate=20.0,
                        num_prisoners=int(num_prisoners),
                        num_supervisors=int(num_supervisors),
                        dev_rate=_dev_rate_from_support(employment_support),
                        pricing_mode=pricing_mode_key,
                        targets=targets if pricing_mode_key == "target" else None,
                        lock_overheads=False,
                        employment_support=employment_support,
                        benefits_discount=0.10 if benefits_yes else 0.0  # pass through so the model can discount instructor
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
                        "dev_rate": _dev_rate_from_support(employment_support),
                        "benefits_yes": benefits_yes
                    }

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
                    effective_pct=100.0,
                    customer_covers_supervisors=customer_covers_supervisors,
                    region=region,
                    customer_type="Commercial",
                    apply_vat=True, vat_rate=20.0,
                    dev_rate=_dev_rate_from_support(employment_support),
                    today=date.today(),
                    lock_overheads=False,
                    employment_support=employment_support,
                    benefits_discount=0.10 if benefits_yes else 0.0
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
        st.markdown(render_table_html(df), unsafe_allow_html=True)

        # Segregated table (only when we have item inputs)
        seg_df = None
        if st.session_state.get("prod_items") is not None:
            items = st.session_state["prod_items"]
            meta = st.session_state["prod_meta"] or {}
            pricing_mode_key = meta.get("pricing_mode_key", "as-is")
            targets = meta.get("targets", [])
            output_pct = meta.get("output_pct", int(prisoner_output))
            dev_rate = meta.get("dev_rate", _dev_rate_from_support(employment_support))
            benefits_applied = bool(meta.get("benefits_yes", False))
            output_scale2 = float(output_pct) / 100.0

            # Instructor monthly (hours/contracts apportion) with optional 10% benefits reduction
            if not customer_covers_supervisors and supervisor_salaries:
                weekly_base = sum((s / 52.0) for s in supervisor_salaries) * max(0.0, min(1.0, workshop_hours / 37.5)) * (1.0 / max(1, int(contracts)))
                if benefits_applied:
                    weekly_base *= 0.90
                inst_monthly = weekly_base * 52.0 / 12.0
            else:
                inst_monthly = 0.0

            overheads_weekly = (inst_monthly * 12.0 / 52.0) * 0.61
            dev_weekly = overheads_weekly * dev_rate

            denom = sum(int(it.get("assigned", 0)) * workshop_hours * 60.0 for it in items)
            rows = []
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
                overheads_weekly_item = overheads_weekly * share
                dev_weekly_item = dev_weekly * share

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
                "Labour Output (%)": prisoner_output,
                "Employment Support": employment_support,
                "Contracts Overseen": contracts,
                "Additional Benefits": "Yes" if benefits_yes else "No",
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