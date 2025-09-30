import pandas as pd
from typing import List, Dict, Tuple
from utils61 import CFG, BAND3_SHADOW

def generate_host_quote(
    *,
    workshop_hours: float,
    area_m2: float,
    usage_key: str,
    num_prisoners: int,
    prisoner_salary: float,
    num_supervisors: int,
    customer_covers_supervisors: bool,
    supervisor_salaries: List[float],
    effective_pct: float,
    customer_type: str,
    apply_vat: bool,
    vat_rate: float,
    dev_rate: float,
    lock_overheads: bool,
) -> Tuple[pd.DataFrame, Dict]:
    breakdown: Dict[str, float] = {}
    breakdown["Prisoner wages"] = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)

    # Instructor salaries (only if customer doesn't provide)
    instructor_cost = 0.0
    if not customer_covers_supervisors:
        instructor_cost = sum((s / 12.0) * (float(effective_pct) / 100.0) for s in supervisor_salaries)
        breakdown["Instructors"] = instructor_cost

    # Overheads = 61% of instructor costs
    if customer_covers_supervisors:
        # Shadow: 61% of Band 3 only
        region = CFG.get("region", "National")
        base = BAND3_SHADOW.get(region, BAND3_SHADOW["National"])
        overheads = (base / 12.0) * 0.61
    else:
        if lock_overheads and supervisor_salaries:
            highest = max(supervisor_salaries)
            base = (highest / 12.0) * (float(effective_pct) / 100.0)
            overheads = base * 0.61
        else:
            overheads = instructor_cost * 0.61
    breakdown["Overheads (61%)"] = overheads

    # Development charge (only for Commercial)
    dev_amount = (instructor_cost + overheads) * float(dev_rate) if customer_type == "Commercial" else 0.0
    if customer_type == "Commercial":
        breakdown["Development charge (applied)"] = dev_amount

    subtotal = sum(breakdown.values())
    vat_amount = subtotal * (float(vat_rate) / 100.0) if apply_vat else 0.0
    grand_total = subtotal + vat_amount

    rows = list(breakdown.items()) + [
        ("Subtotal", subtotal),
        (f"VAT ({float(vat_rate):.1f}%)", vat_amount),
        ("Grand Total (£/month)", grand_total),
    ]
    host_df = pd.DataFrame(rows, columns=["Item", "Amount (£)"])
    ctx = {
        "overheads": overheads,
        "subtotal": subtotal,
        "vat": vat_amount,
        "grand": grand_total,
        "dev_amount": dev_amount,
    }
    return host_df, ctx