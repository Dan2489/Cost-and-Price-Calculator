import streamlit as st
import pandas as pd

from config61 import CFG, hours_scale
from utils61 import inject_govuk_css, PRISON_TO_REGION, SUPERVISOR_PAY, draw_sidebar
from host61 import generate_host_quote
from production61 import labour_minutes_budget, calculate_production_contractual

# ---------------- Page & CSS ----------------
st.set_page_config(page_title="Cost and Price Calculator", page_icon="💷", layout="centered")
inject_govuk_css()
st.markdown("## Cost and Price Calculator")

# ---------------- Base inputs (main form) ----------------
prisons_sorted = ["Select"] + sorted(PRISON_TO_REGION.keys())
prison_choice = st.selectbox("Prison Name", prisons_sorted, index=0, key="prison_choice")
region = PRISON_TO_REGION.get(prison_choice, "Select") if prison_choice != "Select" else "Select"
st.session_state["region"] = region

customer_type = st.selectbox("I want to quote for", ["Select", "Commercial", "Another Government Department"], key="customer_type")
customer_name = st.text_input("Customer Name", key="customer_name")
workshop_mode = st.selectbox("Contract type?", ["Select", "Host", "Production"], key="workshop_mode")

workshop_hours = st.number_input("How many hours per week is the workshop open?", min_value=0.0, format="%.2f", key="workshop_hours")
num_prisoners = st.number_input("How many prisoners employed?", min_value=0, step=1, key="num_prisoners")

num_supervisors = st.number_input("How many instructors?", min_value=0, step=1, key="num_supervisors")
customer_covers_supervisors = st.checkbox("Customer provides instructor(s)?", key="customer_covers_supervisors")

# Dynamic instructor titles (only if MoJ pays)
supervisor_salaries = []
if not customer_covers_supervisors:
    titles_for_region = SUPERVISOR_PAY.get(region, [])
    if region == "Select" or not titles_for_region:
        st.warning("Select a prison to derive the Region before assigning instructor titles.")
    else:
        for i in range(int(num_supervisors)):
            options = [t["title"] for t in titles_for_region]
            sel = st.selectbox(f"Instructor {i+1} title", options, key=f"inst_title_{i}")
            pay = next(t["avg_total"] for t in titles_for_region if t["title"] == sel)
            st.caption(f"Avg Total for {region}: **£{pay:,.0f}** per year")
            supervisor_salaries.append(float(pay))

contracts = st.number_input("How many contracts do these instructors oversee?", min_value=1, value=1, key="contracts")
recommended_pct = round((workshop_hours / CFG.FULL_UTILISATION_WEEK) * (1 / contracts) * 100, 1) if contracts and workshop_hours >= 0 else 0
chosen_pct_default = int(round(recommended_pct))

# Sidebar: lock overheads, instructor allocation, prisoner salary (only 3 controls)
lock_overheads, effective_pct, prisoner_salary = draw_sidebar(
    recommended_pct=recommended_pct,
    chosen_pct=chosen_pct_default,
    prisoner_salary=st.session_state.get("prisoner_salary", 0.0),
)

# Development support selector (affects dev charge)
support = "None"
if customer_type == "Commercial":
    support = st.selectbox(
        "Customer employment support?",
        ["None", "Employment on release/RoTL", "Post release", "Both"],
        help="Affects development charge on overheads (base 20%, reductions up to -20%)."
    )

# Basic validation
errors = []
if prison_choice == "Select": errors.append("Select prison")
if region == "Select": errors.append("Region could not be derived from prison selection")
if customer_type == "Select": errors.append("Select customer type")
if not str(customer_name).strip(): errors.append("Enter customer name")
if workshop_mode == "Select": errors.append("Select contract type")
if workshop_mode == "Production" and workshop_hours <= 0: errors.append("Hours per week must be > 0 (Production)")
if num_prisoners < 0: errors.append("Prisoners employed cannot be negative")
if not customer_covers_supervisors:
    if num_supervisors <= 0: errors.append("Enter number of instructors (>0) or tick 'Customer provides instructor(s)'")
    if len(supervisor_salaries) != int(num_supervisors): errors.append("Choose a title for each instructor")
    if any(s <= 0 for s in supervisor_salaries): errors.append("Instructor Avg Total must be > 0")

# ---------------- HOST ----------------
def run_host():
    if st.button("Generate Host Costs"):
        if errors:
            st.error("Fix errors:\n- " + "\n- ".join(errors)); return
        host_df, _ctx = generate_host_quote(
            region=region,
            num_prisoners=int(num_prisoners),
            prisoner_salary=float(prisoner_salary),
            num_supervisors=int(num_supervisors),
            customer_covers_supervisors=bool(customer_covers_supervisors),
            supervisor_salaries=supervisor_salaries,
            effective_pct=float(effective_pct),
            customer_type=customer_type,
            support=support,
            lock_overheads=lock_overheads,
            apply_vat=True,
            vat_rate=20.0,
        )

        # Render with red negatives
        def _neg_red(v):
            try:
                return "color: #d4351c;" if float(v) < 0 else ""
            except Exception:
                return ""
        st.dataframe(host_df.style.applymap(_neg_red, subset=["Amount (£)"]))

# ---------------- PRODUCTION ----------------
def run_production():
    if errors:
        st.error("Fix errors before production:\n- " + "\n- ".join(errors)); return

    st.markdown("---")
    st.subheader("Production settings")

    planned_output_pct = st.slider(
        "Planned Output (%)", min_value=0, max_value=100, value=CFG.GLOBAL_OUTPUT_DEFAULT,
        help="Scales both planned available and planned used labour minutes."
    )

    pricing_mode_label = st.radio(
        "Price based on:",
        ["Maximum units from capacity", "Target units per week"],
        index=0,
    )
    pricing_mode = "as-is" if pricing_mode_label.startswith("Maximum") else "target"

    # Planned minutes info
    budget_minutes_raw = labour_minutes_budget(int(num_prisoners), float(workshop_hours))
    budget_minutes_planned = budget_minutes_raw * (planned_output_pct / 100.0)
    st.markdown(f"**Planned available Labour minutes @ {planned_output_pct}%:** {budget_minutes_planned:,.0f}")

    # Items
    num_items = st.number_input("Number of items produced?", min_value=1, value=1, step=1, key="num_items_prod")
    items, targets = [], []
    for i in range(int(num_items)):
        with st.expander(f"Item {i+1} details", expanded=(i == 0)):
            name = st.text_input(f"Item {i+1} Name", key=f"name_{i}")
            disp = (name.strip() or f"Item {i+1}") if isinstance(name, str) else f"Item {i+1}"
            required = st.number_input(f"Prisoners required to make 1 item ({disp})", min_value=1, value=1, step=1, key=f"req_{i}")
            minutes_per = st.number_input(f"How many minutes to make 1 item ({disp})", min_value=1.0, value=10.0, format="%.2f", key=f"mins_{i}")

            total_assigned_before = sum(int(st.session_state.get(f"assigned_{j}", 0)) for j in range(i))
            remaining = max(0, int(num_prisoners) - total_assigned_before)
            assigned = st.number_input(
                f"How many prisoners work solely on this item ({disp})",
                min_value=0, max_value=remaining, value=int(st.session_state.get(f"assigned_{i}", 0)),
                step=1, key=f"assigned_{i}"
            )

            # Target units if in target mode
            if pricing_mode == "target":
                cap_100 = (assigned * workshop_hours * 60.0) / (minutes_per * required) if (assigned and minutes_per and required and workshop_hours) else 0
                tgt_default = int(round(cap_100 * (planned_output_pct / 100.0)))
                tgt = st.number_input(f"Target units per week ({disp})", min_value=0, value=tgt_default, step=1, key=f"target_{i}")
                targets.append(int(tgt))

            items.append({"name": name, "required": int(required), "minutes": float(minutes_per), "assigned": int(assigned)})

    results = calculate_production_contractual(
        items, planned_output_pct,
        workshop_hours=float(workshop_hours),
        prisoner_salary=float(prisoner_salary),
        supervisor_salaries=supervisor_salaries,
        effective_pct=float(effective_pct),
        customer_covers_supervisors=bool(customer_covers_supervisors),
        customer_type=customer_type,
        support=support,
        apply_vat=True,
        vat_rate=20.0,
        num_prisoners=int(num_prisoners),
        region=region if region != "Select" else "National",
        lock_overheads=lock_overheads,
        pricing_mode=pricing_mode,
        targets=targets if pricing_mode == "target" else None,
    )

    # Present results
    display_cols = ["Item", "Output %", "Capacity (units/week)", "Units/week",
                    "Unit Cost (£)", "Unit Price ex VAT (£)", "Unit Price inc VAT (£)",
                    "Monthly Total (ex VAT £)", "Monthly Total (inc VAT £)"]
    prod_df = pd.DataFrame([{
        c: (None if (r.get(c) is None) else (round(float(r.get(c)), 2) if isinstance(r.get(c), (int, float)) else r.get(c)))
        for c in display_cols
    } for r in results])

    st.dataframe(prod_df)

    # Grand monthly total (ex VAT)
    try:
        grand_monthly_ex = float(prod_df["Monthly Total (ex VAT £)"].fillna(0).sum())
    except Exception:
        grand_monthly_ex = 0.0
    st.markdown(f"**Grand Monthly Total (ex VAT): £{grand_monthly_ex:,.2f}**")

# ---------------- MAIN ----------------
if workshop_mode == "Host":
    run_host()
elif workshop_mode == "Production":
    run_production()