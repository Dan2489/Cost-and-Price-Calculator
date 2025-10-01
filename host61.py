# host61.py
import pandas as pd
from typing import Dict, List, Tuple

from tariff61 import BAND3_COSTS

def generate_host_quote(
    *,
    num_prisoners: int,
    prisoner_salary: float,
    num_supervisors: int,
    customer_covers_supervisors: bool,
    supervisor_salaries: List[float],
    effective_pct: float,         # instructor allocation %
    region: str,
    customer_type: str,
    dev_rate: float,              # already reduced per support; 0 if Another Government Department
    contracts_overseen: int,
    lock_overheads: bool,
) -> Tuple[pd.DataFrame, Dict]:

    rows = []

    # Prisoner wages (monthly)
    prisoner_wages_m = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)
    rows.append(("Prisoner wages", prisoner_wages_m))

    # Instructor cost (monthly) – excluded if customer provides instructor(s)
    if customer_covers_supervisors:
        instructor_m_total = 0.0
    else:
        share = (float(effective_pct) / 100.0) / max(1, int(contracts_overseen))
        instructor_m_total = sum(((s / 12.0) * share) for s in supervisor_salaries)
    if instructor_m_total > 0:
        rows.append(("Instructors", instructor_m_total))

    # Overheads (61%) – base either shadow Band 3 (if customer provides) or instructor cost
    if customer_covers_supervisors:
        shadow = BAND3_COSTS.get(region, BAND3_COSTS["National"])
        overhead_base_m = (shadow / 12.0) * (float(effective_pct) / 100.0)
    else:
        overhead_base_m = instructor_m_total

    if lock_overheads and supervisor_salaries:
        overhead_base_m = (max(supervisor_salaries) / 12.0) * (float(effective_pct) / 100.0)

    overheads_m = overhead_base_m * 0.61
    rows.append(("Overheads (61%)", overheads_m))

    # Development charge (Commercial only) – show full, reductions (red), revised
    dev_rows = []
    if customer_type == "Commercial":
        # The incoming dev_rate is already reduced (0.20 - selected reductions), we present components
        # For display, we reconstruct "base" and "reductions"
        base_dev_rate = 0.20
        reduction_rate = base_dev_rate - float(dev_rate)
        base_dev = overheads_m * base_dev_rate
        reduction_amount = overheads_m * reduction_rate
        revised_dev = overheads_m * float(dev_rate)

        dev_rows.append(("Development charge (20%)", base_dev))
        if reduction_amount > 0:
            dev_rows.append(("Development charge reductions", -reduction_amount))  # red via render_summary_table
        dev_rows.append(("Revised development charge", revised_dev))
        rows.extend(dev_rows)

    # Subtotal, VAT (20%), Grand Total (monthly)
    subtotal = sum(v for _, v in rows