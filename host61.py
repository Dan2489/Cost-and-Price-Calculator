# host61.py
import pandas as pd
from typing import List, Dict, Tuple
from tariff61 import BAND3_COSTS

def generate_host_quote(
    *,
    num_prisoners: int,
    prisoner_salary: float,
    num_supervisors: int,
    customer_covers_supervisors: bool,
    supervisor_salaries: List[float],
    effective_pct: float,
    region: str,
    customer_type: str,
    dev_rate: float,
    lock_overheads: bool,
) -> Tuple[pd.DataFrame, Dict]:
    breakdown: Dict[str, float] = {}

    # Prisoner wages
    breakdown["Prisoner wages"] = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)

    # Instructor cost
    instructor_cost = 0.0
    if not customer_covers_supervisors:
        instructor_cost = sum((s / 12.0) * (float(effective_pct) / 100.0) for s in supervisor_salaries)
    breakdown["Instructors"] = instructor_cost

    # Overheads
    if customer_covers_supervisors:
        shadow = BAND3_COSTS.get(region, BAND3_COSTS["National"])
        overhead_base = (shadow / 12.0) * (effective_pct / 100.0)
    else:
        overhead_base = instructor_cost

    if lock_overheads and supervisor_salaries:
        overhead_base = (max(supervisor_salaries) / 12.0) * (effective_pct / 100.0)

    overheads_monthly = overhead_base * 0.61
    breakdown["Overheads (61%)"] = overheads_monthly

    # Development charge (Commercial only)
    development_charge = overheads_monthly * (float(dev_rate) if customer_type == "Commercial" else 0.0)
    breakdown["Development charge"] = development_charge

    subtotal = sum(breakdown.values())
    vat_rate = 20.0
    vat_amount = subtotal * (vat_rate / 100.0)
    grand_total = subtotal + vat_amount

    rows = list(breakdown.items()) + [
        ("Subtotal", subtotal),
        (f"VAT ({vat_rate:.1f}%)", vat_amount),
        ("Grand Total (£/month)", grand_total),
    ]
    host_df = pd.DataFrame(rows, columns=["Item", "Amount (£)"])

    ctx = {
        "subtotal": subtotal,
        "vat_amount": vat_amount,
        "grand_total": grand_total,
    }
    return host_df, ctx