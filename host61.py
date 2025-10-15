# host61.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple

import pandas as pd

# Public API: generate_host_quote(...)
# This is intentionally dependency-light so it can be imported by Streamlit app.

@dataclass
class HostContext:
    monthly_wages: float
    monthly_instructor: float
    monthly_overheads: float
    monthly_development: float
    monthly_benefits_reduction: float
    monthly_subtotal_ex_vat: float
    monthly_vat: float
    monthly_grand_total_ex_vat: float
    monthly_grand_total_inc_vat: float

def _round2(x: float) -> float:
    return round(float(x), 2)

def _monthly_from_weekly(x: float) -> float:
    # same convention used elsewhere: 52/12
    return x * 52.0 / 12.0

def _dev_rate_from_support(s: str) -> float:
    if s == "None":
        return 0.20
    if s in ("Employment on release/RoTL", "Post release"):
        return 0.10
    # "Both"
    return 0.00

def _effective_allocation(workshop_hours: float, contracts: int) -> float:
    # Same logic you used previously for “recommended %”, capped at 100
    if workshop_hours <= 0 or contracts <= 0:
        return 0.0
    pct = (workshop_hours / 37.5) * (1.0 / contracts) * 100.0
    return min(100.0, max(0.0, pct))

def generate_host_quote(
    *,
    workshop_hours: float,
    num_prisoners: int,
    prisoner_salary: float,
    num_supervisors: int,
    customer_covers_supervisors: bool,
    supervisor_salaries: List[float],
    region: str,
    contracts: int,
    employment_support: str,
    lock_overheads: bool,
    benefits_checkbox: bool,
    benefits_desc: str | None,
    benefits_discount_pc: float,
) -> Tuple[pd.DataFrame, HostContext]:
    """
    Returns (DataFrame, context). The DF is your summary table (ordered, with borders via utils).
    Shadow overheads apply if customer provides instructors (instructor salary = 0 but
    overhead base = weekly cost of the *highest* selected salary under the recommended allocation).
    The “Additional benefits reduction” appears as a single, negative row AFTER development charge
    and is 10% (configurable) of (Instructor + Overheads + Development) only when Employment Support = 'Both'
    AND the checkbox is ticked.
    """
    # --- labour: wages ---
    weekly_wages = float(num_prisoners) * float(prisoner_salary)
    monthly_wages = _monthly_from_weekly(weekly_wages)

    # --- recommended allocation % (for basing costs) ---
    alloc_pct = _effective_allocation(workshop_hours, max(1, contracts)) / 100.0

    # --- instructor base (weekly) ---
    wk_costs = [(s / 52.0) for s in supervisor_salaries] if supervisor_salaries else []
    if lock_overheads and wk_costs:
        base_weekly_instructor = max(wk_costs)
    else:
        base_weekly_instructor = sum(wk_costs)  # if none, 0

    # Effective instructor (allocation applied)
    eff_weekly_instructor = base_weekly_instructor * alloc_pct

    # If customer provides instructors, then salary is 0 but we still need a shadow base for overheads
    if customer_covers_supervisors:
        monthly_instructor = 0.0
        # shadow overhead base: use the *highest* weekly instructor cost at allocation
        shadow_weekly_base = (max(wk_costs) if wk_costs else 0.0) * alloc_pct
        overhead_base_weekly = shadow_weekly_base
    else:
        monthly_instructor = _monthly_from_weekly(eff_weekly_instructor)
        overhead_base_weekly = eff_weekly_instructor  # overheads ride on the real instructor cost

    # --- overheads (61%) ---
    monthly_overheads = _monthly_from_weekly(overhead_base_weekly * 0.61)

    # --- development charge from support policy ---
    dev_rate = _dev_rate_from_support(employment_support)
    monthly_development = _round2(monthly_overheads * dev_rate)

    # --- benefits (single line reduction after dev) ---
    # only if support == Both and benefits checkbox ticked
    if (employment_support == "Both") and benefits_checkbox:
        benefits_base = monthly_instructor + monthly_overheads + monthly_development
        monthly_benefits_reduction = _round2(-abs(benefits_base * (benefits_discount_pc / 100.0)))
    else:
        monthly_benefits_reduction = 0.0

    # --- totals ---
    monthly_subtotal_ex_vat = _round2(
        monthly_wages + monthly_instructor + monthly_overheads + monthly_development + monthly_benefits_reduction
    )
    # VAT is on the subtotal (your current host CSVs include VAT in exports, so we keep it here)
    monthly_vat = _round2(monthly_subtotal_ex_vat * 0.20)
    monthly_grand_total_ex_vat = monthly_subtotal_ex_vat
    monthly_grand_total_inc_vat = _round2(monthly_subtotal_ex_vat + monthly_vat)

    # Build display rows (only show relevant lines)
    rows = []
    rows.append({"Item": "Prisoner Wages", "Amount (£)": _round2(monthly_wages)})
    # Instructor Salary (hide if 0)
    if monthly_instructor != 0:
        rows.append({"Item": "Instructor Salary", "Amount (£)": _round2(monthly_instructor)})
    # Overheads – no “(61%)” suffix per your request
    rows.append({"Item": "Overheads", "Amount (£)": _round2(monthly_overheads)})
    # Development Charge (always shown, can be zero)
    rows.append({"Item": "Development Charge", "Amount (£)": _round2(monthly_development)})
    # Additional benefits reduction (show if non-zero)
    if monthly_benefits_reduction != 0:
        rows.append({"Item": "Additional benefits reduction", "Amount (£)": _round2(monthly_benefits_reduction)})

    rows.append({"Item": "Subtotal (ex VAT)", "Amount (£)": monthly_subtotal_ex_vat})
    rows.append({"Item": "VAT (20%)", "Amount (£)": monthly_vat})
    rows.append({"Item": "Grand Total (ex VAT)", "Amount (£)": monthly_grand_total_ex_vat})
    rows.append({"Item": "Grand Total (inc VAT)", "Amount (£)": monthly_grand_total_inc_vat})

    df = pd.DataFrame(rows)

    ctx = HostContext(
        monthly_wages=_round2(monthly_wages),
        monthly_instructor=_round2(monthly_instructor),
        monthly_overheads=_round2(monthly_overheads),
        monthly_development=_round2(monthly_development),
        monthly_benefits_reduction=_round2(monthly_benefits_reduction),
        monthly_subtotal_ex_vat=monthly_subtotal_ex_vat,
        monthly_vat=monthly_vat,
        monthly_grand_total_ex_vat=monthly_grand_total_ex_vat,
        monthly_grand_total_inc_vat=monthly_grand_total_inc_vat,
    )
    return df, ctx