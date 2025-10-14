# newapp61.py
import streamlit as st
import pandas as pd
from datetime import date

from config61 import CFG
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
from utils61 import (
    inject_govuk_css, sidebar_controls, fmt_currency,
    export_html, render_table_html, build_header_block,
    export_csv_single_row, export_csv_bytes_rows
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
# Sidebar (back-compat: supports 1-value or 3-value return)
# -------------------------------
_sc = sidebar_controls(CFG.GLOBAL_OUTPUT_DEFAULT)
if isinstance(_sc, tuple):
    # Old signature: (lock_overheads, instructor_pct, prisoner_output)
    prisoner_output = _sc[-1]
else:
    # New signature: only output %
    prisoner_output = _sc

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

# Instructor inputs (title/grade and COUNT only)
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

# NEW: Additional benefits -> 10% discount to Instructor & Overheads
benefits_yes = st.checkbox("Any additional prison benefits that you feel warrant a further reduction?")
benefits_text = ""
if benefits_yes:
    benefits_text = st.text_area("Describe the benefits")

# -------------------------------
# Derived/Helpers
# -------------------------------
def _uk_date(d: date) -> str:
    return d.strftime("%d/%m/%Y")

def _dev_rate_from_support(s: str) -> float:
    if s == "None":
        return 0.20
    if s in ("Employment on release/RoTL", "Post release"):
        return 0.10
    return 0.00

def _recommended_pct(hours: float, contracts_count: int) -> float:
    try:
        if hours > 0 and contracts_count > 0:
            return min(100.0, round((hours / 37.5) * (1.0 / contracts_count) * 100.0, 1))
    except Exception:
        pass
    return 0.0

# Instructor % now ALWAYS derived (and never shown)
effective_instructor_pct = _recommended_pct(workshop_hours, int(contracts))

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

# Generic row-search (safe: no regex)
def _grab_amount(df: pd.DataFrame, needle: str) -> float:
    try:
        if {"Item", "Amount (£)"}.issubset(df.columns):
            m = df["Item"].astype(str).str.contains(needle, case=False, na=False, regex=False)
            if m.any():
                raw = str(df.loc[m, "Amount (£)"].iloc[-1]).replace("£", "").replace(",", "")
                return float(raw)
    except Exception:
        pass
    return 0.0

# Apply 10% Benefits discount to Instructor & Overheads in a Host quote table
def _apply_benefits_discount_host(df: pd.DataFrame, instructor_discount: float) -> pd.DataFrame:
    """Returns a new dataframe with 10% reductions lines added (red) and totals adjusted."""
    if df is None or df.empty or instructor_discount <= 0:
        return df

    # Read original rows (safe match)
    inst = _grab_amount(df, "Instructor Salary")
    # Accept either 'Overheads' or 'Overheads (61%' in legacy exports
    over = _grab_amount(df, "Overheads (61%")
    if over == 0.0:
        over = _grab_amount(df, "Overheads")

    inst_red = round(inst * instructor_discount, 2)
    over_red = round(over * instructor_discount, 2)

    # Build new table: insert two negative lines just after Instructor & Overheads
    out = []
    for _, r in df.iterrows():
        label = str(r.get("Item", ""))
        out.append(dict(r))
        if label.lower().startswith("instructor salary"):
            out.append({"Item": f"Benefits Reduction - Instructor (10%)", "Amount (£)": -inst_red})
        if label.lower().startswith("overheads"):
            out.append({"Item": f"Benefits Reduction - Overheads (10%)", "Amount (£)": -over_red})

    new_df = pd.DataFrame(out)

    # Recompute Subtotal / Grand Total if present
    # (sum of all non-VAT rows up to Subtotal, then Grand Total incl VAT if present)
    # We keep simple: when we see a row Subtotal/Grand Total we replace their numbers with recomputed values.
    def _sum_before(label: str) -> float:
        s = 0.0
        for _, rr in new_df.iterrows():
            it = str(rr.get("Item", ""))
            val = rr.get("Amount (£)")
            if isinstance(val, str):
                try: val = float(val.replace("£", "").replace(",", ""))
                except Exception: val = 0.0
            val = 0.0 if pd.isna(val) else float(val)
            if it.lower().startswith(label.lower()):
                break
            # exclude VAT lines from the base
            if "vat" in it.lower():
                continue
            s += val
        return s

    # Update Subtotal
    st_mask = new_df["Item"].astype(str).str.contains("Subtotal", case=False, na=False, regex=False)
    if st_mask.any():
        subtotal = round(_sum_before("Subtotal"), 2)
        new_df.loc[st_mask, "Amount (£)"] = subtotal

    # Update Grand Total (ex VAT / inc VAT variants)
    gt_mask = new_df["Item"].astype(str).str.contains("Grand Total", case=False, na=False, regex=False)
    if gt_mask.any():
        # If a separate VAT line exists, just recompute as subtotal + VAT line(s)
        vat_mask = new_df["Item"].astype(str).str.contains("VAT", case=False, na=False, regex=False)
        if vat_mask.any():
            # First recompute VAT from the new subtotal if there is a single VAT line with % in label
            # Otherwise sum existing VAT lines
            subtotal = round(_sum_before("Grand Total"), 2)
            vat_total = 0.0
            for _, rr in new_df[vat_mask].iterrows():
                it = str(rr["Item"])
                amt = rr["Amount (£)"]
                if isinstance(amt, str):
                    try: amt = float(amt.replace("£", "").replace(",", ""))
                    except Exception: amt = 0.0
                amt = 0.0 if pd.isna(amt) else float(amt)
                # Try to parse a "20%" style from the label
                pct = None
                for token in it.replace("(", " ").replace(")", " ").split():
                    if token.endswith("%"):
                        try: pct = float(token.strip("%")) / 100.0
                        except Exception: pct = None
                if pct is not None:
                    vat_total += round(subtotal * pct, 2)
                else:
                    vat_total += amt
            grand = round(subtotal + vat_total, 2)
        else:
            # No VAT rows: treat Grand Total as ex VAT and recompute as subtotal
            grand = round(_sum_before("Grand Total"), 2)
        new_df.loc[gt_mask, "Amount (£)"] = grand

    return new_df

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
                # Use derived instructor %
                instructor_allocation=effective_instructor_pct,
                # We still pass lock_overheads if your host61 uses it; default False when not present
                lock_overheads=False,
            )
            # Remove “(61%)” in label for display consistency
            if "Item" in host_df.columns:
                host_df["Item"] = host_df["Item"].astype(str).str.replace("Overheads (61%)", "Overheads", regex=False)

            # Apply 10% benefits reduction to Instructor & Overheads if selected
            if benefits_yes:
                host_df = _apply_benefits_discount_host(host_df, 0.10)

            st.session_state["host_df"] = host_df

    if "host_df" in st.session_state:
        df = st.session_state["host_df"].copy()
        if customer_covers_supervisors and "Item" in df.columns:
            df = df[~df["Item"].astype(str).str.contains("Instructor Salary", na=False, regex=False)]

        # Make reductions red
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

        source_df = st.session_state["host_df"].copy()

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
            "Instructor Allocation (%)": effective_instructor_pct,
            "Employment Support": employment_support,
            "Contracts Overseen": contracts,
            "Additional Prison Benefits?": "Yes" if benefits_yes else "No",
            "Benefits Notes": benefits_text,
            "VAT Rate (%)": 20.0,
        }

        amounts = {
            "Host: Prisoner wages (£/month)": _grab_amount(source_df, "Prisoner Wages"),
            "Host: Instructor Salary (£/month)": _grab_amount(source_df, "Instructor Salary"),
            "Host: Overheads (£/month)": _grab_amount(source_df, "Overheads"),
            "Host: Development charge (£/month)": _grab_amount(source_df, "Development charge"),
            "Host: Development Reduction (£/month)": _grab_amount(source_df, "Reduction"),
            "Host: Development Revised (£/month)": _grab_amount(source_df, "Revised development charge"),
            "Host: Subtotal (£/month)": _grab_amount(source_df, "Subtotal"),
            "Host: VAT (£/month)": _grab_amount(source_df, "VAT"),
            "Host: Grand Total (£/month)": _grab_amount(source_df, "Grand Total"),
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
                        # use derived instructor % (no slider)
                        effective_pct=float(effective_instructor_pct),
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
                        # Production reductions handled in the pricing functions as before
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

    else:  # Ad-hoc unchanged (uses derived instructor % internally)
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
                    effective_pct=float(effective_instructor_pct),
                    customer_covers_supervisors=customer_covers_supervisors,
                    region=region,
                    customer_type="Commercial",
                    apply_vat=True, vat_rate=20.0,
                    dev_rate=_dev_rate_from_support(employment_support),
                    today=date.today(),
                    lock_overheads=False,
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
            df = df[~df["Item"].astype(str).str.contains("Instructor Salary", na=False, regex=False)]
        st.markdown(render_table_html(df), unsafe_allow_html=True)

        # Downloads
        header_block = build_header_block(
            uk_date=_uk_date(date.today()),
            customer_name=customer_name,
            prison_name=prison_choice,
            region=region
        )

        c1, c2 = st.columns(2)
        with c1:
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
                "Instructor Allocation (%)": effective_instructor_pct,
                "Labour Output (%)": prisoner_output,
                "Employment Support": employment_support,
                "Contracts Overseen": contracts,
                "Additional Prison Benefits?": "Yes" if benefits_yes else "No",
                "Benefits Notes": benefits_text,
                "VAT Rate (%)": 20.0,
            }
            csv_bytes = export_csv_single_row(common, df, None)
            st.download_button(
                "Download CSV (Production)",
                data=csv_bytes,
                file_name="production_quote.csv",
                mime="text/csv"
            )
        with c2:
            st.download_button(
                "Download PDF-ready HTML (Production)",
                data=export_html(None, df, title="Production Quote", header_block=header_block, segregated_df=None),
                file_name="production_quote.html",
                mime="text/html"
            )