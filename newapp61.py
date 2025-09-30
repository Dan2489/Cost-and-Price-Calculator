# newapp61.py
import streamlit as st
from datetime import date
from config61 import CFG
import tariff61
import production61

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _currency(v) -> str:
    try:
        return f"£{float(v):,.2f}"
    except Exception:
        return ""


# -----------------------------------------------------------------------------
# Main App
# -----------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="Cost and Price Calculator", layout="centered")
    st.markdown("## Cost and Price Calculator")

    # --- Sidebar controls ---
    st.sidebar.header("Controls")

    lock_overheads = st.checkbox("Lock overheads to highest instructor salary", key="lock_overheads")
    instructor_pct = st.slider("Instructor allocation (%)", 0, 100, 100)
    prisoner_output = st.slider(
        "Prisoner labour output (%)", 0, 100, CFG["GLOBAL_OUTPUT_DEFAULT"]
    )

    # --- Main form ---
    with st.form("main_form"):
        prison_name = st.selectbox("Prison Name", list(tariff61.PRISON_TO_REGION.keys()))
        customer_name = st.text_input("Customer Name")
        contract_type = st.selectbox("Contract Type", ["Host", "Production"])

        workshop_hours = st.number_input("How many hours is the workshop open per week?", min_value=0.0, format="%.2f")
        num_prisoners = st.number_input("How many prisoners employed per week?", min_value=0, step=1)
        prisoner_salary = st.number_input("Average prisoner salary per week (£)", min_value=0.0, format="%.2f")

        num_instructors = st.number_input("How many instructors?", min_value=0, step=1)

        # Dynamically show instructor dropdowns
        instructor_salaries = []
        region = tariff61.PRISON_TO_REGION[prison_name]
        region_band = tariff61.SUPERVISOR_PAY[region]

        if num_instructors > 0:
            for i in range(int(num_instructors)):
                title = st.selectbox(
                    f"Instructor {i+1} Title",
                    [r["title"] for r in region_band],
                    key=f"inst_{i}"
                )
                selected = next(r for r in region_band if r["title"] == title)
                st.caption(f"{region} — £{selected['avg_total']:,}")
                instructor_salaries.append(selected["avg_total"])

        contracts = st.number_input("How many contracts do they oversee in this workshop?", min_value=1, value=1)

        support = st.selectbox(
            "What employment support does the customer offer?",
            ["None", "Employment on release/RoTL", "Post release", "Both"]
        )

        submitted = st.form_submit_button("Generate Costs")

    if not submitted:
        return

    # --- Development charge logic ---
    if support == "None":
        dev_rate = 0.20
    elif support in ("Employment on release/RoTL", "Post release"):
        dev_rate = 0.10
    else:  # Both
        dev_rate = 0.00

    # --- HOST ---
    if contract_type == "Host":
        rows = []
        prisoner_wages = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)
        rows.append(("Prisoner wages", prisoner_wages))

        inst_monthly = 0.0
        if num_instructors > 0:
            inst_monthly = sum((s / 12.0) * (instructor_pct / 100.0) for s in instructor_salaries)
        rows.append(("Instructors", inst_monthly))

        # Overheads (61% method)
        base = inst_monthly
        if num_instructors == 0:  # shadow cost if customer provides instructors
            shadow = production61.BAND3_COSTS.get(region, 42247.81)
            base = (shadow / 12.0) * (instructor_pct / 100.0)

        if lock_overheads and instructor_salaries:
            base = (max(instructor_salaries) / 12.0) * (instructor_pct / 100.0)

        overheads = base * CFG["overheads_rate"]
        rows.append(("Overheads (61%)", overheads))

        # Development charge
        dev_charge = overheads * dev_rate
        if dev_rate < 0.20:
            rows.append(("Development charge (20%)", overheads * 0.20))
            rows.append(("Reduction", -(overheads * 0.20 - dev_charge)))
            rows.append(("Revised development charge", dev_charge))
        else:
            rows.append(("Development charge", dev_charge))

        subtotal = sum(x[1] for x in rows)
        vat_amount = subtotal * (CFG["vat_rate"] / 100.0)
        grand_total = subtotal + vat_amount

        rows.append(("Subtotal", subtotal))
        rows.append((f"VAT ({CFG['vat_rate']}%)", vat_amount))
        rows.append(("Grand Total (£/month)", grand_total))

        st.markdown("### Host Quote")
        st.table(rows)

    # --- PRODUCTION ---
    else:
        st.markdown("### Production settings")

        prod_type = st.radio("Contract type", ["Contractual work", "Ad-hoc"])

        if prod_type == "Contractual work":
            pricing_mode_label = st.radio("Price based on:", ["Maximum units from capacity", "Target units per week"])
            pricing_mode = "as-is" if pricing_mode_label.startswith("Maximum") else "target"

            num_items = st.number_input("Number of items produced?", min_value=1, value=1, step=1)
            items, targets = [], []
            for i in range(int(num_items)):
                with st.expander(f"Item {i+1} details", expanded=(i == 0)):
                    name = st.text_input(f"Item {i+1} Name", key=f"name_{i}")
                    required = st.number_input(f"Prisoners required to make 1 item ({name or i+1})", min_value=1, value=1, step=1, key=f"req_{i}")
                    minutes_per = st.number_input(f"Minutes to make 1 item ({name or i+1})", min_value=1.0, value=10.0, format="%.2f", key=f"mins_{i}")
                    assigned = st.number_input(f"How many prisoners work solely on this item ({name or i+1})", min_value=0, max_value=num_prisoners, value=0, step=1, key=f"assigned_{i}")

                    if pricing_mode == "target":
                        tgt = st.number_input(f"Target units per week ({name or i+1})", min_value=0, value=0, step=1, key=f"target_{i}")
                        targets.append(tgt)

                    items.append({
                        "name": name,
                        "required": int(required),
                        "minutes": float(minutes_per),
                        "assigned": int(assigned),
                    })

            results = production61.calculate_production_contractual(
                items, prisoner_output,
                workshop_hours=workshop_hours,
                prisoner_salary=prisoner_salary,
                supervisor_salaries=instructor_salaries,
                effective_pct=instructor_pct,
                customer_covers_supervisors=(num_instructors == 0),
                region=region,
                customer_type="Commercial",
                apply_vat=True,
                vat_rate=CFG["vat_rate"],
                num_prisoners=num_prisoners,
                num_supervisors=num_instructors,
                dev_rate=dev_rate,
                pricing_mode=pricing_mode,
                targets=targets if pricing_mode == "target" else None,
                lock_overheads=lock_overheads,
            )

            st.markdown("### Production Quote")
            st.table(results)


if __name__ == "__main__":
    main()