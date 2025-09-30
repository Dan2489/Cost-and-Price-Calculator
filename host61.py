import pandas as pd
import streamlit as st
from config61 import CFG
from utils61 import BAND3_SHADOW

def generate_host_quote(
    *,
    num_prisoners: int,
    prisoner_salary: float,
    num_supervisors: int,
    customer_covers_supervisors: bool,
    supervisor_salaries: list[float],
    effective_pct: float,
    region: str,
    customer_type: str,
    vat_rate: float,
    dev_rate: float,
) -> tuple[pd.DataFrame, dict]:
    breakdown: dict[str, float] = {}
    # Prisoner wages
    breakdown["Prisoner wages"] = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)

    # Instructors
    instructor_cost = 0.0
    if not customer_covers_supervisors:
        instructor_cost = sum((s / 12.0) * (float(effective_pct) / 100.0) for s in supervisor_salaries)
    breakdown["Instructors"] = instructor_cost

    # Overheads: 61% of instructor costs (or shadow Band 3 if customer provides)
    if customer_covers_supervisors:
        shadow_salary = BAND3_SHADOW.get(region, BAND3_SHADOW["National"])
        overheads = shadow_salary * CFG.OVERHEAD_PCT / 12.0
    else:
        if st.session_state.get("lock_overheads"):
            highest = max(supervisor_salaries) if supervisor_salaries else 0.0
            overheads = (highest / 12.0) * CFG.OVERHEAD_PCT
        else:
            overheads = sum(((s / 12.0) * CFG.OVERHEAD_PCT) for s in supervisor_salaries)
    breakdown["Overheads (61%)"] = overheads

    # Development charge
    dev_charge = 0.0
    if customer_type == "Commercial":
        dev_charge = overheads * float(dev_rate)
        breakdown["Development charge (before reductions)"] = overheads * 0.20
        if dev_rate < 0.20:
            reduction = (0.20 - dev_rate) * overheads
            breakdown["Reductions"] = -reduction
        breakdown["Revised Development charge"] = dev_charge
    breakdown["Development charge (applied)"] = dev_charge

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