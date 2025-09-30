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
    dev_rate: float,   # 0.2 by default, reduced if support offered
) -> Tuple[pd.DataFrame, Dict]:
    breakdown: Dict[str, float] = {}

    # Prisoner wages
    breakdown["Prisoner wages"] = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)

    # Instructor costs
    instructor_cost = 0.0
    if not customer_covers_supervisors:
        instructor_cost = sum((s / 12.0) * (float(effective_pct) / 100.0) for s in supervisor_salaries)
    breakdown["Instructors"] = instructor_cost

    # Overheads = 61% of instructor costs (or shadow Band 3 if customer provides)
    if customer_covers_supervisors:
        shadow = BAND3_COSTS.get(region, BAND3_COSTS["National"])
        overhead_base = (shadow / 12.0) * (float(effective_pct) / 100.0)
    else:
        overhead_base = instructor_cost
    overheads_monthly = overhead_base * 0.61
    breakdown["Overheads (61%)"] = overheads_monthly

    # Development charge (Commercial only, reduced by support)
    if customer_type == "Commercial":
        dev_charge = overheads_monthly * dev_rate
        breakdown["Development charge (applied)"] = dev_charge
    else:
        dev_charge = 0.0
        breakdown["Development charge (not applied)"] = 0.0

    # Subtotal
    subtotal = sum(breakdown.values())

    rows = list(breakdown.items()) + [
        ("Subtotal (£/month)", subtotal),
    ]
    host_df = pd.DataFrame(rows, columns=["Item", "Amount (£)"])

    ctx = {
        "overheads_monthly": overheads_monthly,
        "subtotal": subtotal,
        "dev_charge": dev_charge,
    }
    return host_df, ctx