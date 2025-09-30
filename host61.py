# host61.py
import pandas as pd
from config61 import CFG
from tariff61 import BAND3_COSTS

def generate_host_quote(
    *,
    num_prisoners: int,
    prisoner_salary: float,
    num_supervisors: int,
    customer_covers_supervisors: bool,
    supervisor_salaries: list[float],
    effective_pct: float,
    region: str,
    customer_type: str,
    dev_rate: float,
    contracts_overseen: int,
    lock_overheads: bool,
):
    """
    Host monthly breakdown using the 61% overhead model.
    Overheads = 61% * instructor-cost-base
    - If customer covers instructors: shadow Band 3 base (salary removed), then 61%
    - If locking overheads: base uses highest selected instructor salary
    - Dev charge applies only to Commercial; we also return reduction details
    """
    rows = []

    # Prisoner wages (monthly)
    prisoner_monthly = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)
    rows.append(("Prisoner wages", prisoner_monthly))

    # Instructor monthly wages (actual wages; included only if customer doesn't provide)
    if customer_covers_supervisors or num_supervisors == 0:
        instructor_monthly = 0.0
    else:
        share = (effective_pct / 100.0) / max(1, int(contracts_overseen))
        instructor_monthly = sum((s / 12.0) * share for s in supervisor_salaries)
    rows.append(("Instructors", instructor_monthly))

    # Overheads monthly (61% of base)
    if customer_covers_supervisors:
        shadow_annual = BAND3_COSTS.get(region, BAND3_COSTS["National"])
        overhead_base_m = (shadow_annual / 12.0) * (effective_pct / 100.0)
    else:
        overhead_base_m = instructor_monthly

    if lock_overheads and supervisor_salaries:
        highest = max(supervisor_salaries)
        overhead_base_m = (highest / 12.0) * (effective_pct / 100.0)

    overheads_monthly = overhead_base_m * CFG.overheads_rate
    rows.append(("Overheads (61%)", overheads_monthly))

    # Development charge (Commercial only). Show reductions in red & revised charge.
    if customer_type == "Commercial":
        base_dev = overheads_monthly * 0.20
        applied_dev = overheads_monthly * float(dev_rate)
        reduction = base_dev - applied_dev
        rows.append(("Development charge (20%)", base_dev))
        if reduction > 1e-8:
            rows.append(("Development charge reductions", -reduction))  # will render as red via .neg style if used
        rows.append(("Revised development charge", applied_dev))
        dev_to_add = applied_dev
    else:
        dev_to_add = 0.0

    subtotal = prisoner_monthly + instructor_monthly + overheads_monthly + dev_to_add
    vat_amount = subtotal * (CFG.vat_rate / 100.0)
    grand_total = subtotal + vat_amount

    rows += [
        ("Subtotal", subtotal),
        (f"VAT ({CFG.vat_rate:.0f}%)", vat_amount),
        ("Grand Total (£/month)", grand_total),
    ]

    df = pd.DataFrame(rows, columns=["Item", "Amount (£)"])
    ctx = {
        "overheads_monthly": overheads_monthly,
        "dev_charge": dev_to_add,
        "grand_total": grand_total,
    }
    return df, ctx