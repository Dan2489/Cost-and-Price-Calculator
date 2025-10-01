from typing import List, Dict, Tuple
import pandas as pd
from tariff61 import BAND3_COSTS

def generate_host_quote(
    *,
    workshop_hours: float,
    num_prisoners: int,
    prisoner_salary: float,
    num_supervisors: int,
    customer_covers_supervisors: bool,
    supervisor_salaries: List[float],
    region: str,
    contracts: int,
    employment_support: str,
    instructor_allocation: float,
    lock_overheads: bool,
) -> Tuple[pd.DataFrame, Dict]:
    breakdown: Dict[str, float] = {}

    # Prisoner Wages
    breakdown["Prisoner Wages"] = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)

    # Instructor Salary
    instructor_cost = 0.0
    if not customer_covers_supervisors:
        instructor_cost = sum((s / 12.0) * (float(instructor_allocation) / 100.0) for s in supervisor_salaries)
        breakdown["Instructor Salary"] = instructor_cost
    else:
        breakdown["Instructor Salary"] = 0.0

    # Overheads (61%)
    if customer_covers_supervisors:
        shadow = BAND3_COSTS.get(region, BAND3_COSTS["National"])
        overhead_base = (shadow / 12.0) * (float(instructor_allocation) / 100.0)
    else:
        overhead_base = instructor_cost

    if lock_overheads and supervisor_salaries:
        overhead_base = (max(supervisor_salaries) / 12.0) * (float(instructor_allocation) / 100.0)

    overheads_m = overhead_base * 0.61
    breakdown["Overheads (61%)"] = overheads_m

    # Development Charge – always 20% of overheads
    full_dev_charge = overheads_m * 0.20
    breakdown["Development Charge"] = full_dev_charge

    # Apply reductions
    reduction_val = 0.0
    if employment_support == "Employment on release/RoTL":
        reduction_val = -abs(overheads_m * 0.10)
    elif employment_support == "Post release":
        reduction_val = -abs(overheads_m * 0.10)
    elif employment_support == "Both":
        reduction_val = -abs(overheads_m * 0.20)

    if reduction_val != 0.0:
        breakdown["Development Charge Reduction (Support Applied)"] = reduction_val

    revised_dev_charge = full_dev_charge + reduction_val
    breakdown["Revised Development Charge"] = revised_dev_charge

    # Totals
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
        "subtotal": subtotal,
        "vat_amount": vat_amount,
        "grand_total": grand_total,
    }
    return host_df, ctx