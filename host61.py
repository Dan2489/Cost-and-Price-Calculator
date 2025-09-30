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
    Overheads base = instructor cost base:
      - If customer provides instructors: use Band 3 shadow salary for region (salary removed); apply effective_pct; then 61%.
      - Else: use actual selected instructors (apportioned by contracts and effective_pct); then 61%.
      - If lock_overheads=True and there are instructors: base uses the HIGHEST instructor salary (still paying all selected wages).
    Dev charge:
      - Applies only when customer_type == "Commercial"
      - Base is 20%; reductions are reflected by dev_rate (after reductions)
      - Show (20%), reductions (red), and revised dev charge.
    """
    rows: list[tuple[str, float]] = []

    # Prisoner wages (monthly)
    prisoner_monthly = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)
    rows.append(("Prisoner wages", prisoner_monthly))

    # Instructor monthly wages (added ONLY if customer doesn't provide)
    if customer_covers_supervisors or num_supervisors == 0:
        instructor_monthly = 0.0
    else:
        # Apportion each instructor by contracts and effective %
        share = (float(effective_pct) / 100.0) / max(1, int(contracts_overseen))
        instructor_monthly = sum((s / 12.0) * share for s in supervisor_salaries)
    rows.append(("Instructors", instructor_monthly))

    # Overheads monthly (61% of base)
    if customer_covers_supervisors:
        shadow_annual = BAND3_COSTS.get(region, BAND3_COSTS["National"])
        overhead_base_m = (shadow_annual / 12.0) * (float(effective_pct) / 100.0)
    else:
        overhead_base_m = instructor_monthly

    if lock_overheads and supervisor_salaries:
        highest = max(supervisor_salaries)
        overhead_base_m = (highest / 12.0) * (float(effective_pct) / 100.0)

    overheads_monthly = overhead_base_m * 0.61
    rows.append(("Overheads (61%)", overheads_monthly))

    # Development charge (Commercial only): show 20%, reductions (red), revised
    dev_to_add = 0.0
    if customer_type == "Commercial":
        base_dev = overheads_monthly * 0.20
        applied_dev = overheads_monthly * float(dev_rate)
        reduction = base_dev - applied_dev
        rows.append(("Development charge (20%)", base_dev))
        if reduction > 1e-8:
            rows.append(("Development charge reductions", -reduction))  # render red in UI
        rows.append(("Revised development charge", applied_dev))
        dev_to_add = applied_dev

    subtotal = prisoner_monthly + instructor_monthly + overheads_monthly + dev_to_add
    vat_amount = subtotal * (20.0 / 100.0)
    grand_total = subtotal + vat_amount

    rows += [
        ("Subtotal", subtotal),
        ("VAT (20%)", vat_amount),
        ("Grand Total (£/month)", grand_total),
    ]

    # Also return a DataFrame for CSV export
    df = pd.DataFrame(rows, columns=["Item", "Amount (£)"])
    ctx = {
        "rows": rows,
        "subtotal": subtotal,
        "vat_amount": vat_amount,
        "grand_total": grand_total,
    }
    return df, ctx