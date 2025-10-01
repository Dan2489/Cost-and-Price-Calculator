from typing import List, Dict, Tuple
import pandas as pd

def generate_production_quote(
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
    prisoner_output: float = 100.0,
) -> Tuple[pd.DataFrame, Dict]:
    """
    Simplified production calculation placeholder.
    Your full contractual/adhoc workflow can plug in here.
    """
    breakdown: Dict[str, float] = {}

    # prisoner wages
    wages_month = num_prisoners * prisoner_salary * (52.0 / 12.0)
    breakdown["Prisoner wages"] = wages_month

    # instructors
    inst_month = sum((s / 12.0) * (instructor_allocation / 100.0) * (1.0 / contracts) for s in supervisor_salaries)
    breakdown["Instructors"] = inst_month

    # overheads 61%
    overhead_base = inst_month
    breakdown["Overheads (61%)"] = overhead_base * 0.61

    subtotal = sum(breakdown.values())
    breakdown["Subtotal"] = subtotal
    vat_amount = subtotal * 0.20
    breakdown["VAT (20%)"] = vat_amount
    grand_total = subtotal + vat_amount
    breakdown["Grand Total (£/month)"] = grand_total

    rows = [(k, v) for k, v in breakdown.items()]
    prod_df = pd.DataFrame(rows, columns=["Item", "Amount (£)"])
    ctx = {"subtotal": subtotal, "vat_amount": vat_amount, "grand_total": grand_total}
    return prod_df, ctx