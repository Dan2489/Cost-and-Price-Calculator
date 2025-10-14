# newapp61.py — full app, Host + Production working, dev reduction shown, benefits handled

import streamlit as st
import pandas as pd
from datetime import date

# -------------------------------
# Minimal config & lookups (inline)
# -------------------------------
class CFG:
    GLOBAL_OUTPUT_DEFAULT = 100  # only used for prisoner-output sidebar slider

PRISON_TO_REGION = {
    "Altcourse": "National",
    "Hindley": "National",
    "Ranby": "National",
    "Durham": "National",
    "Elmley": "National",
    "Wealstun": "National",
    "Highpoint": "National",
    "Lowdham Grange": "National",
    "Winchester": "National",
}

SUPERVISOR_PAY = {
    "National": [
        {"title": "Production Instructor: Band 3", "avg_total": 42248},
        {"title": "Production Instructor: Band 4", "avg_total": 47350},
        {"title": "Prison Officer Specialist - Instructor: Band 4", "avg_total": 48969},
    ]
}

# -------------------------------
# Inline utility helpers (no external imports)
# -------------------------------
def inject_govuk_css():
    st.markdown(
        """
        <style>
          :root { --govuk-green:#00703c; --govuk-yellow:#ffdd00; --govuk-red:#d4351c; }
          .stButton > button { background: var(--govuk-green)!important; color:#fff!important; border-radius:0!important; }
          .neg { color: var(--govuk-red); font-weight:600; }
          table.custom { width:100%; border-collapse:collapse; margin:12px 0; }
          table.custom th, table.custom td { border:1px solid #b1b4b6; padding:6px 10px; text-align:left; }
          table.custom th { background:#f3f2f1; font-weight:700; }
        </style>
        """,
        unsafe_allow_html=True,
    )

def sidebar_controls(default_output: int):
    with st.sidebar:
        st.header("Controls")
        prisoner_output = st.slider("Prisoner labour output (%)", 0, 100, default_output, step=1)
    # keep signature: (lock_overheads, instructor_pct, prisoner_output)
    return False, 0, prisoner_output

def fmt_currency(val) -> str:
    try:
        return f"£{float(val):,.2f}"
    except Exception:
        return str(val)

def render_table_html(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "<p><em>No data</em></p>"
    return df.to_html(index=False, classes="custom", escape=False)

def export_csv_bytes_rows(rows: list[dict]) -> bytes:
    import io
    df = pd.DataFrame(rows)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

def _uk_date(d: date) -> str:
    return d.strftime("%d/%m/%Y")

def build_header_block(*, uk_date: str, customer_name: str, prison_name: str, region: str) -> str:
    return (
        f"<h2>Quotation</h2>"
        f"<p><strong>Date:</strong> {uk_date}</p>"
        f"<p><strong>Prison:</strong> {prison_name} ({region})</p>"
        f"<p><strong>Customer:</strong> {customer_name}</p>"
        "<p>We are pleased to set out below the terms of our Quotation for the Goods and/or Services you are "
        "currently seeking. We confirm that this Quotation and any subsequent contract entered into as a result "
        "is, and will be, subject exclusively to our Standard Conditions of Sale of Goods and/or Services a copy "
        "of which is available on request. Please note that all prices are exclusive of VAT and carriage costs at "
        "time of order of which the customer shall be additionally liable to pay.</p>"
    )

def export_html(df_host: pd.DataFrame, df_prod: pd.DataFrame, *, title: str, header_block: str = "", segregated_df: pd.DataFrame | None = None) -> bytes:
    html = ["<html><head><meta charset='utf-8' /><title>", title, "</title></head><body>"]
    if header_block:
        html.append(header_block)
        html.append("<hr>")
    if df_host is not None:
        html.append("<h3>Summary</h3>")
        html.append(render_table_html(df_host))
    if df_prod is not None:
        html.append("<h3>Summary</h3>")
        html.append(render_table_html(df_prod))
    if segregated_df is not None and not segregated_df.empty:
        html.append("<h3>Segregated Costs</h3>")
        html.append(render_table_html(segregated_df))
    html.append("</body></html>")
    return "".join(html).encode("utf-8")

# -------------------------------
# Dev-rate logic
# -------------------------------
STANDARD_DEV_RATE = 0.20  # "before" baseline
def applicable_dev_rate(s: str) -> float:
    if s == "None":
        return 0.20
    if s in ("Employment on release/RoTL", "Post release"):
        return 0.10
    return 0.00  # Both

# -------------------------------
# HOST summary (includes dev reduction + revised)
# -------------------------------
def generate_host_summary(
    *, num_prisoners: int, prisoner_salary: float,
    supervisor_salaries: list[float],
    employment_support: str,
    benefits_discount_on_instructor: float
) -> pd.DataFrame:

    prisoner_month = num_prisoners * prisoner_salary * 52.0 / 12.0

    instr_month_base = (sum(supervisor_salaries) / 12.0) if supervisor_salaries else 0.0
    benefits_reduction = instr_month_base * benefits_discount_on_instructor if benefits_discount_on_instructor > 0 else 0.0
    instr_month_after_benefit = instr_month_base - benefits_reduction

    overheads_month = instr_month_base * 0.61  # overheads based on base instructor

    dev_before = overheads_month * STANDARD_DEV_RATE
    dev_rate = applicable_dev_rate(employment_support)
    dev_revised = overheads_month * dev_rate
    dev_reduction = max(0.0, dev_before - dev_revised)

    grand_total_ex_vat = prisoner_month + instr_month_after_benefit + overheads_month + dev_revised - dev_reduction
    vat = grand_total_ex_vat * 0.20
    grand_inc_vat = grand_total_ex_vat + vat

    rows = [
        {"Item": "Prisoner Wages", "Amount (£)": fmt_currency(prisoner_month)},
        {"Item": "Instructor Salary", "Amount (£)": fmt_currency(instr_month_after_benefit)},
        {"Item": "Overheads", "Amount (£)": fmt_currency(overheads_month)},
        {"Item": "Development charge (before)", "Amount (£)": fmt_currency(dev_before)},
    ]
    if dev_reduction > 0:
        rows.append({"Item": "<span class='neg'>Development reduction</span>", "Amount (£)": f"<span class='neg'>- {fmt_currency(dev_reduction)}</span>"})
    rows.append({"Item": "Revised development charge", "Amount (£)": fmt_currency(dev_revised)})
    if benefits_reduction > 0:
        rows.append({"Item": "<span class='neg'>Additional benefits reduction</span>", "Amount (£)": f"<span class='neg'>- {fmt_currency(benefits_reduction)}</span>"})
    rows.extend([
        {"Item": "Grand Total (ex VAT)", "Amount (£)": fmt_currency(grand_total_ex_vat)},
        {"Item": "VAT (20%)", "Amount (£)": fmt_currency(vat)},
        {"Item": "Grand Total (inc VAT)", "Amount (£)": fmt_currency(grand_inc_vat)},
    ])
    return pd.DataFrame(rows)

# -------------------------------
# PRODUCTION calculator (inline)
# -------------------------------
def calc_production_tables(
    *, items: list[dict],
    workshop_hours: float,
    prisoner_output_pct: int,
    prisoner_salary_week: float,
    supervisor_salaries: list[float],
    employment_support: str,
    benefits_discount_on_instructor: float,
    pricing_mode: str,   # "as-is" or "target"
    targets: list[int] | None
):
    """
    Returns (main_df, seg_df)
    main_df columns:
      Item, Output %, Capacity (units/week), Units/week, Unit Cost (£),
      Unit Price ex VAT (£), Unit Price inc VAT (£),
      Monthly Total ex VAT (£), Monthly Total inc VAT (£)
    seg_df columns:
      Item, Output %, Capacity (units/week), Units/week, Unit Cost excl Instructor (£),
      Monthly Total excl Instructor ex VAT (£)
      + Instructor Salary (monthly), Grand Total (ex VAT)
    """

    out_scale = float(prisoner_output_pct) / 100.0
    total_minutes_budget = sum(int(it.get("assigned", 0)) * workshop_hours * 60.0 for it in items)
    # instructor weekly (base & after benefits)
    instr_week_base = (sum(supervisor_salaries) / 52.0) if supervisor_salaries else 0.0
    instr_week_after_benefit = instr_week_base * (1.0 - benefits_discount_on_instructor)

    # overheads & dev (weekly) — based on base instructor
    overheads_week = instr_week_base * 0.61
    dev_rate = applicable_dev_rate(employment_support)
    dev_week = overheads_week * dev_rate

    main_rows = []
    seg_rows = []
    monthly_excl_inst_sum = 0.0

    for idx, it in enumerate(items):
        name = (it.get("name") or "").strip() or f"Item {idx+1}"
        minutes_per = float(it.get("minutes", 0.0))
        pris_required = max(1, int(it.get("required", 1)))
        pris_assigned = int(it.get("assigned", 0))

        # capacity (100% and planned)
        if pris_assigned > 0 and minutes_per > 0 and pris_required > 0 and workshop_hours > 0:
            cap_100 = (pris_assigned * workshop_hours * 60.0) / (minutes_per * pris_required)
        else:
            cap_100 = 0.0
        cap_planned = cap_100 * out_scale

        if pricing_mode == "target" and targets and idx < len(targets or []):
            units_for_pricing = float(max(0, int(targets[idx])))
        else:
            units_for_pricing = float(cap_planned)

        # share for overhead/instructor/dev
        share = ((pris_assigned * workshop_hours * 60.0) / total_minutes_budget) if total_minutes_budget > 0 else 0.0

        # weekly components
        prisoner_week = pris_assigned * prisoner_salary_week
        overheads_item_week = overheads_week * share
        dev_item_week = dev_week * share
        instructor_item_week = instr_week_after_benefit * share

        # excl & incl instructor weekly
        weekly_excl_inst = prisoner_week + overheads_item_week + dev_item_week
        weekly_incl_inst = weekly_excl_inst + instructor_item_week

        # prices
        if units_for_pricing > 0:
            unit_cost = weekly_incl_inst / units_for_pricing
            unit_price_ex = unit_cost  # cost & price aligned here
            unit_price_inc = unit_price_ex * 1.20
            monthly_total_ex = unit_price_ex * units_for_pricing * 52.0 / 12.0
            monthly_total_inc = monthly_total_ex * 1.20
        else:
            unit_cost = unit_price_ex = unit_price_inc = None
            monthly_total_ex = monthly_total_inc = 0.0

        main_rows.append({
            "Item": name,
            "Output %": int(prisoner_output_pct),
            "Capacity (units/week)": int(round(cap_planned)) if cap_planned > 0 else 0,
            "Units/week": int(round(units_for_pricing)) if units_for_pricing > 0 else 0,
            "Unit Cost (£)": None if unit_cost is None else round(unit_cost, 4),
            "Unit Price ex VAT (£)": None if unit_price_ex is None else round(unit_price_ex, 4),
            "Unit Price inc VAT (£)": None if unit_price_inc is None else round(unit_price_inc, 4),
            "Monthly Total ex VAT (£)": round(monthly_total_ex, 4),
            "Monthly Total inc VAT (£)": round(monthly_total_inc, 4),
        })

        # segregated row (excl instructor)
        unit_cost_excl = (weekly_excl_inst / units_for_pricing) if units_for_pricing > 0 else None
        monthly_excl = (unit_cost_excl * units_for_pricing * 52.0 / 12.0) if unit_cost_excl else 0.0
        monthly_excl_inst_sum += monthly_excl

        seg_rows.append({
            "Item": name,
            "Output %": int(prisoner_output_pct),
            "Capacity (units/week)": int(round(cap_planned)) if cap_planned > 0 else 0,
            "Units/week": int(round(units_for_pricing)) if units_for_pricing > 0 else 0,
            "Unit Cost excl Instructor (£)": None if unit_cost_excl is None else round(unit_cost_excl, 4),
            "Monthly Total excl Instructor ex VAT (£)": round(monthly_excl, 4),
        })

    # instructor monthly line + grand total for segregated table
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
    return main_df, seg_df

# -------------------------------
# App UI
# -------------------------------
st.set_page_config(page_title="Cost and Price Calculator", page_icon="💷", layout="centered")
inject_govuk_css()
st.title("Cost and Price Calculator")

# Sidebar (only output slider retained)
_, _, prisoner_output = sidebar_controls(CFG.GLOBAL_OUTPUT_DEFAULT)

# Base inputs
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
supervisor_salaries = []
if num_supervisors > 0 and region != "Select":
    titles_for_region = SUPERVISOR_PAY.get(region, [])
    options = [t["title"] for t in titles_for_region]
    for i in range(int(num_supervisors)):
        sel = st.selectbox(f"Instructor {i+1} Title", options, key=f"inst_title_{i}")
        pay = next(t["avg_total"] for t in titles_for_region if t["title"] == sel)
        st.caption(f"{region} — £{pay:,.0f}")
        supervisor_salaries.append(float(pay))

contracts = st.number_input("How many contracts do they oversee in this workshop?", min_value=1, value=1)

employment_support = st.selectbox(
    "What employment support does the customer offer?",
    ["None", "Employment on release/RoTL", "Post release", "Both"],
)

# Additional benefits (optional 10% off instructor salary)
has_benefits = st.radio(
    "Any additional prison benefits that you feel warrant a further reduction?",
    ["No", "Yes"], index=0, horizontal=True
)
benefits_text = ""
if has_benefits == "Yes":
    benefits_text = st.text_area("Describe the benefits")
instructor_discount = 0.10 if has_benefits == "Yes" else 0.0

# -------------------------------
# HOST
# -------------------------------
if contract_type == "Host":
    if st.button("Generate Host Costs"):
        errors = []
        if prison_choice == "Select": errors.append("Select prison")
        if region == "Select": errors.append("Region could not be derived from prison selection")
        if not str(customer_name).strip(): errors.append("Enter customer name")
        if workshop_hours <= 0: errors.append("Workshop hours must be greater than zero")
        if len(supervisor_salaries) != int(num_supervisors): errors.append("Choose a title for each instructor")

        if errors:
            st.error("Fix errors:\n- " + "\n- ".join(errors))
        else:
            host_df = generate_host_summary(
                num_prisoners=int(num_prisoners),
                prisoner_salary=float(prisoner_salary),
                supervisor_salaries=supervisor_salaries,
                employment_support=employment_support,
                benefits_discount_on_instructor=instructor_discount,
            )
            st.session_state["host_df"] = host_df
            st.session_state["host_ctx"] = {
                "benefits_text": benefits_text,
                "benefits_flag": has_benefits,
                "employment_support": employment_support,
            }

    if "host_df" in st.session_state:
        df = st.session_state["host_df"].copy()
        st.markdown(render_table_html(df), unsafe_allow_html=True)

        header_block = build_header_block(
            uk_date=_uk_date(date.today()),
            customer_name=customer_name, prison_name=prison_choice, region=region
        )

        # pull numeric values for CSV
        def _grab(df_in: pd.DataFrame, needle: str) -> float:
            try:
                m = df_in["Item"].astype(str).str.contains(needle, case=False, na=False, regex=False)
                if m.any():
                    raw = str(df_in.loc[m, "Amount (£)"].iloc[-1])
                    raw = raw.replace("£", "").replace(",", "").replace("-", "").strip()
                    raw = "".join(ch for ch in raw if (ch.isdigit() or ch in "."))
                    return float(raw)
            except Exception:
                pass
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
            "Employment Support": ctx.get("employment_support", employment_support),
            "Additional Benefits": ctx.get("benefits_flag", "No"),
            "Benefits Description": ctx.get("benefits_text", ""),
            "Host: Prisoner wages (£/month)": prisoner_month,
            "Host: Instructor Salary (£/month)": instructor_month,
            "Host: Overheads (£/month)": overheads_month,
            "Host: Development charge (before £/month)": dev_before,
            "Host: Development Reduction (£/month)": dev_reduction,
            "Host: Development Revised (£/month)": dev_revised,
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

# -------------------------------
# PRODUCTION
# -------------------------------
if contract_type == "Production":
    st.markdown("---")
    st.subheader("Production settings")

    # minutes capacity context
    _, _, output_pct = False, 0, prisoner_output  # already set
    output_scale = float(output_pct) / 100.0

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
                    index=0, key=f"mins_unit_{i}", horizontal=True
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
                    min_value=0, max_value=remaining,
                    value=int(st.session_state.get(f"assigned_{i}", 0)),
                    step=1, key=f"assigned_{i}"
                )

                # preview capacity
                if assigned > 0 and minutes_per > 0 and required > 0 and workshop_hours > 0:
                    cap_100 = (assigned * workshop_hours * 60.0) / (minutes_per * required)
                else:
                    cap_100 = 0.0
                cap_planned = cap_100 * output_scale
                st.caption(f"{disp} capacity @ 100%: **{cap_100:.0f} units/week** · @ {output_pct}%: **{cap_planned:.0f}**")

                if pricing_mode_key == "target":
                    tgt_default = int(round(cap_planned)) if cap_planned > 0 else 0
                    tgt = st.number_input(f"Target units per week ({disp})", min_value=0, value=tgt_default, step=1, key=f"target_{i}")
                    targets.append(int(tgt))

                items.append({
                    "name": name, "required": int(required),
                    "minutes": float(minutes_per), "assigned": int(assigned)
                })

        if st.button("Generate Production Costs", key="generate_contractual"):
            errs = []
            if prison_choice == "Select": errs.append("Select prison")
            if region == "Select": errs.append("Region could not be derived from prison selection")
            if not str(customer_name).strip(): errs.append("Enter customer name")
            if workshop_hours <= 0: errs.append("Workshop hours must be greater than zero")
            if len(supervisor_salaries) != int(num_supervisors): errs.append("Choose a title for each instructor")

            if errs:
                st.error("Fix errors:\n- " + "\n- ".join(errs))
            else:
                main_df, seg_df = calc_production_tables(
                    items=items,
                    workshop_hours=float(workshop_hours),
                    prisoner_output_pct=int(output_pct),
                    prisoner_salary_week=float(prisoner_salary),
                    supervisor_salaries=supervisor_salaries,
                    employment_support=employment_support,
                    benefits_discount_on_instructor=instructor_discount,
                    pricing_mode=pricing_mode_key,
                    targets=targets if pricing_mode_key == "target" else None
                )
                # format numbers in display DF
                disp = main_df.copy()
                for c in ["Unit Cost (£)", "Unit Price ex VAT (£)", "Unit Price inc VAT (£)", "Monthly Total ex VAT (£)", "Monthly Total inc VAT (£)"]:
                    disp[c] = disp[c].apply(lambda v: "" if v is None else fmt_currency(v))
                st.session_state["prod_df"] = disp
                st.session_state["prod_df_raw"] = main_df
                st.session_state["seg_df"] = seg_df
                st.session_state["prod_ctx"] = {
                    "employment_support": employment_support,
                    "benefits_flag": has_benefits,
                    "benefits_text": benefits_text,
                }

    else:
        st.info("Ad-hoc flow not included in this trimmed file.")

    # ===== Results + Segregated + Downloads =====
    if "prod_df" in st.session_state and isinstance(st.session_state["prod_df"], pd.DataFrame):
        df = st.session_state["prod_df"]
        st.markdown(render_table_html(df), unsafe_allow_html=True)

        seg_df = st.session_state.get("seg_df")
        if seg_df is not None and not seg_df.empty:
            # format money cols for display
            sdisp = seg_df.copy()
            for c in ["Unit Cost excl Instructor (£)", "Monthly Total excl Instructor ex VAT (£)"]:
                sdisp[c] = sdisp[c].apply(lambda v: "" if v is None or v == "" else fmt_currency(v))
            st.markdown("### Segregated Costs")
            st.markdown(render_table_html(sdisp), unsafe_allow_html=True)

        # Downloads (Production)
        header_block = build_header_block(
            uk_date=_uk_date(date.today()),
            customer_name=customer_name, prison_name=prison_choice, region=region
        )

        # CSV rows: export the raw main_df (numbers) row-wise, with common metadata attached to each row
        raw_items = st.session_state["prod_df_raw"]
        rows = []
        ctx = st.session_state.get("prod_ctx", {})
        for _, r in raw_items.iterrows():
            row = {
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
                "Employment Support": ctx.get("employment_support", employment_support),
                "Additional Benefits": ctx.get("benefits_flag", "No"),
                "Benefits Description": ctx.get("benefits_text", ""),
                # item metrics
                "Item": r["Item"],
                "Output %": r["Output %"],
                "Capacity (units/week)": r["Capacity (units/week)"],
                "Units/week": r["Units/week"],
                "Unit Cost (£)": r["Unit Cost (£)"],
                "Unit Price ex VAT (£)": r["Unit Price ex VAT (£)"],
                "Unit Price inc VAT (£)": r["Unit Price inc VAT (£)"],
                "Monthly Total ex VAT (£)": r["Monthly Total ex VAT (£)"],
                "Monthly Total inc VAT (£)": r["Monthly Total inc VAT (£)"],
            }
            rows.append(row)

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