from typing import List, Dict, Tuple
import pandas as pd

from config61 import CFG

def generate_host_quote(
    *,
    workshop_hours: float,
    num_prisoners: int,
    prisoner_salary: float,
    num_supervisors: int,
    customer_covers_supervisors: bool,
    supervisor_salaries: List[float],
    effective_pct: float,
    customer_type: str,
    apply_vat: bool,   # kept for compatibility (always True in app)
    vat_rate: float,   # e.g. 20.0
) -> Tuple[pd.DataFrame, Dict]:
    """
    Generate monthly host quote breakdown.
    - Overheads = 61% of instructor cost (or Band 3 shadow if customer provides)
    """

    breakdown: Dict[str, float] = {}

    # Prisoner wages (weekly → monthly)
    breakdown["Prisoner wages"] = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)

    # Instructor costs
    instructor_cost = 0.0
    if not customer_covers_supervisors:
        instructor_cost = sum((s / 12.0) * (float(effective_pct) / 100.0) for s in supervisor_salaries)
    breakdown["Instructors"] = instructor_cost

    # Overheads = 61% of instructor costs
    overheads_subtotal = instructor_cost * 0.61
    breakdown["Overheads (61%)"] = overheads_subtotal

    # Development charge (Commercial only)
    dev_rate = 0.0  # no separate dev slider in host mode
    breakdown["Development charge (applied)"] = overheads_subtotal * (float(dev_rate) if customer_type == "Commercial" else 0.0)

    # Subtotal
    subtotal = sum(breakdown.values())

    # VAT (always applied)
    vat_amount = subtotal * (float(vat_rate) / 100.0)
    grand_total = subtotal + vat_amount

    rows = list(breakdown.items()) + [
        ("Subtotal", subtotal),
        (f"VAT ({float(vat_rate):.1f}%)", vat_amount),
        ("Grand Total (£/month)", grand_total),
    ]
    host_df = pd.DataFrame(rows, columns=["Item", "Amount (£)"])

    ctx = {
        "overheads_subtotal": overheads_subtotal,
        "subtotal": subtotal,
        "vat_amount": vat_amount,
        "grand_total": grand_total,
    }
    return host_df, ctx