# newapp61.py  — FULL FILE

import streamlit as st
import pandas as pd
from datetime import date

from config61 import CFG
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
from utils61 import (
    inject_govuk_css,
    fmt_currency,
    export_csv_single_row,
    export_csv_bytes_rows,
    export_html,
    render_table_html,
    build_header_block,
)
from production61 import (
    labour_minutes_budget,
    calculate_production_contractual,
    calculate_adhoc,
)
import host61


# -------------------------------
# Page setup
# -------------------------------
st.set_page_config(page_title="Cost and Price Calculator", page_icon="💷", layout="centered")
inject_govuk_css()
st.title("Cost and Price Calculator")


# -------------------------------
# Base inputs (no instructor slider / no lock-overheads control)
# -------------------------------
with st.sidebar:
    prisoner_output = st.slider("Prisoner labour output (%)", min_value=0, max_value=100, value=CFG.GLOBAL_OUTPUT_DEFAULT, step=1)

prisons_sorted = ["Select"] + sorted(PRISON_TO_REGION.keys())
prison_choice = st.selectbox("Prison Name", prisons_sorted, index=0, key="prison_choice")
region = PRISON_TO_REGION.get(prison_choice, "Select") if prison_choice != "Select" else "Select"
st.session_state["region"] = region

customer_name = st.text_input("Customer Name", key="customer_name")
contract_type = st.selectbox("Contract Type", ["Select", "Host", "Production"], key="contract_type")

workshop_hours = st.number_input("How many hours is the workshop open per week?", min_value=0.0, format="%.2f")
num_prisoners = st.number_input("How many prisoners employed per week?", min_value=0, step=1)
prisoner_salary = st.number_input("Average prisoner salary per week (£)", min_value=0.0, format="%.2f")

# Instructors
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

# Contracts: hide control if customer provides instructors (assume 1)
if not customer_covers_supervisors:
    contracts = st.number_input("How many contracts do they oversee in this workshop?", min_value=1, value=1)
else:
    contracts = 1

# Employment support (renamed option)
employment_support = st.selectbox(
    "What employment support does the customer offer?",
    ["None", "Employment on release/RoTL", "Pre-release support", "Both"],
)

# Additional benefits (applies only alongside "Both")
additional_benefits = st.checkbox("Are there any additional benefits to the prison?", value=False)
additional_benefits_desc = ""
if additional_benefits:
    additional_benefits_desc = st.text_area("Please describe the additional benefits", value="")

# -------------------------------
# Helpers / validation
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


def _uk_date(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _dev_rate_from_support(s: str) -> float:
    s = (s or "").lower()
    if "both" in s:
        return 0.0
    if "employment on release/rotl" in s or "pre-release support" in s:
        return 0.10
    return 0.20


# -------------------------------
# HOST
# -------------------------------
if contract_type == "Host":
    if st.button("Generate Host Costs"):
        errs = validate_inputs()
        if errs:
            st.error("Fix errors:\n- " + "\n- ".join(errs))
        else:
            # host61 must contain the function shown in your last message (with additional_benefits param)
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
                additional_benefits=additional_benefits,
            )
            st.session_state["host_df"] = host_df

    if "host_df" in st.session_state:
        df = st.session_state["host_df"].copy()

        # Red for discount rows
        if "Item" in df.columns:
            df_display = df.copy()
            df_display["Item"] = df_display["Item"].apply(
                lambda x: f"<span style='color:red'>{x}</span>" if any(w in str(x).lower() for w in ["reduction", "discount"]) else x
            )
            st.markdown(render_table_html(df_display), unsafe_allow_html=True)
        else:
            st.markdown(render_table_html(df), unsafe_allow_html=True)

        # Downloads
        header_block = build_header_block(
            uk_date=_uk_date(date.today()),
            customer_name=customer_name,
            prison_name=prison_choice,
            region=region
        )

        # Flatten for CSV
        source_df = st.session_state["host_df"].copy()

        def _grab_amount(needle: str) -> float:
            try:
                m = source_df["Item"].astype(str).str.contains(needle, case=False, na=False)
                if m.any():
                    raw = str(source_df.loc[m, "Amount (£)"].iloc[-1]).replace("£", "").replace(",", "")
                    return float(raw)
            except Exception:
                pass
            return 0.0

        dev_before_amt  = _grab_amount("Development Charge (before")
        dev_single_amt  = _grab_amount("Development charge")
        dev_revised_amt = _grab_amount("Revised development charge")

        amounts = {
            "Host: Prisoner wages (£/month)": _grab_amount("Prisoner Wages"),
            "Host: Instructor cost (£/month)": _grab_amount("Instructor Salary"),  # displayed label is "Instructor cost"
            "Host: Overheads (£/month)": _grab_amount("Overheads"),                # label without (61%)
            "Host: Development charge (£/month)": dev_before_amt if dev_before_amt > 0 else dev_single_amt,
            "Host: Development Reduction (£/month)": _grab_amount("Development charge discount"),
            "Host: Development Revised (£/month)": dev_revised_amt if dev_revised_amt > 0 else dev_single_amt,
            "Host: Additional benefit discount (£/month)": _grab_amount("Additional benefit discount"),
            "Host: Grand Total (£/month)": _grab_amount("Grand Total (£/month)"),
            "Host: VAT (£/month)": _grab_amount("VAT (20%)"),
            "Host: Grand Total + VAT (£/month)": _grab_amount("Grand Total + VAT"),
        }

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
            "Additional Benefits (desc)": additional_benefits_desc,
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

                # Capacity
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
                    # Production: customers do NOT provide instructors for costing
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

                    # Show the main items/pricing table
                    display_cols = ["Item", "Output %", "Capacity (units/week)", "Units/week",
                                    "Unit Price ex VAT (£)", "Unit Price inc VAT (£)",
                                    "Monthly Total ex VAT (£)", "Monthly Total inc VAT (£)"]
                    if pricing_mode_key == "target":
                        display_cols += ["Feasible", "Note"]

                    df = pd.DataFrame([{
                        k: (None if r.get(k) is None else (round(float(r.get(k)), 4) if isinstance(r.get(k), (int, float)) else r.get(k)))
                        for k in display_cols
                    } for r in results])

                    st.markdown(render_table_html(df), unsafe_allow_html=True)

                    # ===== Monthly Breakdown (ex VAT) — excludes prisoner wages =====
                    # Weekly pools (hours/contract split)
                    hours_frac = (float(workshop_hours) / 37.5) if workshop_hours > 0 else 0.0
                    contracts_safe = max(1, int(contracts))
                    inst_weekly_total = sum((s / 52.0) * hours_frac / contracts_safe for s in supervisor_salaries)
                    overheads_weekly = inst_weekly_total * 0.61

                    # Dev on (Inst + OH)
                    dev_rate_eff = _dev_rate_from_support(employment_support)
                    dev_weekly_before = (inst_weekly_total + overheads_weekly) * 0.20
                    dev_weekly_actual = (inst_weekly_total + overheads_weekly) * dev_rate_eff
                    dev_weekly_discount = max(0.0, dev_weekly_before - dev_weekly_actual)

                    # Additional benefit discount — only if Both AND benefits ticked; 10% of Instructor cost
                    addl_benefit_monthly = 0.0
                    if employment_support == "Both" and additional_benefits:
                        addl_benefit_monthly = (inst_weekly_total * 52.0 / 12.0) * 0.10

                    inst_monthly       = inst_weekly_total * 52.0 / 12.0
                    overheads_monthly  = overheads_weekly * 52.0 / 12.0
                    dev_before_monthly = dev_weekly_before * 52.0 / 12.0
                    dev_actual_monthly = dev_weekly_actual * 52.0 / 12.0
                    dev_disc_monthly   = dev_weekly_discount * 52.0 / 12.0

                    subtotal_monthly_ex_vat = inst_monthly + overheads_monthly + dev_actual_monthly - addl_benefit_monthly
                    total_with_vat_monthly  = subtotal_monthly_ex_vat * 1.20

                    breakdown_rows = [
                        ("Instructor cost",                          inst_monthly),
                        ("Overheads",                                overheads_monthly),
                        ("Development charge (on Inst+OH)",          dev_before_monthly),
                        ("Development discount",                    -dev_disc_monthly),
                        ("Revised development charge",               dev_actual_monthly),
                    ]
                    if addl_benefit_monthly > 0:
                        breakdown_rows.append(("Additional benefit discount", -addl_benefit_monthly))

                    breakdown_rows.append(("Subtotal (ex VAT £/month)",      subtotal_monthly_ex_vat))
                    breakdown_rows.append(("Total with VAT (£/month)",        total_with_vat_monthly))

                    prod_breakdown_df = pd.DataFrame(breakdown_rows, columns=["Item", "Amount (£)"])
                    prod_breakdown_df["Amount (£)"] = prod_breakdown_df["Amount (£)"].apply(fmt_currency)

                    st.markdown("### Monthly Breakdown (ex VAT) — excludes prisoner wages")
                    st.markdown(render_table_html(prod_breakdown_df), unsafe_allow_html=True)

                    # ===== Unit cost (prisoner-only) & Units required per month =====
                    # Use the same minutes-share as for pricing (by assigned minutes)
                    denom_minutes = sum(int(it.get("assigned", 0)) * workshop_hours * 60.0 for it in items)
                    unit_rows = []
                    for idx, it in enumerate(items):
                        name          = (it.get("name") or f"Item {idx+1}").strip()
                        pris_assigned = int(it.get("assigned", 0))

                        try:
                            units_week = float(df.loc[idx, "Units/week"])
                        except Exception:
                            units_week = 0.0

                        minutes_this = pris_assigned * workshop_hours * 60.0
                        share = (minutes_this / denom_minutes) if denom_minutes > 0 else 0.0

                        # Prisoner-only unit cost (monthly)
                        if units_week and pris_assigned > 0:
                            unit_cost_prisoner_only_week = (pris_assigned * prisoner_salary) / units_week
                            unit_cost_prisoner_only_month = unit_cost_prisoner_only_week * 52.0 / 12.0
                        else:
                            unit_cost_prisoner_only_month = None

                        # Allocate non-prisoner monthly subtotal by share
                        allocated_non_prisoner_month = subtotal_monthly_ex_vat * share

                        if unit_cost_prisoner_only_month and unit_cost_prisoner_only_month > 0:
                            units_required_cover = allocated_non_prisoner_month / unit_cost_prisoner_only_month
                        else:
                            units_required_cover = None

                        unit_rows.append({
                            "Item": name,
                            "Unit cost (prisoner only, £/unit per month)": None if unit_cost_prisoner_only_month is None else round(unit_cost_prisoner_only_month, 4),
                            "Units required (per month) to cover non-prisoner costs": None if units_required_cover is None else int(round(units_required_cover)),
                        })

                    prod_units_df = pd.DataFrame(unit_rows, columns=[
                        "Item",
                        "Unit cost (prisoner only, £/unit per month)",
                        "Units required (per month) to cover non-prisoner costs",
                    ])

                    st.markdown("### Unit Costs & Units Required (Prisoner wages only)")
                    st.markdown(render_table_html(prod_units_df), unsafe_allow_html=True)

                    # Persist the main items table for downloads
                    st.session_state["prod_df"] = df

                    # Downloads (Production)
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
                            "Customer Provides Instructors": "No",  # enforced for Production pricing
                            "Labour Output (%)": prisoner_output,
                            "Employment Support": employment_support,
                            "Contracts Overseen": contracts,
                            "VAT Rate (%)": 20.0,
                            "Additional Benefits": "Yes" if additional_benefits else "No",
                            "Additional Benefits (desc)": additional_benefits_desc,
                        }
                        # Export just the main items table (as before). If you want the two extra tables in CSV/PDF,
                        # add them into export_html/export_csv in utils61.
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
                    customer_covers_supervisors=False,
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
                    # Display ad-hoc table
                    adhoc_rows = []
                    for p in result.get("per_line", []):
                        adhoc_rows.append({
                            "Item": p.get("name", "—"),
                            "Units": p.get("units", 0),
                            "Unit Cost (ex VAT £)": round(p.get("unit_cost_ex_vat", 0.0), 2),
                            "Unit Cost (inc VAT £)": round(p.get("unit_cost_inc_vat", 0.0), 2),
                            "Line Total (ex VAT £)": round(p.get("line_total_ex_vat", 0.0), 2),
                            "Line Total (inc VAT £)": round(p.get("line_total_inc_vat", 0.0), 2),
                        })
                    adhoc_df = pd.DataFrame(adhoc_rows, columns=[
                        "Item", "Units", "Unit Cost (ex VAT £)", "Unit Cost (inc VAT £)",
                        "Line Total (ex VAT £)", "Line Total (inc VAT £)"
                    ])
                    st.markdown(render_table_html(adhoc_df), unsafe_allow_html=True)

                    # Downloads (Ad-hoc)
                    header_block = build_header_block(
                        uk_date=_uk_date(date.today()),
                        customer_name=customer_name,
                        prison_name=prison_choice,
                        region=region
                    )
                    c1, c2 = st.columns(2)
                    with c1:
                        common = {
                            "Quote Type": "Production (Ad-hoc)",
                            "Date": _uk_date(date.today()),
                            "Prison Name": prison_choice,
                            "Region": region,
                            "Customer Name": customer_name,
                            "Contract Type": "Production",
                            "Workshop Hours / week": workshop_hours,
                            "Prisoners Employed": num_prisoners,
                            "Prisoner Salary / week": prisoner_salary,
                            "Instructors Count": num_supervisors,
                            "Customer Provides Instructors": "No",
                            "Labour Output (%)": prisoner_output,
                            "Employment Support": employment_support,
                            "Contracts Overseen": contracts,
                            "VAT Rate (%)": 20.0,
                            "Additional Benefits": "Yes" if additional_benefits else "No",
                            "Additional Benefits (desc)": additional_benefits_desc,
                        }
                        csv_bytes = export_csv_single_row(common, adhoc_df, None)
                        st.download_button(
                            "Download CSV (Ad-hoc)",
                            data=csv_bytes,
                            file_name="production_adhoc_quote.csv",
                            mime="text/csv"
                        )
                    with c2:
                        st.download_button(
                            "Download PDF-ready HTML (Ad-hoc)",
                            data=export_html(None, adhoc_df, title="Production Quote (Ad-hoc)", header_block=header_block, segregated_df=None),
                            file_name="production_adhoc_quote.html",
                            mime="text/html"
                        )