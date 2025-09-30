from datetime import date
import pandas as pd
import streamlit as st

from config61 import CFG
from utils61 import (
    PRISON_TO_REGION, SUPERVISOR_PAY,
    draw_sidebar, validate_inputs,
    render_host_df_to_html, render_generic_df_to_html,
    export_csv_bytes, export_html
)
from host61 import generate_host_quote
from production61 import calculate_production_contractual, labour_minutes_budget

# --------------------------------------------------------------------
# Page setup
# --------------------------------------------------------------------
st.set_page_config(page_title="Cost and Price Calculator", page_icon="💷", layout="centered")

st.markdown("## Cost and Price Calculator")

# --------------------------------------------------------------------
# Base inputs
# --------------------------------------------------------------------
prisons_sorted = ["Select"] + sorted(PRISON_TO_REGION.keys())
prison_choice = st.selectbox("Prison Name", prisons_sorted, index=0, key="prison_choice")
region = PRISON_TO_REGION.get(prison_choice, "Select") if prison_choice != "Select" else "Select"
st.session_state["region"] = region

customer_type = st.selectbox("I want to quote for", ["Select", "Commercial", "Another Government Department"], key="customer_type")
customer_name = st.text_input("Customer Name", key="customer_name")
workshop_mode = st.selectbox("Contract type?", ["Select", "Host", "Production"], key="workshop_mode")

workshop_hours = st.number_input("How many hours per week is the workshop open?", min_value=0.0, format="%.2f", key="workshop_hours")
num_prisoners   = st.number_input("How many prisoners employed?", min_value=0, step=1, key="num_prisoners")
num_supervisors = st.number_input("How many instructors?", min_value=0, step=1, key="num_supervisors")
customer_covers_supervisors = st.checkbox("Customer provides instructor(s)?", key="customer_covers_supervisors")

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

# Sidebar: lock overheads, instructor allocation slider, prisoner salary slider
lock_overheads, chosen_pct, prisoner_salary = draw_sidebar(chosen_pct_default, chosen_pct_default, st.session_state.get("prisoner_salary", 0.0))
effective_pct = chosen_pct

# Development charge setting
support = "None"
if customer_type == "Commercial":
    support = st.selectbox(
        "Customer employment support?",
        ["None", "Employment on release/RoTL", "Post release", "Both"],
        help="Affects development charge (on overheads). 'Both' reduces dev charge to 0%."
    )

# --------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------
errors = validate_inputs(prison_choice, region, customer_type, customer_name,
                         workshop_mode, num_supervisors, supervisor_salaries,
                         customer_covers_supervisors, num_prisoners)

# --------------------------------------------------------------------
# HOST
# --------------------------------------------------------------------
def run_host():
    if st.button("Generate Host Costs"):
        if errors:
            st.error("Fix errors:\n- " + "\n- ".join(errors)); return

        host_df, _ctx = generate_host_quote(
            workshop_hours=float(workshop_hours),
            num_prisoners=int(num_prisoners),
            prisoner_salary=float(prisoner_salary),
            num_supervisors=int(num_supervisors),
            customer_covers_supervisors=bool(customer_covers_supervisors),
            supervisor_salaries=supervisor_salaries,
            effective_pct=float(effective_pct),
            customer_type=customer_type,
            support=support,
            apply_vat=True,
            vat_rate=20.0,
        )
        st.markdown(render_host_df_to_html(host_df), unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.download_button("Download CSV (Host)", data=export_csv_bytes(host_df), file_name="host_quote.csv", mime="text/csv")
        with c2:
            st.download_button(
                "Download PDF-ready HTML (Host)",
                data=export_html(host_df, None, title="Host Quote"),
                file_name="host_quote.html", mime="text/html"
            )

# --------------------------------------------------------------------
# PRODUCTION
# --------------------------------------------------------------------
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

    budget_minutes_raw = labour_minutes_budget(int(num_prisoners), float(workshop_hours))
    budget_minutes_planned = budget_minutes_raw * (planned_output_pct / 100.0)
    st.markdown(f"**Planned available Labour minutes @ {planned_output_pct}%:** {budget_minutes_planned:,.0f}")

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

            if pricing_mode == "target":
                tgt_default = int(round((assigned * workshop_hours * 60.0 / (minutes_per * required)) * (planned_output_pct / 100.0)))
                tgt = st.number_input(f"Target units per week ({disp})", min_value=0, value=tgt_default, step=1, key=f"target_{i}")
                targets.append(int(tgt))

            items.append({"name": name, "required": int(required), "minutes": float(minutes_per), "assigned": int(assigned)})

    results, ctx = calculate_production_contractual(
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
        num_supervisors=int(num_supervisors),
        lock_overheads=lock_overheads,
        dev_rate=0.0,
        pricing_mode=pricing_mode,
        targets=targets if pricing_mode == "target" else None,
    )

    prod_df = pd.DataFrame([{
        k: (None if r.get(k) is None else (round(float(r.get(k)), 2) if isinstance(r.get(k), (int, float)) else r.get(k)))
        for k in ["Item", "Output %", "Capacity (units/week)", "Units/week",
                  "Unit Cost (£)", "Unit Price ex VAT (£)", "Unit Price inc VAT (£)", "Monthly Total (£)", "Feasible", "Note"]
    } for r in results])

    st.markdown(render_generic_df_to_html(prod_df), unsafe_allow_html=True)
    st.markdown(f"**Grand Monthly Total: £{ctx['grand_monthly_total']:,.2f}**")

    d1, d2 = st.columns(2)
    with d1:
        st.download_button("Download CSV (Production)", data=export_csv_bytes(prod_df), file_name="production_quote.csv", mime="text/csv")
    with d2:
        st.download_button(
            "Download PDF-ready HTML (Production)",
            data=export_html(None, prod_df, title="Production Quote"),
            file_name="production_quote.html", mime="text/html"
        )

# --------------------------------------------------------------------
# MAIN
# --------------------------------------------------------------------
if workshop_mode == "Host":
    run_host()
elif workshop_mode == "Production":
    run_production()