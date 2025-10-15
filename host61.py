# host61.py
from __future__ import annotations
import pandas as pd
from utils61 import fmt_currency

VAT_RATE_PC = 20.0

def _dev_rate_from_support(s: str) -> float:
    s = (s or "").strip().lower()
    if s == "none":
        return 0.20
    if s in ("employment on release/rotl", "post release"):
        return 0.10
    return 0.00  # "Both"

def _instructor_allocation(workshop_hours: float, contracts: int) -> float:
    try:
        base = (float(workshop_hours) / 37.5) / max(1, int(contracts))
        return max(0.0, min(1.0, base))
    except Exception:
        return 0.0

def _monthly_from_annual(annual: float, alloc: float) -> float:
    return float(annual) * float(alloc) / 12.0

def generate_host_quote(
    *,
    workshop_hours: float,
    num_prisoners: int,
    prisoner_salary: float,
    num_supervisors: int,
    customer_covers_supervisors: bool,
    supervisor_salaries: list[float],   # annual totals per selected title
    region: str,
    contracts: int,
    employment_support: str,
    lock_overheads: bool,
    benefits_yes: bool,
    benefits_desc: str | None,
    benefits_discount_pc: float = 10.0,
):
    """
    Returns (df, ctx) where df is the breakdown table and ctx the raw numbers.
    """
    alloc = _instructor_allocation(workshop_hours, contracts)

    # Prisoner wages (monthly)
    pris_wages_m = float(num_prisoners) * float(prisoner_salary) * 52.0 / 12.0

    # Determine base annual for overheads (shadow even if customer provides)
    if supervisor_salaries:
        if lock_overheads:
            base_annual = max(supervisor_salaries)
        else:
            base_annual = sum(supervisor_salaries)
    else:
        base_annual = 0.0

    # Instructor monthly (zero if customer provides)
    inst_m = 0.0 if customer_covers_supervisors else _monthly_from_annual(base_annual, alloc)

    # Overheads monthly (shadow)
    over_base_m = _monthly_from_annual(base_annual, alloc)
    overheads_m = over_base_m * 0.61

    # Development charge (before any benefits discount)
    dev_rate = _dev_rate_from_support(employment_support)
    dev_before_m = overheads_m * dev_rate

    # Benefits reductions
    ben_pc = (float(benefits_discount_pc) / 100.0) if benefits_yes else 0.0
    ben_inst = inst_m * ben_pc * (-1)
    ben_over = overheads_m * ben_pc * (-1)
    ben_dev  = dev_before_m * ben_pc * (-1)

    dev_revised_m = dev_before_m + ben_dev  # after benefit reduction

    # Totals
    subtotal_ex_vat = pris_wages_m + (inst_m + ben_inst) + (overheads_m + ben_over) + dev_revised_m
    vat = subtotal_ex_vat * (VAT_RATE_PC / 100.0)
    grand_ex = subtotal_ex_vat
    grand_inc = subtotal_ex_vat + vat

    rows = [
        {"Item": "Prisoner Wages", "Amount (£)": pris_wages_m},
        {"Item": "Instructor Salary", "Amount (£)": inst_m},
    ]
    if benefits_yes and ben_inst != 0:
        rows.append({"Item": "Additional benefits reduction – Instructor (10%)", "Amount (£)": ben_inst})
    rows.append({"Item": "Overheads", "Amount (£)": overheads_m})
    if benefits_yes and ben_over != 0:
        rows.append({"Item": "Additional benefits reduction – Overheads (10%)", "Amount (£)": ben_over})
    rows.append({"Item": "Development Charge", "Amount (£)": dev_before_m})
    if benefits_yes and ben_dev != 0:
        rows.append({"Item": "Additional benefits reduction – Development (10%)", "Amount (£)": ben_dev})
    rows.append({"Item": "Revised Development Charge", "Amount (£)": dev_revised_m})
    rows.append({"Item": "Grand Total (ex VAT)", "Amount (£)": grand_ex})
    rows.append({"Item": f"VAT ({int(VAT_RATE_PC)}%)", "Amount (£)": vat})
    rows.append({"Item": "Grand Total (inc VAT)", "Amount (£)": grand_inc})

    df = pd.DataFrame(rows)

    ctx = {
        "alloc": alloc,
        "prisoner_wages_m": pris_wages_m,
        "instructor_m": inst_m,
        "overheads_m": overheads_m,
        "dev_rate": dev_rate,
        "dev_before_m": dev_before_m,
        "benefits": {
            "yes": benefits_yes,
            "pc": ben_pc,
            "inst": ben_inst,
            "over": ben_over,
            "dev": ben_dev,
        },
        "dev_revised_m": dev_revised_m,
        "grand_ex": grand_ex,
        "vat": vat,
        "grand_inc": grand_inc,
    }
    return df, ctx