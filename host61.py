# host61.py
from typing import List, Dict, Tuple
import pandas as pd
from utils61 import currency

# Band 3 shadow costs (annual)
BAND3_COSTS = {
    "Outer London": 45855.97,
    "Inner London": 49202.70,
    "National": 42247.81,
}

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
    lock_overheads: bool = False,
) -> Tuple[pd.DataFrame, Dict]:
    breakdown: Dict[str, float] = {}

    # Prisoner wages (monthly)
    breakdown["Prisoner wages"] = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)

    # Instructor cost (monthly)
    instructor_cost_m = 0.0
    if not customer_covers_supervisors:
        instructor_cost_m = sum((s / 12.0) * (effective_pct / 100.0) for s in supervisor_salaries)
    breakdown["Instructors"] = instructor_cost_m

    # Overhead base
    if customer_covers_supervisors:
        shadow = BAND3_COSTS.get(region, 42247.81)
        overhead_base = (shadow / 12.0) * (effective_pct / 100.0)
    else:
        overhead_base = instructor_cost_m

    if lock_overheads and supervisor_salaries:
        overhead_base = (max(supervisor_salaries) / 12.0) * (effective_pct / 100.0)

    overheads_m = overhead_base * 0.61
    breakdown["Overheads (61%)"] = overheads_m

    # Development charge (Commercial only)
    if customer_type == "Commercial":
        dev_charge = overheads_m * dev_rate
        breakdown["Development charge (applied)"] = dev_charge
    else:
        dev_charge = 0.0

    subtotal = sum(breakdown.values())
    grand_total = subtotal

    rows = list(breakdown.items()) + [
        ("Subtotal", subtotal),
        ("Grand Total (£/month)", grand_total),
    ]

    host_df = pd.DataFrame(rows, columns=["Item", "Amount (£)"])
    host_df["Amount (£)"] = host_df["Amount (£)"].apply(currency)

    ctx = {
        "subtotal": subtotal,
        "grand_total": grand_total,
    }
    return host_df, ctx