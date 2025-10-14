import streamlit as st
import pandas as pd
from datetime import date

from config61 import CFG
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
from utils61 import (
    inject_govuk_css, fmt_currency,
    export_html, render_table_html, build_header_block,
    export_csv_bytes_rows,
)

# ===============================
# Helpers (local to this app)
# ===============================

def _uk_date(d: date) -> str:
    return d.strftime("%d/%m/%Y")

def _recommended_allocation(hours_per_week: float, contracts: int) -> float:
    """Workshop-hours/37.5 divided by number of contracts, as a percent (cap 100)."""
    if hours_per_week <= 0 or contracts <= 0:
        return 0.0
    return min(100.0, round((hours_per_week / 37.5) * (1.0 / contracts) * 100.0, 1))

def _dev_rate_from_support(s: str) -> float:
    # Business rule: None = 20%, RoTL/Post = 10%, Both = 0%
    if s == "None":
        return 0.20
    if s in ("Employment on release/RoTL", "Post release"):
        return 0.10
    return 0.00

def _currency_to_float(x):
    try:
        if x is None:
            return 0.0
        s = str(x)
        for ch in ["£", ",", " "]:
            s = s.replace(ch, "")
        # remove a prefixed minus if it came as "- £123" etc.
        s = s.replace("-", "-").replace("–", "-")
        s = s.strip()
        # strip any trailing text
        keep = "".join(ch for ch in s if ch.isdigit() or ch in ".-")
        return float(keep) if keep not in ("", "-", ".", "-.") else 0.0
    except Exception:
        return 0.0

def _build_host_summary_rows(
    *,
    num_prisoners: int,
    prisoner_salary_week: float,
    instructor_month_base: float,
    overheads_month_from_base: float,
    dev_rate: float,
    benefits_discount_pct: float
) -> pd.DataFrame:
    """
    Constructs the exact summary table layout required, including:
    - Development charge (before)
    - Development reduction (red, if any)
    - Revised development charge
    - Additional benefits reduction (red, if selected)
    - Totals and VAT
    """
    prisoner_month = num_prisoners * prisoner_salary_week * 52.0 / 12.0

    # Benefits: 10% reduction on instructor salary only
    benefits_reduction = instructor_month_base * benefits_discount_pct if benefits_discount_pct > 0 else 0.0
    instructor_after_benefit = instructor_month_base - benefits_reduction

    # Dev: computed on overheads (based on base instructor, not reduced)
    dev_before = overheads_month_from_base * 0.20  # STANDARD baseline shown as "before"
    dev_revised = overheads_month_from_base * dev_rate
    dev_reduction = max(0.0, dev_before - dev_revised)

    grand_ex_vat = prisoner_month + instructor_after_benefit + overheads_month_from_base + dev_revised
    vat = grand_ex_vat * 0.20
    grand_inc_vat = grand_ex_vat + vat

    rows = []
    rows.append({"Item": "Prisoner Wages", "Amount (£)": fmt_currency(prisoner_month)})
    rows.append({"Item": "Instructor Salary", "Amount (£)": fmt_currency(instructor_after_benefit)})
    rows.append({"Item": "Overheads", "Amount (£)": fmt_currency(overheads_month_from_base)})
    rows.append({"Item": "Development charge (before)", "Amount (£)": fmt_currency(dev_before)})

    if dev_reduction > 0:
        rows.append({"Item": "<span style='color:#d4351c;'>Development reduction</span>",
                     "Amount (£)": f"<span style='color:#d4351c;'>- {fmt_currency(dev_reduction)}</span>"})

    rows.append({"Item": "Revised development charge", "Amount (£)": fmt_currency(dev_revised)})

    if benefits_reduction > 0:
        rows.append({"Item": "<span style='color:#d4351c;'>Additional benefits reduction</span>",
                     "Amount (£)": f"<span style='color:#d4351c;'>- {fmt_currency(benefits_reduction)}</span>"})

    rows.append({"Item": "Grand Total (ex VAT)", "Amount (£)": fmt_currency(grand_ex_vat)})
    rows.append({"Item": "VAT (20%)", "Amount (£)": fmt_currency(vat)})
    rows.append({"Item": "Grand Total (inc VAT)", "Amount (£)": fmt_currency(grand_inc_vat)})

    return pd.DataFrame(rows)

def _calc_instructor_month_from_titles(titles, region: str, allocation_pct: float) -> float:
    """Sum the selected titles' annual pay, convert to monthly, apply allocation %."""
    if not titles:
        return 0.0
    pays = []
    region_titles = SUPERVISOR_PAY.get(region, [])
    for chosen in titles:
        # chosen equals a title string; find its avg_total
        match = next((t["avg_total"] for t in region_titles if t["title"] == chosen), None)
        if match is not None:
            pays.append(float(match))
    total_annual = sum(pays)
    return (total_annual / 12.0) * (allocation_pct / 100.0)

def _calc_overheads_from_instructor_base_month(instructor_month_base: float) -> float:
    return instructor_month_base * 0.61

def _prod_capacity(assigned: int, hours_per_week: float, minutes_per: float, pris_required: int) -> float:
    if assigned > 0 and hours_per_week > 0 and pris_required > 0 and minutes_per > 0:
        return (assigned * hours_per_week * 60.0) / (minutes_per * pris_required)
    return 0.0

# ===============================
# Page setup
# ===============================
st.set_page_config(page_title="Cost and Price Calculator", page_icon="💷", layout="centered")
inject_govuk_css()
st.title("Cost and Price Calculator")

# ===============================
# Sidebar (only labour output slider)
# ===============================
with st.sidebar:
    st.header("Controls")
    prisoner_output = st.slider("Prisoner labour output (%)", 0, 100, CFG.GLOBAL_OUTPUT_DEFAULT, step=1)

# ===============================
# Base inputs
# ===============================
prisons_sorted = ["Select"] + sorted(PRISON_TO_REGION.keys())
prison_choice = st.selectbox("Prison Name", prisons_sorted, index=0, key="prison_choice")
region = PRISON_TO_REGION.get(prison_choice, "Select") if prison_choice != "Select" else "Select"

customer_name = st.text_input("Customer Name", key="customer_name")
contract_type = st.selectbox("Contract Type", ["Select", "Host", "Production"], key="contract_type")

workshop_hours = st.number_input("How many hours is the workshop open per week?", min_value=0.0, format="%.2f")
num_prisoners = st.number_input("How many prisoners employed per week?", min_value=0, step=1)
prisoner_salary = st.number_input("Average prisoner salary per week (£)", min_value=0.0, format="%.2f")

# Instructors (required at full contract capacity)
num_supervisors = st.number_input("How many instructors are required at full contract capacity.", min_value=1, step=1)
customer_covers_supervisors = st.checkbox("Customer provides Instructor(s)?", value=False)

selected_titles = []
if num_supervisors > 0 and region != "Select" and not customer_covers_supervisors:
    titles_for_region = SUPERVISOR_PAY.get(region, [])
    title_options = [t["title"] for t in titles_for_region]
    for i in range(int(num_supervisors)):
        sel = st.selectbox(f"Instructor {i+1} Title", title_options, key=f"inst_title_{i}")
        st.caption(f"{region} — £{next(t['avg_total'] for t in titles_for_region if t['title']==sel):,.0f}")
        selected_titles.append(sel)

contracts = st.number_input("How many contracts do they oversee in this workshop?", min_value=1, value=1)

employment_support = st.selectbox(
    "What employment support does the customer offer?",
    ["None", "Employment on release/RoTL", "Post release", "Both"],
)

# Additional prison benefits
benefits_choice = st.radio(
    "Any additional prison benefits that you feel warrant a further reduction?",
    ["No", "Yes"], index=0, horizontal=True
)
benefits_text = ""
if benefits_choice == "Yes":
    benefits_text = st.text_area("Describe the benefits")
benefits_discount_pct = 0.10 if benefits_choice == "Yes" else 0.0

# Internal effective allocation (not shown)
effective_allocation_pct = _recommended_allocation(workshop_hours, int(contracts))

# ===============================
# HOST
# ===============================
if contract_type == "Host":

    if st.button("Generate Host Costs"):
        errs = []
        if prison_choice == "Select": errs.append("Select prison")
        if region == "Select": errs.append("Region could not be derived from prison selection")
        if not str(customer_name).strip(): errs.append("Enter customer name")
        if workshop_hours <= 0: errs.append("Workshop hours must be greater than zero")
        if not customer_covers_supervisors and len(selected_titles) != int(num_supervisors):
            errs.append("Choose a title for each instructor")
        if errs:
            st.error("Fix errors:\n- " + "\n- ".join(errs))
        else:
            # Build summary from business rules (no external host61 dependency)
            instr_month_base = 0.0 if customer_covers_supervisors else _calc_instructor_month_from_titles(
                selected_titles, region, effective_allocation_pct
            )
            overheads_month = 0.0 if customer_covers_supervisors else _calc_overheads_from_instructor_base_month(instr_month_base)
            dev_rate = _dev_rate_from_support(employment_support)

            host_df = _build_host_summary_rows(
                num_prisoners=int(num_prisoners),
                prisoner_salary_week=float(prisoner_salary),
                instructor_month_base=instr_month_base,
                overheads_month_from_base=overheads_month,
                dev_rate=dev_rate,
                benefits_discount_pct=benefits_discount_pct
            )

            st.session_state["host_df"] = host_df
            st.session_state["host_ctx"] = {
                "benefits_text": benefits_text,
                "benefits_flag": benefits_choice,
                "employment_support": employment_support,
                "effective_allocation_pct": effective_allocation_pct,
                "customer_covers_supervisors": customer_covers_supervisors,
                "selected_titles": selected_titles,
            }

    if "host_df" in st.session_state:
        df = st.session_state["host_df"].copy()
        st.markdown(render_table_html(df), unsafe_allow_html=True)

        # Downloads
        header_block = build_header_block(
            uk_date=_uk_date(date.today()),
            customer_name=customer_name,
            prison_name=prison_choice,
            region=region
        )

        # For CSV, parse numeric again from displayed df (safe & consistent)
        def _grab(df_in: pd.DataFrame, label: str) -> float:
            m = df_in["Item"].astype(str).str.contains(label, case=False, na=False)
            if m.any():
                return _currency_to_float(df_in.loc[m, "Amount (£)"].iloc[-1])
            return 0.0

        prisoner_month   = _grab(df, "Prisoner Wages")
        instructor_month = _grab(df, "Instructor Salary")
        overheads_month  = _grab(df, "Overheads")
        dev_before       = _grab(df, "Development charge (before)")
        dev_reduction    = _grab(df, "Development reduction")
        dev_revised      = _grab(df, "Revised development charge")
        benefits_reduct  = _grab(df, "Additional benefits reduction")
        grand_ex_vat     = _grab(df, "Grand Total (ex VAT)")
        vat_month        = _grab(df, "VAT (20%)")
        grand_inc_vat    = _grab(df, "Grand Total (inc VAT)")

        ctx = st.session_state.get("host_ctx", {})
        csv_row = {
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
            "Customer Provides Instructors": "Yes" if ctx.get("customer_covers_supervisors") else "No",
            "Employment Support": ctx.get("employment_support", employment_support),
            "Effective Instructor Allocation (%)": ctx.get("effective_allocation_pct", effective_allocation_pct),
            "Additional Benefits": ctx.get("benefits_flag", "No"),
            "Benefits Description": ctx.get("benefits_text", ""),
            # results
            "Host: Prisoner wages (£/month)": prisoner_month,
            "Host: Instructor Salary (£/month)": instructor_month,
            "Host: Overheads (£/month)": overheads_month,
            "Host: Development charge (before £/month)": dev_before,
            "Host: Development Reduction (£/month)": dev_reduction,
            "Host: Revised development charge (£/month)": dev_revised,
            "Host: Additional benefits reduction (£/month)": benefits_reduct,
            "Host: Grand Total (ex VAT £/month)": grand_ex_vat,
            "Host: VAT (£/month)": vat_month,
            "Host: Grand Total (inc VAT £/month)": grand_inc_vat,
        }

        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "Download CSV (Host)",
                data=export_csv_bytes_rows([csv_row]),
                file_name="host_quote.csv",
                mime="text/csv"
            )
        with c2:
            st.download_button(
                "Download PDF-ready HTML (Host)",
                data=export_html(df, None, title="Host Quote", header_block=header_block, segregated_df=None),
                file_name="host_quote.html",
                mime="text/html"
            )

# ===============================
# PRODUCTION
# ===============================
if contract_type == "Production":
    st.markdown("---")
    st.subheader("Production settings")

    output_pct = int(prisoner_output)
    out_scale = float(output_pct) / 100.0

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
                ["Minutes", "Seconds"], index=0, key=f"mins_unit_{i}", horizontal=True
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

            # Preview capacity
            cap_100 = _prod_capacity(int(assigned), float(workshop_hours), float(minutes_per), int(required))
            cap_planned = cap_100 * out_scale
            st.caption(f"{disp} capacity @ 100%: **{cap_100:.0f} units/week** · @ {output_pct}%: **{cap_planned:.0f}**")

            if pricing_mode_key == "target":
                tgt_default = int(round(cap_planned)) if cap_planned > 0 else 0
                tgt = st.number_input(f"Target units per week ({disp})", min_value=0, value=tgt_default, step=1, key=f"target_{i}")
                targets.append(int(tgt))

            items.append({"name": name, "required": int(required), "minutes": float(minutes_per), "assigned": int(assigned)})

    if st.button("Generate Production Costs", key="generate_contractual"):
        errs = []
        if prison_choice == "Select": errs.append("Select prison")
        if region == "Select": errs.append("Region could not be derived from prison selection")
        if not str(customer_name).strip(): errs.append("Enter customer name")
        if workshop_hours <= 0: errs.append("Workshop hours must be greater than zero")
        if not customer_covers_supervisors and len(selected_titles) != int(num_supervisors):
            errs.append("Choose a title for each instructor")

        if errs:
            st.error("Fix errors:\n- " + "\n- ".join(errs))
        else:
            # Use the same rules as Host
            effective_allocation_pct = _recommended_allocation(workshop_hours, int(contracts))
            instr_month_base = 0.0 if customer_covers_supervisors else _calc_instructor_month_from_titles(
                selected_titles, region, effective_allocation_pct
            )
            instr_week_after_benefit = (instr_month_base * (1.0 - (0.10 if benefits_choice == "Yes" else 0.0))) / (52.0/12.0)
            overheads_month = 0.0 if customer_covers_supervisors else _calc_overheads_from_instructor_base_month(instr_month_base)
            overheads_week = overheads_month / (52.0/12.0)
            dev_rate = _dev_rate_from_support(employment_support)
            dev_week = overheads_week * dev_rate

            total_minutes = sum(int(it["assigned"]) * workshop_hours * 60.0 for it in items)

            main_rows = []
            seg_rows = []
            monthly_excl_inst_sum = 0.0

            for idx, it in enumerate(items):
                name = (it.get("name") or "").strip() or f"Item {idx+1}"
                mins_per = float(it.get("minutes", 0.0))
                pris_req = max(1, int(it.get("required", 1)))
                pris_ass = int(it.get("assigned", 0))

                cap_100 = _prod_capacity(pris_ass, float(workshop_hours), mins_per, pris_req)
                cap_planned = cap_100 * out_scale

                if pricing_mode_key == "target" and targets and idx < len(targets or []):
                    units_week = float(max(0, int(targets[idx])))
                else:
                    units_week = float(cap_planned)

                share = ((pris_ass * workshop_hours * 60.0) / total_minutes) if total_minutes > 0 else 0.0

                prisoner_week = pris_ass * prisoner_salary
                overheads_item_week = overheads_week * share
                dev_item_week = dev_week * share
                instructor_item_week = instr_week_after_benefit * share

                weekly_excl = prisoner_week + overheads_item_week + dev_item_week
                weekly_incl = weekly_excl + instructor_item_week

                if units_week > 0:
                    unit_cost = weekly_incl / units_week
                    unit_price_ex = unit_cost
                    unit_price_inc = unit_price_ex * 1.20
                    monthly_total_ex = unit_price_ex * units_week * 52.0 / 12.0
                    monthly_total_inc = monthly_total_ex * 1.20
                else:
                    unit_cost = unit_price_ex = unit_price_inc = None
                    monthly_total_ex = monthly_total_inc = 0.0

                main_rows.append({
                    "Item": name,
                    "Output %": output_pct,
                    "Capacity (units/week)": int(round(cap_planned)) if cap_planned > 0 else 0,
                    "Units/week": int(round(units_week)) if units_week > 0 else 0,
                    "Unit Cost (£)": None if unit_cost is None else round(unit_cost, 4),
                    "Unit Price ex VAT (£)": None if unit_price_ex is None else round(unit_price_ex, 4),
                    "Unit Price inc VAT (£)": None if unit_price_inc is None else round(unit_price_inc, 4),
                    "Monthly Total ex VAT (£)": round(monthly_total_ex, 4),
                    "Monthly Total inc VAT (£)": round(monthly_total_inc, 4),
                })

                # segregated
                unit_cost_excl = (weekly_excl / units_week) if units_week > 0 else None
                monthly_excl = (unit_cost_excl * units_week * 52.0 / 12.0) if unit_cost_excl else 0.0
                monthly_excl_inst_sum += monthly_excl

                seg_rows.append({
                    "Item": name,
                    "Output %": output_pct,
                    "Capacity (units/week)": int(round(cap_planned)) if cap_planned > 0 else 0,
                    "Units/week": int(round(units_week)) if units_week > 0 else 0,
                    "Unit Cost excl Instructor (£)": None if unit_cost_excl is None else round(unit_cost_excl, 4),
                    "Monthly Total excl Instructor ex VAT (£)": round(monthly_excl, 4),
                })

            instr_month_after_benefit = instr_week_after_benefit * 52.0 / 12.0
            seg_rows.append({
                "Item": "Instructor Salary (monthly)",
                "Output %": "",
                "Capacity (units/week)": "",
                "Units/week": "",
                "Unit Cost excl Instructor (£)": "",
                "Monthly Total excl Instructor ex VAT (£)": round(instr_month_after_benefit, 4),
            })
            seg_rows.append({
                "Item": "Grand Total (ex VAT)",
                "Output %": "",
                "Capacity (units/week)": "",
                "Units/week": "",
                "Unit Cost excl Instructor (£)": "",
                "Monthly Total excl Instructor ex VAT (£)": round(monthly_excl_inst_sum + instr_month_after_benefit, 4),
            })

            main_df = pd.DataFrame(main_rows)
            seg_df = pd.DataFrame(seg_rows)

            # Display formatting
            disp = main_df.copy()
            for c in ["Unit Cost (£)", "Unit Price ex VAT (£)", "Unit Price inc VAT (£)",
                      "Monthly Total ex VAT (£)", "Monthly Total inc VAT (£)"]:
                disp[c] = disp[c].apply(lambda v: "" if v is None else fmt_currency(v))

            st.session_state["prod_df"] = disp
            st.session_state["prod_df_raw"] = main_df
            st.session_state["seg_df"] = seg_df
            st.session_state["prod_ctx"] = {
                "employment_support": employment_support,
                "benefits_flag": benefits_choice,
                "benefits_text": benefits_text,
                "effective_allocation_pct": effective_allocation_pct,
                "customer_covers_supervisors": customer_covers_supervisors,
                "selected_titles": selected_titles,
            }

    # ===== Results + Downloads =====
    if "prod_df" in st.session_state and isinstance(st.session_state["prod_df"], pd.DataFrame):
        df = st.session_state["prod_df"]
        st.markdown(render_table_html(df), unsafe_allow_html=True)

        seg_df = st.session_state.get("seg_df")
        if seg_df is not None and not seg_df.empty:
            sdisp = seg_df.copy()
            for c in ["Unit Cost excl Instructor (£)", "Monthly Total excl Instructor ex VAT (£)"]:
                sdisp[c] = sdisp[c].apply(lambda v: "" if v in ("", None) else fmt_currency(v))
            st.markdown("### Segregated Costs")
            st.markdown(render_table_html(sdisp), unsafe_allow_html=True)

        header_block = build_header_block(
            uk_date=_uk_date(date.today()),
            customer_name=customer_name, prison_name=prison_choice, region=region
        )

        # CSV: row per item with common metadata
        raw_items = st.session_state["prod_df_raw"]
        rows = []
        ctx = st.session_state.get("prod_ctx", {})
        for _, r in raw_items.iterrows():
            rows.append({
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
                "Customer Provides Instructors": "Yes" if ctx.get("customer_covers_supervisors") else "No",
                "Employment Support": ctx.get("employment_support", employment_support),
                "Effective Instructor Allocation (%)": ctx.get("effective_allocation_pct", 0.0),
                "Additional Benefits": ctx.get("benefits_flag", "No"),
                "Benefits Description": ctx.get("benefits_text", ""),
                "Item": r["Item"],
                "Output %": r["Output %"],
                "Capacity (units/week)": r["Capacity (units/week)"],
                "Units/week": r["Units/week"],
                "Unit Cost (£)": r["Unit Cost (£)"],
                "Unit Price ex VAT (£)": r["Unit Price ex VAT (£)"],
                "Unit Price inc VAT (£)": r["Unit Price inc VAT (£)"],
                "Monthly Total ex VAT (£)": r["Monthly Total ex VAT (£)"],
                "Monthly Total inc VAT (£)": r["Monthly Total inc VAT (£)"],
            })

        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "Download CSV (Production)",
                data=export_csv_bytes_rows(rows),
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