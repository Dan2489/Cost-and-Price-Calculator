from typing import List, Dict, Tuple
import pandas as pd
from utils61 import fmt_currency

def generate_host_quote(
    *,
    workshop_hours: float,
    num_prisoners: int,
    prisoner_salary: float,
    num_supervisors: int,
    supervisor_salaries: List[float],
    region: str,
    contracts: int = 1,
    employment_support: str = "None",
    instructor_allocation: float = 100.0,
    lock_overheads: bool = False,
) -> Tuple[pd.DataFrame, Dict]:
    """
    Host quote calculation:
    - Prisoner wages
    - Instructor costs
    - Overheads at 61%
    - Development charge based on employment_support
    """

    breakdown: Dict[str, float] = {}

    # Prisoner wages (monthly)
    breakdown["Prisoner wages"] = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)

    # Instructor costs (monthly, apportioned by contracts and allocation)
    instructor_cost = 0.0
    if num_supervisors > 0:
        instructor_cost = sum(
            (s / 12.0) * (instructor_allocation / 100.0) * (1.0 / contracts)
            for s in supervisor_salaries
        )
    breakdown["Instructors"] = instructor_cost

    # Overheads: 61% of instructor cost (locked if requested)
    if lock_overheads and supervisor_salaries:
        overhead_base = (max(supervisor_salaries) / 12.0) * (instructor_allocation / 100.0) * (1.0 / contracts)
    else:
        overhead_base = instructor_cost
    breakdown["Overheads (61%)"] = overhead_base * 0.61

    # Development charge (Commercial only: 20%, reduced for employment support)
    dev_rate = 0.20
    if employment_support == "Employment on release/RoTL":
        dev_rate = 0.10
    elif employment_support == "Post release":
        dev_rate = 0.10
    elif employment_support == "Both":
        dev_rate = 0.00

    breakdown["Development charge (before reductions)"] = overhead_base * 0.20
    if dev_rate < 0.20:
        reduction = overhead_base * (0.20 - dev_rate)
        breakdown["Development charge reductions"] = -reduction
    breakdown["Revised development charge"] = overhead_base * dev_rate

    # Subtotal
    subtotal = sum(breakdown.values())
    breakdown["Subtotal"] = subtotal

    # VAT 20%
    vat_amount = subtotal * 0.20
    breakdown["VAT (20%)"] = vat_amount

    # Grand total
    grand_total = subtotal + vat_amount
    breakdown["Grand Total (£/month)"] = grand_total

    # Build DataFrame
    rows = [(k, v) for k, v in breakdown.items()]
    host_df = pd.DataFrame(rows, columns=["Item", "Amount (£)"])

    ctx = {
        "subtotal": subtotal,
        "vat_amount": vat_amount,
        "grand_total": grand_total,
    }
    return host_df, ctx