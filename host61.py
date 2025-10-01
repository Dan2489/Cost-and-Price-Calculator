# host61.py
from typing import List, Dict, Tuple
import pandas as pd
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
    contracts_overseen: int,
    lock_overheads: bool,
) -> Tuple[pd.DataFrame, Dict]:
    breakdown: Dict[str, float] = {}

    # Prisoner wages (monthly)
    breakdown["Prisoner wages"] = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)

    # Instructor cost (monthly)
    instructor_cost = 0.0
    if not customer_covers_supervisors:
        share = (float(effective_pct) / 100.0) / max(1, int(contracts_overseen))
        instructor_cost = sum((s / 12.0) * share for s in supervisor_salaries)
    breakdown["Instructors"] = instructor_cost

    # Overheads based on 61%
    if customer_covers_supervisors:
        shadow = BAND3_COSTS.get(region, BAND3_COSTS["National"])
        overhead_base = (shadow / 12.0) * (float(effective_pct) / 100.0)
    else:
        overhead_base = instructor_cost

    if lock_overheads and supervisor_salaries:
        overhead_base = (max(supervisor_salaries) / 12.0) * (float(effective_pct) / 100.0)

    overheads_m = overhead_base * 0.61
    breakdown["Overheads (61%)"] = overheads_m

    # Development charge (Commercial only)
    dev_charge = overheads_m * (float(dev_rate) if customer_type == "Commercial" else 0.0)
    if dev_charge > 0:
        breakdown["Development charge (applied)"] = dev_charge
        if dev_rate < 0.20:
            reduction = overheads_m * 0.20 - dev_charge
            breakdown["Development charge reduction"] = -reduction
            breakdown["Revised development charge"] = dev_charge

    subtotal = sum(breakdown.values())
    vat_amount = subtotal * 0.20
    grand_total = subtotal + vat_amount

    rows = list(breakdown.items()) + [
        ("Subtotal", subtotal),
        ("VAT (20%)", vat_amount),
        ("Grand Total (£/month)", grand_total),
    ]
    host_df = pd.DataFrame(rows, columns=["Item", "Amount (£)"])

    ctx = {
        "rows": rows,
        "subtotal": subtotal,
        "vat_amount": vat_amount,
        "grand_total": grand_total,
    }
    return host_df, ctx