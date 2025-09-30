# host61.py
# Host monthly breakdown (instructor-only model)
# - Instructor wage is adjusted by % allocation
# - Overheads = 61% of that adjusted wage
# - If customer provides instructor: instructor wage = 0; overheads = 61% of Band 3 (adjusted by %)
# - Never show "shadow" Band 3 in the table
from typing import List, Dict, Tuple
import pandas as pd

from utils61 import BAND3_SHADOW_SALARY

def generate_host_quote(
    *,
    workshop_hours: float,                     # kept for compatibility (unused)
    num_prisoners: int,
    prisoner_salary: float,
    num_supervisors: int,
    customer_covers_supervisors: bool,
    supervisor_salaries: List[float],
    effective_pct: float,                      # 0..100
    customer_type: str,
    apply_vat: bool,
    vat_rate: float,
    region: str,
    lock_overheads: bool,
    dev_rate: float,
) -> Tuple[pd.DataFrame, Dict]:
    breakdown: Dict[str, float] = {}

    # Prisoner wages (monthly)
    breakdown["Prisoner wages"] = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)

    pct = float(effective_pct) / 100.0

    # Instructor wage (monthly) – adjusted by % allocation (or 0 if customer provides)
    if customer_covers_supervisors:
        instructor_monthly = 0.0
    else:
        instructor_monthly = sum((s / 12.0) * pct for s in supervisor_salaries)
    breakdown["Instructors"] = instructor_monthly

    # Base for overheads (monthly) – adjusted by % allocation
    if customer_covers_supervisors:
        base_overheads_m = (BAND3_SHADOW_SALARY.get(region, 0.0) / 12.0) * pct
    else:
        if lock_overheads and supervisor_salaries:
            base_overheads_m = (max(supervisor_salaries) / 12.0) * pct
        else:
            base_overheads_m = sum((s / 12.0) * pct for s in supervisor_salaries)

    overheads_m = 0.61 * base_overheads_m
    breakdown["Overheads (61%)"] = overheads_m

    # Development charge (Commercial only) – on overheads only
    dev_m = overheads_m * (float(dev_rate) if customer_type == "Commercial" else 0.0)
    breakdown["Development charge (applied)"] = dev_m

    subtotal = sum(breakdown.values())
    vat_amount = subtotal * (float(vat_rate) / 100.0) if apply_vat else 0.0
    grand_total = subtotal + vat_amount

    rows = list(breakdown.items()) + [
        ("Subtotal", subtotal),
        (f"VAT ({float(vat_rate):.1f}%)", vat_amount),
        ("Grand Total (£/month)", grand_total),
    ]
    host_df = pd.DataFrame(rows, columns=["Item", "Amount (£)"])
    ctx = {"subtotal": subtotal, "vat_amount": vat_amount, "grand_total": grand_total}
    return host_df, ctx