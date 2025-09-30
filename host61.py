from typing import List, Dict, Tuple
import pandas as pd

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
    vat_rate: float,
    dev_rate: float,
    lock_overheads: bool = False
) -> Tuple[pd.DataFrame, Dict]:
    breakdown: Dict[str, float] = {}
    breakdown["Prisoner wages"] = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)

    # Instructor costs
    if not customer_covers_supervisors:
        instructor_cost = sum((s / 12.0) * (effective_pct / 100.0) for s in supervisor_salaries)
        breakdown["Instructors"] = instructor_cost
    else:
        instructor_cost = 0.0

    # Determine overhead base
    if customer_covers_supervisors:
        shadow = BAND3_COSTS.get(region, 42247.81)  # default National
        overhead_base = (shadow / 12.0) * (effective_pct / 100.0)
    else:
        overhead_base = instructor_cost

    if lock_overheads and supervisor_salaries:
        overhead_base = (max(supervisor_salaries) / 12.0) * (effective_pct / 100.0)

    breakdown["Overheads (61%)"] = overhead_base * 0.61

    # Development charge
    dev_charge = 0.0
    if customer_type == "Commercial":
        dev_charge = breakdown["Overheads (61%)"] * dev_rate
        breakdown["Development charge"] = dev_charge

    subtotal = sum(breakdown.values())
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