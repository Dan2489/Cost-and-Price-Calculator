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

    # Prisoner wages
    breakdown["Prisoner wages"] = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)

    # Instructor costs
    instructor_cost = 0.0
    if not customer_covers_supervisors:
        instructor_cost = sum((s / 12.0) * (float(instructor_allocation) / 100.0) for s in supervisor_salaries)
        breakdown["Instructors"] = instructor_cost
    else:
        breakdown["Instructors"] = 0.0

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

    # Development charge
    dev_rate = 0.20
    if employment_support == "Employment on release/RoTL":
        dev_rate -= 0.10
    elif employment_support == "Post release":
        dev_rate -= 0.10
    elif employment_support == "Both":
        dev_rate -= 0.20
    dev_rate = max(dev_rate, 0.0)

    dev_charge = overheads_m * dev_rate
    if dev_charge > 0:
        breakdown["Development charge (applied)"] = dev_charge

    # Show reduction separately in red
    if employment_support != "None":
        reduction_val = -abs(overheads_m * (0.20 - dev_rate))
        breakdown["Development charge reduction (support applied)"] = reduction_val
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
        "subtotal": subtotal,
        "vat_amount": vat_amount,
        "grand_total": grand_total,
    }
    return host_df, ctx