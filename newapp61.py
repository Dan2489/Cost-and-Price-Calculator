# newapp61.py
import pandas as pd
import streamlit as st
from io import BytesIO
from datetime import date

from config61 import CFG
from utils61 import inject_govuk_css, draw_sidebar, currency
from host61 import generate_host_quote
from production61 import labour_minutes_budget, calculate_production_contractual, calculate_adhoc
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY   # <-- imported here

# -----------------------------------------------------------------------------
# Page config
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Cost and Price Calculator", page_icon="💷", layout="centered")
inject_govuk_css()
st.markdown("## Cost and Price Calculator")

# -----------------------------------------------------------------------------
# Sidebar
# -----------------------------------------------------------------------------
sidebar_ctx = draw_sidebar()

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def export_csv_bytes(df: pd.DataFrame) -> BytesIO:
    b = BytesIO()
    df.to_csv(b, index=False)
    b.seek(0)
    return b

# -----------------------------------------------------------------------------
# Main Form
# -----------------------------------------------------------------------------
with st.form("main_form"):
    prison_choice = st.selectbox("Prison Name", ["Select"] + sorted(PRISON_TO_REGION.keys()), index=0)
    region = PRISON_TO_REGION.get(prison_choice, "National") if prison_choice != "Select" else "Select"

    customer_name = st.text_input("Customer Name")
    workshop_mode = st.selectbox("Contract type?", ["Select", "Host", "Production"])

    workshop_hours = st.number_input("How many hours is the workshop open per week?", min_value=0.0, step=0.5)
    num_prisoners = st.number_input("How many prisoners employed per week?", min_value=0, step=1)
    prisoner_salary = st.number_input("Average prisoner salary per week (£)", min_value=0.0, step=1.0)

    num_supervisors = st.number_input("How many instructors?", min_value=0, step=1)
    customer_covers_supervisors = st.checkbox("Customer provides instructor(s)?")

    supervisor_salaries = []
    if not customer_covers_supervisors and region != "Select" and num_supervisors > 0:
        for i in range(int(num_supervisors)):
            options = [t["title"] for t in SUPERVISOR_PAY[region]]
            sel = st.selectbox(f"Instructor {i+1} title", options, key=f"inst_title_{i}")
            pay = next(t["avg_total"] for t in SUPERVISOR_PAY[region] if t["title"] == sel)
            st.caption(f"Avg Total for {region}: **£{pay:,.0f}** per year")
            supervisor_salaries.append(float(pay))

    contracts = st.number_input("How many contracts do they oversee in this workshop?", min_value=1, step=1)
    recommended_pct = round((workshop_hours / CFG.FULL_UTILISATION_WEEK) * (1 / contracts) * 100, 1) if contracts else 100

    customer_type = st.selectbox("I want to quote for", ["Select", "Commercial", "Another Government Department"])
    support = st.selectbox(
        "Customer employment support?",
        ["None", "Employment on release/RoTL", "Post release", "Both"],
    )
    if support == "None":
        dev_rate = 0.20
    elif support in ("Employment on release/RoTL", "Post release"):
        dev_rate = 0.10
    else:
        dev_rate = 0.00

    submitted = st.form_submit_button("Continue")

# -----------------------------------------------------------------------------
# Host Mode
# -----------------------------------------------------------------------------
if submitted and workshop_mode == "Host":
    host_df, ctx = generate_host_quote(
        num_prisoners=int(num_prisoners),
        prisoner_salary=float(prisoner_salary),
        num_supervisors=int(num_supervisors),
        customer_covers_supervisors=bool(customer_covers_supervisors),
        supervisor_salaries=supervisor_salaries,
        effective_pct=float(sidebar_ctx["instructor_allocation"]),
        region=region,
        customer_type=customer_type,
        dev_rate=dev_rate,
        lock_overheads=sidebar_ctx["lock_overheads"],
    )

    st.markdown("### Host Costs")
    st.table(host_df)
    st.download_button("Download CSV (Host)", data=export_csv_bytes(host_df), file_name="host_quote.csv", mime="text/csv")

# -----------------------------------------------------------------------------
# Production Mode
# -----------------------------------------------------------------------------
if submitted and workshop_mode == "Production":
    st.markdown("### Production settings")

    planned_output_pct = sidebar_ctx["prisoner_output"]

    prod_type = st.radio(
        "Do you want ad-hoc costs with a deadline, or contractual work?",
        ["Contractual work", "Ad-hoc costs (multiple lines) with deadlines"],
        index=0,
    )

    if prod_type == "Contractual work":
        pricing_mode_label = st.radio(
            "Price based on:",
            ["Maximum units from capacity", "Target units per week"],
            index=0,
        )
        pricing_mode = "as-is" if pricing_mode_label.startswith("Maximum") else "target"

        budget_minutes_raw = labour_minutes_budget(int(num_prisoners), float(workshop_hours))
        budget_minutes_planned = budget_minutes_raw * (planned_output_pct / 100.0)
        st.markdown(f"**Planned available Labour minutes @ {planned_output_pct}%:** {budget_minutes_planned:,.0f}")

        num_items = st.number_input("Number of items produced?", min_value=1, value=1, step=1)
        items, targets = [], []
        for i in range(int(num_items)):
            with st.expander(f"Item {i+1} details", expanded=(i == 0)):
                name = st.text_input(f"Item {i+1} Name", key=f"name_{i}")
                disp = name.strip() or f"Item {i+1}"
                required = st.number_input(f"Prisoners required to make 1 item ({disp})", min_value=1, value=1, step=1, key=f"req_{i}")
                minutes_per = st.number_input(f"How many minutes to make 1 item ({disp})", min_value=1.0, value=10.0, step=1.0, key=f"mins_{i}")
                assigned = st.number_input(
                    f"How many prisoners work solely on this item ({disp})",
                    min_value=0, max_value=int(num_prisoners), step=1, key=f"assigned_{i}"
                )

                cap_100 = (assigned * workshop_hours * 60.0) / (minutes_per * required) if assigned and minutes_per else 0
                cap_planned = cap_100 * (planned_output_pct / 100.0)
                st.caption(f"{disp} capacity @ 100%: {cap_100:.0f} units/week · @ {planned_output_pct}%: {cap_planned:.0f}")

                if pricing_mode == "target":
                    tgt_default = int(round(cap_planned)) if cap_planned > 0 else 0
                    tgt = st.number_input(f"Target units per week ({disp})", min_value=0, value=tgt_default, step=1, key=f"target_{i}")
                    targets.append(int(tgt))

                items.append({"name": name, "required": int(required), "minutes": float(minutes_per), "assigned": int(assigned)})

        results = calculate_production_contractual(
            items, planned_output_pct,
            workshop_hours=float(workshop_hours),
            prisoner_salary=float(prisoner_salary),
            supervisor_salaries=supervisor_salaries,
            effective_pct=float(sidebar_ctx["instructor_allocation"]),
            customer_covers_supervisors=bool(customer_covers_supervisors),
            region=region,
            customer_type=customer_type,
            dev_rate=dev_rate,
            pricing_mode=pricing_mode,
            targets=targets if pricing_mode == "target" else None,
            lock_overheads=sidebar_ctx["lock_overheads"],
        )

        st.markdown("### Production Results")
        st.dataframe(pd.DataFrame(results))

    else:  # Ad-hoc
        st.write("Ad-hoc logic would go here (calculate_adhoc).")