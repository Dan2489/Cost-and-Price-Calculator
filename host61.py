from typing import List, Dict, Tuple
import pandas as pd
import streamlit as st
from config61 import CFG

def generate_host_quote(
    *,
    workshop_hours: float,
    area_m2: float,
    usage_key: str,
    num_prisoners: int,
    prisoner_salary: float,
    num_supervisors: int,
    customer_covers_supervisors: bool,
    supervisor_salaries: List[float],
    effective_pct: float,
    customer_type: str,
    apply_vat: bool,
    vat_rate: float,
    dev_rate: float,
    lock_overheads: bool,
) -> Tuple[pd.DataFrame, Dict]:
    breakdown: Dict[str, float] = {}
    breakdown["Prisoner wages"] = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)

    instructor_cost = 0.0
    if not customer_covers_supervisors:
        instructor_cost = sum((s / 12.0) * (float(effective_pct) / 100.0) for s in supervisor_salaries)
    breakdown["Instructors"] = instructor_cost

    # Overheads = 61% of instructor cost
    if customer_covers_supervisors:
        # Shadow Band 3 values
        shadow = {
            "Inner London": 49202.70,
            "Outer London": 45855.97,
            "National": 42247.81,
        }
        # use one band 3 shadow only
        region = st.session_state.get("region", "National")
        overheads_subtotal = shadow[region] * 0.61 / 12.0
    else:
        if lock_overheads:
            max_salary = max(supervisor_salaries) if supervisor_salaries else 0
            overheads_subtotal = (max_salary / 12.0) * 0.61
        else:
            overheads_subtotal = instructor_cost * 0.61

    breakdown["Overheads (61%)"] = overheads_subtotal

    # Development charge
    if customer_type != "Public":
        breakdown["Development charge (applied)"] = overheads_subtotal * float(dev_rate)

    subtotal = sum(breakdown.values())
    vat_amount = subtotal * (float(vat_rate) / 100.0) if apply_vat else 0.0
    grand_total = subtotal + vat_amount

    rows = list(breakdown.items()) + [
        ("Subtotal", subtotal),
        (f"VAT ({float(vat_rate):.1f}%)", vat_amount),
        ("Grand Total (£/month)", grand_total),
    ]
    host_df = pd.DataFrame(rows, columns=["Item", "Amount (£)"])

    ctx = {
        "overheads_subtotal": overheads_subtotal,
        "subtotal": subtotal,
        "vat_amount": vat_amount,
        "grand_total": grand_total,
    }
    return host_df, ctx