# host61.py
from __future__ import annotations
import pandas as pd

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
    supervisor_salaries: list[float],
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
    The additional 10% benefits reduction applies **only** if Employment Support = "Both".
    """

    alloc = _instructor_allocation(workshop_hours, contracts)

    # Prisoner wages (monthly)
    pris_wages_m = float(num_prisoners) * float(prisoner_salary) * 52.0 / 12.0

    # Determine base annual for overheads (shadow even if customer provides)
    if supervisor_salaries:
        base_annual = max(supervisor_salaries) if lock_overheads else sum(supervisor_salaries)
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

    # Apply benefits reduction ONLY when ES == "Both"
    benefits_applicable = benefits_yes and (employment_support.strip().lower() == "both")
    ben_pc = (float(benefits_discount_pc) / 100.0) if benefits_applicable else 0.0

    # Single combined reduction over (inst + overheads + dev_before)
    combined_base = inst_m + overheads_m + dev_before_m
    ben_combined = -combined_base * ben_pc

    # Revised Dev is dev_before less the portion of the combined reduction that relates to dev_before
    # i.e., reduce dev by (dev_before * ben_pc)
    dev_revised_m = dev_before_m * (1 - ben_pc)

    # Subtotal ex VAT
    subtotal_ex_vat = pris_wages_m + inst_m + overheads_m + dev_revised_m + (ben_combined if benefits_applicable else 0.0)
    vat = subtotal_ex_vat * (VAT_RATE_PC / 100.0)
    grand_ex = subtotal_ex_vat
    grand_inc = subtotal_ex_vat + vat

    # ORDER: Dev first, then Benefits Reduction (if applicable), then Revised Dev, then totals
    rows = [
        {"Item": "Prisoner Wages", "Amount (£)": pris_wages_m},
        {"Item": "Instructor Salary", "Amount (£)": inst_m},
        {"Item": "Overheads", "Amount (£)": overheads_m},
        {"Item": "Development Charge", "Amount (£)": dev_before_m},
    ]
    if benefits_applicable and ben_combined != 0:
        rows.append({"Item": "Additional benefits reduction (10%)", "Amount (£)": ben_combined})
    rows.append({"Item": "Revised Development Charge", "Amount (£)": dev_revised_m})
    rows.append({"Item": "Grand Total (ex VAT)", "Amount (£)": grand_ex})
    rows.append({"Item": f"VAT ({int(VAT_RATE_PC)}%)", "Amount (£)": vat})
    rows.append({"Item": "Grand Total (inc VAT)", "Amount (£)": grand_inc})

    return pd.DataFrame(rows), {
        "alloc": alloc,
        "prisoner_wages_m": pris_wages_m,
        "instructor_m": inst_m,
        "overheads_m": overheads_m,
        "dev_rate": dev_rate,
        "dev_before_m": dev_before_m,
        "benefits": {
            "applicable": benefits_applicable,
            "pc": ben_pc,
            "combined": ben_combined,
        },
        "dev_revised_m": dev_revised_m,
        "grand_ex": grand_ex, "vat": vat, "grand_inc": grand_inc,
    }