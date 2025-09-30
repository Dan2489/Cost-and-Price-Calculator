# host61.py
from typing import List, Dict, Tuple
import pandas as pd
import streamlit as st
from config61 import CFG
from utils61 import BAND3_SHADOW_SALARY

def generate_host_quote(
    *,
    workshop_hours: float,
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
    region: str,
    lock_overheads: bool = False,
) -> Tuple[pd.DataFrame, Dict]:
    breakdown: Dict[str, float] = {}
    breakdown["Prisoner wages"] = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)

    # --- Instructor costs ---
    if customer_covers_supervisors:
        instructor_cost = 0.0
        # Shadow base for overheads only (not shown in breakdown)
        base_for_overheads = BAND3_SHADOW_SALARY.get(region, 0.0) * (float(effective_pct) / 100.0)
    else:
        # Salary apportioned by effective_pct
        instructor_cost = sum((s / 12.0) * (float(effective_pct) / 100.0) for s in supervisor_salaries)
        base_for_overheads = sum((s / 12.0) * (float(effective_pct) / 100.0) for s in supervisor_salaries)

    breakdown["Instructors"] = instructor_cost

    # --- Overheads (61%) ---
    if lock_overheads and not customer_covers_supervisors and supervisor_salaries:
        # use the highest instructor cost (monthly, adjusted)
        highest = max(supervisor_salaries)
        base_for_overheads = (highest / 12.0) * (float(effective_pct) / 100.0)

    overheads_m = 0.61 * base_for_overheads
    breakdown["Overheads (61%)"] = overheads_m

    # --- Development charge (Commercial only) ---
    dev_charge = overheads_m * (float(dev_rate) if customer_type == "Commercial" else 0.0)
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