# host61.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple
import pandas as pd

@dataclass
class HostContext:
    monthly_wages: float
    monthly_instructor: float
    monthly_overheads: float
    monthly_dev_base: float
    monthly_dev_discount: float
    monthly_dev_revised: float
    monthly_benefits_reduction: float
    monthly_subtotal_ex_vat: float
    monthly_vat: float
    monthly_grand_total_ex_vat: float
    monthly_grand_total_inc_vat: float

def _r2(x: float) -> float:
    return round(float(x), 2)

def _m_from_w(x: float) -> float:
    # 52 weeks / 12 months
    return x * 52.0 / 12.0

def _support_dev_rate(s: str) -> float:
    # Final (revised) development rate after support
    # None -> 20%, RoTL/Post -> 10%, Both -> 0%
    if s == "None":
        return 0.20
    if s in ("Employment on release/RoTL", "Post release"):
        return 0.10
    return 0.00  # Both

def _recommended_allocation(workshop_hours: float, contracts: int) -> float:
    if workshop_hours <= 0 or contracts <= 0:
        return 0.0
    pct = (workshop_hours / 37.5) * (1.0 / contracts) * 100.0
    return min(100.0, max(0.0, pct)) / 100.0

def _base_dev_rate() -> float:
    # Base “list” rate used to show Development discount line
    return 0.20

def _compute_common_costs(
    *,
    workshop_hours: float,
    contracts: int,
    customer_covers_supervisors: bool,
    supervisor_salaries: List[float],
    lock_overheads: bool,
    employment_support: str,
    benefits_on: bool,
    benefits_pc: float,
) -> Tuple[float, float, float, float, float, float]:
    """
    Returns:
      (monthly_instructor, monthly_overheads, dev_base, dev_discount, dev_revised, benefits_reduction)
    """
    alloc = _recommended_allocation(workshop_hours, max(1, contracts))
    wk_costs = [(s / 52.0) for s in supervisor_salaries] if supervisor_salaries else []
    if lock_overheads and wk_costs:
        base_weekly_inst = max(wk_costs)
    else:
        base_weekly_inst = sum(wk_costs)

    eff_weekly_inst = base_weekly_inst * alloc

    if customer_covers_supervisors:
        monthly_instructor = 0.0
        # shadow base for overheads uses highest salary at allocation
        shadow_weekly = (max(wk_costs) if wk_costs else 0.0) * alloc
        overhead_base_weekly = shadow_weekly
    else:
        monthly_instructor = _m_from_w(eff_weekly_inst)
        overhead_base_weekly = eff_weekly_inst

    monthly_overheads = _m_from_w(overhead_base_weekly * 0.61)

    # Development: first compute base at 20% of (instr+overheads)
    dev_base = _r2((monthly_instructor + monthly_overheads) * _base_dev_rate())
    # Revised rate by support:
    revised_rate = _support_dev_rate(employment_support)
    dev_revised = _r2((monthly_instructor + monthly_overheads) * revised_rate)
    dev_discount = _r2(dev_base - dev_revised)

    # Benefits (after revised development):
    if employment_support == "Both" and benefits_on:
        benefits_base = monthly_instructor + monthly_overheads + dev_revised
        benefits_reduction = _r2(-abs(benefits_base * (benefits_pc / 100.0)))
    else:
        benefits_reduction = 0.0

    return (
        _r2(monthly_instructor),
        _r2(monthly_overheads),
        dev_base,
        dev_discount,
        dev_revised,
        benefits_reduction,
    )

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

    # Monthly prisoner wages
    monthly_wages = _m_from_w(float(num_prisoners) * float(prisoner_salary))

    (
        monthly_instructor,
        monthly_overheads,
        dev_base,
        dev_discount,
        dev_revised,
        benefits_reduction,
    ) = _compute_common_costs(
        workshop_hours=workshop_hours,
        contracts=contracts,
        customer_covers_supervisors=customer_covers_supervisors,
        supervisor_salaries=supervisor_salaries,
        lock_overheads=lock_overheads,
        employment_support=employment_support,
        benefits_on=benefits_checkbox,
        benefits_pc=benefits_discount_pc,
    )

    subtotal = _r2(
        monthly_wages
        + monthly_instructor
        + monthly_overheads
        + dev_revised
        + benefits_reduction
    )
    vat = _r2(subtotal * 0.20)
    grand_ex = subtotal
    grand_inc = _r2(subtotal + vat)

    rows = []
    rows.append({"Item": "Prisoner Wages", "Amount (£)": _r2(monthly_wages)})
    if monthly_instructor != 0:
        rows.append({"Item": "Instructor Cost", "Amount (£)": _r2(monthly_instructor)})
    rows.append({"Item": "Overheads", "Amount (£)": _r2(monthly_overheads)})
    rows.append({"Item": "Development charge (20% of Instructor+Overheads)", "Amount (£)": dev_base})
    if dev_discount != 0:
        rows.append({"Item": "Development discount", "Amount (£)": _r2(-abs(dev_discount))})
    rows.append({"Item": "Revised development", "Amount (£)": dev_revised})
    if benefits_reduction != 0:
        rows.append({"Item": "Additional benefits reduction", "Amount (£)": benefits_reduction})

    rows.append({"Item": "Subtotal (ex VAT)", "Amount (£)": subtotal})
    rows.append({"Item": "VAT (20%)", "Amount (£)": vat})
    rows.append({"Item": "Grand Total (ex VAT)", "Amount (£)": grand_ex})
    rows.append({"Item": "Grand Total (inc VAT)", "Amount (£)": grand_inc})

    df = pd.DataFrame(rows)

    ctx = HostContext(
        monthly_wages=_r2(monthly_wages),
        monthly_instructor=monthly_instructor,
        monthly_overheads=monthly_overheads,
        monthly_dev_base=dev_base,
        monthly_dev_discount=dev_discount,
        monthly_dev_revised=dev_revised,
        monthly_benefits_reduction=benefits_reduction,
        monthly_subtotal_ex_vat=subtotal,
        monthly_vat=vat,
        monthly_grand_total_ex_vat=grand_ex,
        monthly_grand_total_inc_vat=grand_inc,
    )
    return df, ctx