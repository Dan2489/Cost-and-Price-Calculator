import pandas as pd
from typing import List, Dict, Tuple

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
    apply_vat: bool,
    vat_rate: float,
    region: str,
    lock_overheads: bool,
    dev_rate: float,
) -> Tuple[pd.DataFrame, Dict]:
    breakdown: Dict[str, float] = {}

    # Prisoner wages
    breakdown["Prisoner wages"] = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)

    # Instructor cost (monthly, apportioned)
    instructor_cost = 0.0
    if not customer_covers_supervisors:
        instructor_cost = sum((s / 12.0) * (float(effective_pct) / 100.0) for s in supervisor_salaries)
    breakdown["Instructors"] = instructor_cost

    # Shadow wage (Band 3) for overheads — always calculated
    shadow_band3 = 42248.0  # national band 3
    shadow_cost = (shadow_band3 / 12.0) * (float(effective_pct) / 100.0)

    # Use either shadow cost, or highest real instructor if lock_overheads
    if customer_covers_supervisors:
        base_for_overheads = shadow_cost
    else:
        if lock_overheads and supervisor_salaries:
            highest = max(supervisor_salaries)
            base_for_overheads = (highest / 12.0) * (float(effective_pct) / 100.0)
        else:
            base_for_overheads = instructor_cost

    # Overheads = 61% of base
    overheads = base_for_overheads * 0.61
    breakdown["Overheads (61%)"] = overheads

    # Development charge (Commercial only)
    dev_charge = overheads * (float(dev_rate) if customer_type == "Commercial" else 0.0)
    breakdown["Development charge"] = dev_charge

    subtotal = sum(breakdown.values())
    vat_amount = subtotal * (float(vat_rate) / 100.0) if apply_vat else 0.0
    grand_total = subtotal + vat_amount

    rows = list(breakdown.items()) + [
        ("Subtotal", subtotal),
        (f"VAT ({float(vat_rate):.1f}%)", vat_amount),
        ("Grand Total (£/month)", grand_total),
    ]
    host_df = pd.DataFrame(rows, columns=["Item", "Amount (£)"])

    ctx = {"subtotal": subtotal, "vat_amount": vat_amount, "grand_total": grand_total}
    return host_df, ctx