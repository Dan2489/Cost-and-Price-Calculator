import pandas as pd
from config61 import CFG

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
    - Overheads = 61% * instructor-cost-base
    - If customer covers instructors: use shadow Band 3 cost (salary removed) to form overhead base
    - Dev charge applies to Commercial only; shown with reductions in red by caller
    """

    # Instructor monthly cost (split by contracts)
    if customer_covers_supervisors or num_supervisors == 0:
        instructor_monthly = 0.0
    else:
        share = (effective_pct / 100.0) / max(1, contracts_overseen)
        instructor_monthly = sum((s / 12.0) * share for s in supervisor_salaries)

    # Overhead base
    if customer_covers_supervisors:
        shadow_annual = CFG.SHADOW_COSTS.get(region, CFG.SHADOW_COSTS["National"])
        overhead_base_m = (shadow_annual / 12.0) * (effective_pct / 100.0)
    else:
        overhead_base_m = instructor_monthly

    if lock_overheads and supervisor_salaries:
        highest = max(supervisor_salaries)
        overhead_base_m = (highest / 12.0) * (effective_pct / 100.0)

    overheads_monthly = overhead_base_m * 0.61

    # Prisoner wages (monthly)
    prisoner_monthly = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)

    # Development charge (Commercial only)
    dev_charge = overheads_monthly * (dev_rate if customer_type == "Commercial" else 0.0)

    subtotal = instructor_monthly + overheads_monthly + prisoner_monthly + dev_charge

    rows = [
        ("Prisoner wages", prisoner_monthly),
        ("Instructors", instructor_monthly),
        ("Overheads (61%)", overheads_monthly),
        ("Development charge", dev_charge),
        ("Grand Total (£/month)", subtotal),
    ]
    df = pd.DataFrame(rows, columns=["Item", "Amount (£)"])

    ctx = {
        "overheads_monthly": overheads_monthly,
        "dev_charge": dev_charge,
        "grand_total": subtotal,
    }
    return df, ctx