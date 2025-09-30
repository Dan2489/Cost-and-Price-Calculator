from typing import List, Dict, Tuple
import pandas as pd
import streamlit as st

def generate_host_quote(
    *,
    num_prisoners: int,
    prisoner_salary: float,
    num_supervisors: int,
    customer_covers_supervisors: bool,
    supervisor_salaries: List[float],
    effective_pct: float,
    customer_type: str,
    apply_vat: bool,
    vat_rate: float,
    dev_rate: float,  # not used directly anymore, replaced by support logic
) -> Tuple[pd.DataFrame, Dict]:
    breakdown: Dict[str, float] = {}

    # Prisoner wages
    breakdown["Prisoner wages"] = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)

    # Instructor salaries (monthly, adjusted by allocation %)
    instructor_cost = 0.0
    if not customer_covers_supervisors:
        instructor_cost = sum((s / 12.0) * (float(effective_pct) / 100.0) for s in supervisor_salaries)
    breakdown["Instructors"] = instructor_cost

    # --- Development charge ---
    dev_base = instructor_cost * 0.20
    dev_reduction = 0.0
    if customer_type == "Commercial":
        support = st.session_state.get("support", "None")
        if support == "Employment on release/RoTL":
            dev_reduction = instructor_cost * 0.10
        elif support == "Post release":
            dev_reduction = instructor_cost * 0.10
        elif support == "Both":
            dev_reduction = instructor_cost * 0.20
    dev_final = max(0.0, dev_base - dev_reduction)

    breakdown["Development charge (20%)"] = dev_base
    if dev_reduction > 0:
        breakdown["Reduction applied"] = -dev_reduction
    breakdown["Revised Development charge"] = dev_final

    # Subtotal / VAT / Grand total
    subtotal = sum(v for v in breakdown.values())
    vat_amount = subtotal * (float(vat_rate) / 100.0)
    grand_total = subtotal + vat_amount

    # Build rows for DataFrame
    rows = []
    for item, val in breakdown.items():
        if item == "Reduction applied":
            rows.append((item, val))  # show as negative (red in HTML later)
        else:
            rows.append((item, val))

    rows += [
        ("Subtotal", subtotal),
        (f"VAT ({float(vat_rate):.1f}%)", vat_amount),
        ("Grand Total (£/month)", grand_total),
    ]
    host_df = pd.DataFrame(rows, columns=["Item", "Amount (£)"])

    ctx = {
        "subtotal": subtotal,
        "vat_amount": vat_amount,
        "grand_total": grand_total,
    }
    return host_df, ctx