# host61.py
# Host monthly breakdown: based only on prisoner wages + instructor costs + 61% overheads
from typing import List, Dict, Tuple
import pandas as pd
import streamlit as st
from config61 import CFG
from tariff61 import BAND3_SHADOW_COSTS

def generate_host_quote(
    *,
    workshop_hours: float,
    num_prisoners: int,
    prisoner_salary: float,
    num_supervisors: int,
    customer_covers_supervisors: bool,
    supervisor_salaries: List[float],
    lock_overheads: bool,
    region: str,
    apply_vat: bool,
    vat_rate: float,
) -> Tuple[pd.DataFrame, Dict]:
    breakdown: Dict[str, float] = {}
    # Prisoner wages
    breakdown["Prisoner wages"] = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)

    # Instructor cost
    if not customer_covers_supervisors:
        instructor_cost = sum((s / 12.0) for s in supervisor_salaries)
    else:
        # Shadow Band 3 cost if customer provides instructor
        band3_salary = BAND3_SHADOW_COSTS.get(region, 0.0)
        instructor_cost = 0.0
        breakdown["Shadow Instructor (Band 3)"] = band3_salary / 12.0
    breakdown["Instructors"] = instructor_cost

    # Overheads = 61% of instructor cost (lock to highest if selected)
    if lock_overheads and supervisor_salaries:
        highest_cost = max(supervisor_salaries)
        overheads = (highest_cost * 0.61) / 12.0
    else:
        ref_cost = (sum(supervisor_salaries) if supervisor_salaries else BAND3_SHADOW_COSTS.get(region, 0.0))
        overheads = (ref_cost * 0.61) / 12.0
    breakdown["Overheads (61%)"] = overheads

    subtotal = sum(breakdown.values())
    vat_amount = subtotal * (float(vat_rate) / 100.0)
    grand_total = subtotal + vat_amount

    rows = list(breakdown.items()) + [
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