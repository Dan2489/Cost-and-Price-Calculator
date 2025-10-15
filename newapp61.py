import streamlit as st
import pandas as pd
from datetime import date

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
# Sidebar (now only Output%)
# -------------------------------
# Returns (lock_overheads=False, instructor_pct=100, prisoner_output)
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

benefits_yes = st.selectbox("Any additional prison benefits that you feel warrant a further reduction?", ["No", "Yes"]) == "Yes"
benefits_desc = ""
if benefits_yes:
    benefits_desc = st.text_area("Describe the benefits", placeholder="Explain the additional prison benefits…")
BENEFITS_DISCOUNT_PC = 0.10 if benefits_yes else 0.00  # 10% off Instructor Salary when benefits apply

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
def _uk_date(d: date) -> str:
    return d.strftime("%d/%m/%Y")

def _dev_rate_from_support(s: str) -> float:
    if s == "None":
        return 0.20
    if s in ("Employment on release/RoTL", "Post release"):
        return 0.10
    return 0.00  # Both

def _get_num_from(df, item_contains: str) -> float:
    """Read numeric Amount (£) from a row where Item contains substring (case-insensitive)."""
    try:
        m = df["Item"].astype(str).str.contains(item_contains, case=False, na=False, regex=False)
        if m.any():
            val = str(df.loc[m, "Amount (£)"].iloc[-1]).replace("£", "").replace(",", "")
            return float(val)
    except Exception:
        pass
    return 0.0

def _set_or_add_row(df, item_name: str, amount: float, after_item_contains: str = None):
    """Set existing row by item label, or insert a new row after a given anchor (by contains)."""
    df2 = df.copy()
    m = df2["Item"].astype(str).str.lower() == item_name.lower()
    if m.any():
        df2.loc[m, "Amount (£)"] = round(amount, 2)
        return df2

    # Insert
    insert_at = len(df2)
    if after_item_contains:
        m2 = df2["Item"].astype(str).str.contains(after_item_contains, case=False, na=False, regex=False)
        if m2.any():
            insert_at = m2[m2].index.max() + 1
    new_row = pd.DataFrame([{"Item": item_name, "Amount (£)": round(amount, 2)}])
    top = df2.iloc[:insert_at]
    bottom = df2.iloc[insert_at:]
    return pd.concat([top, new_row, bottom], ignore_index=True)

def _recalc_host_totals(df, vat_rate=0.20):
    """Recalculate Subtotal, VAT, Grand Total in host df."""
    df2 = df.copy()
    # Remove old totals
    df2 = df2[~df2["Item"].astype(str).str.contains("Subtotal|Grand Total|VAT", case=False, na=False, regex=True)]
    subtotal = df2["Amount (£)"].apply(lambda x: float(str(x).replace("£","").replace(",","")) if str(x).strip() != "" else 0.0).sum()
    vat = subtotal * vat_rate
    grand = subtotal + vat
    df2 = _set_or_add_row(df2, "Subtotal (ex VAT)", subtotal)
    df2 = _set_or_add_row(df2, "VAT (20%)", vat, after_item_contains="Subtotal")
    df2 = _set_or_add_row(df2, "Grand Total (inc VAT)", grand, after_item_contains="VAT")
    return df2

def _apply_benefits_discount_host(df: pd.DataFrame, benefits_pc: float, employment_support: str) -> pd.DataFrame:
    """
    Apply benefits discount to Instructor Salary (reduce by benefits_pc),
    then recompute Overheads (proportional to instructor),
    and Development charge (baseline 20% of Overheads) + reduction to revised based on employment support.
    Preserve order and hide zero rows in display layer.
    """
    if df is None or df.empty or benefits_pc <= 0:
        return df

    dev_rate = _dev_rate_from_support(employment_support)
    base_rate = 0.20  # "Development charge" baseline before reduction

    df2 = df.copy()

    inst_orig = _get_num_from(df2, "Instructor Salary")
    over_orig = _get_num_from(df2, "Overheads")
    # try revised first (if file previously produced both)
    dev_revised_orig = _get_num_from(df2, "Revised development charge")
    dev_before_orig = _get_num_from(df2, "Development charge (before")
    if dev_before_orig == 0.0:  # or just "Development charge"
        dev_before_orig = _get_num_from(df2, "Development charge")
    dev_red_orig = _get_num_from(df2, "Development Reduction")

    # New instructor after benefits
    inst_new = inst_orig * (1.0 - benefits_pc)

    # Scale overheads by same instructor ratio (fall back to 61% if missing/zero)
    if inst_orig > 0 and over_orig > 0:
        scale = inst_new / inst_orig
        over_new = over_orig * scale
    else:
        over_new = inst_new * 0.61  # safe default

    # Rebuild Development: baseline 20% of Overheads, revised = dev_rate * Overheads
    dev_before_new = over_new * base_rate
    dev_revised_new = over_new * dev_rate
    dev_red_new = max(0.0, dev_before_new - dev_revised_new)

    # Add/Update rows (and an explicit benefits reduction row)
    # 1) Instructor Salary
    df2 = _set_or_add_row(df2, "Instructor Salary", inst_new)
    # 2) Benefits reduction (red)
    benefits_amt = inst_orig - inst_new
    if benefits_amt > 0:
        df2 = _set_or_add_row(df2, "Additional benefits reduction", -benefits_amt, after_item_contains="Instructor Salary")
    # 3) Overheads
    df2 = _set_or_add_row(df2, "Overheads", over_new)
    # 4) Dev rows
    df2 = _set_or_add_row(df2, "Development charge (before reduction)", dev_before_new)
    if dev_red_new > 0:
        df2 = _set_or_add_row(df2, "Development Reduction", -dev_red_new, after_item_contains="Development charge (before")
    df2 = _set_or_add_row(df2, "Revised development charge", dev_revised_new)

    # Re-totals
    df2 = _recalc_host_totals(df2, vat_rate=0.20)
    return df2

# -------------------------------
# HOST
# -------------------------------
if contract_type == "Host":
    if st.button("Generate Host Costs"):
        errs = validate_inputs()
        if errs:
            st.error("Fix errors:\n- " + "\n- ".join(errs))
        else:
            # instructor_pct no longer used by UI; compute from hours/contracts (capped 100)
            effective_pct = min(100.0, (workshop_hours / 37.5) * (1.0 / contracts) * 100.0) if contracts > 0 and workshop_hours > 0 else 0.0
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
                instructor_allocation=effective_pct,
                lock_overheads=False,  # removed from UI
            )
            # Apply benefits discount post-generation (so totals/dev recalc correctly)
            if BENEFITS_DISCOUNT_PC > 0 and not customer_covers_supervisors:
                host_df = _apply_benefits_discount_host(host_df, BENEFITS_DISCOUNT_PC, employment_support)

            st.session_state["host_df"] = host_df

    if "host_df" in st.session_state:
        df = st.session_state["host_df"].copy()
        # Colour reductions red (both development reduction and additional benefits reduction)
        if "Item" in df.columns:
            df_display = df.copy()
            df_display["Item"] = df_display["Item"].apply(
                lambda x: f"<span style='color:red'>{x}</span>"
                if any(key in str(x).lower() for key in ["reduction", "benefits reduction"])
                else x
            )
            st.markdown(render_table_html(df_display), unsafe_allow_html=True)
        else:
            st.markdown(render_table_html(df), unsafe_allow_html=True)

        # === Downloads ===
        header_block = build_header_block(
            uk_date=_uk_date(date.today()),
            customer_name=customer_name,
            prison_name=prison_choice,
            region=region,
            benefits_desc=benefits_desc if benefits_yes else None
        )

        # Flat one-row CSV (Host)
        source_df = st.session_state["host_df"].copy()

        def _grab_amount(needle: str) -> float:
            return _get_num_from(source_df, needle)

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
            "Benefits Applied (%)": BENEFITS_DISCOUNT_PC * 100.0,
            "Benefits Notes": benefits_desc if benefits_yes else "",
        }
        amounts = {
            "Host: Prisoner wages (£/month)": _grab_amount("Prisoner Wages"),
            "Host: Instructor Salary (£/month)": _grab_amount("Instructor Salary"),
            "Host: Overheads (£/month)": _grab_amount("Overheads"),
            "Host: Development charge (before) (£/month)": _grab_amount("Development charge (before"),
            "Host: Development Reduction (£/month)": _grab_amount("Development Reduction"),
            "Host: Revised development charge (£/month)": _grab_amount("Revised development charge"),
            "Host: Additional benefits reduction (£/month)": _grab_amount("Additional benefits reduction"),
            "Host: Subtotal (£/month)": _grab_amount("Subtotal"),
            "Host: VAT (£/month)": _grab_amount("VAT"),
            "Host: Grand Total (£/month)": _grab_amount("Grand Total"),
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
                    # instructor % follows the same rule as host: hours/contracts
                    effective_pct = min(100.0, (workshop_hours / 37.5) * (1.0 / contracts) * 100.0) if contracts > 0 and workshop_hours > 0 else 0.0
                    results = calculate_production_contractual(
                        items, int(prisoner_output),
                        workshop_hours=float(workshop_hours),
                        prisoner_salary=float(prisoner_salary),
                        supervisor_salaries=supervisor_salaries,
                        effective_pct=float(effective_pct),
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
                        benefits_discount_pc=BENEFITS_DISCOUNT_PC  # production also respects benefits
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
                effective_pct = min(100.0, (workshop_hours / 37.5) * (1.0 / contracts) * 100.0) if contracts > 0 and workshop_hours > 0 else 0.0
                result = calculate_adhoc(
                    lines, int(prisoner_output),
                    workshop_hours=float(workshop_hours),
                    num_prisoners=int(num_prisoners),
                    prisoner_salary=float(prisoner_salary),
                    supervisor_salaries=supervisor_salaries,
                    effective_pct=float(effective_pct),
                    customer_covers_supervisors=customer_covers_supervisors,
                    region=region,
                    customer_type="Commercial",
                    apply_vat=True, vat_rate=20.0,
                    dev_rate=_dev_rate_from_support(employment_support),
                    today=date.today(),
                    lock_overheads=False,
                    employment_support=employment_support,
                    benefits_discount_pc=BENEFITS_DISCOUNT_PC
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

        # Downloads (Production)
        header_block = build_header_block(
            uk_date=_uk_date(date.today()),
            customer_name=customer_name,
            prison_name=prison_choice,
            region=region,
            benefits_desc=benefits_desc if benefits_yes else None
        )

        c1, c2 = st.columns(2)
        with c1:
            # Single-row CSV (no segregated table now)
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
                "VAT Rate (%)": 20.0,
                "Benefits Applied (%)": BENEFITS_DISCOUNT_PC * 100.0,
                "Benefits Notes": benefits_desc if benefits_yes else "",
            }
            csv_bytes = export_csv_single_row(common, df, segregated_df=None)
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