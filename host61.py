# host61.py
# Host monthly breakdown using instructor-only model:
# - Prisoner wages (monthly)
# - Instructors (monthly) unless customer provides
# - Overheads = 61% of base instructor cost (see lock rule)
# - Dev charge applies to overheads only (Commercial); VAT always 20% (handled by caller)
from typing import List, Dict, Tuple
import pandas as pd
import streamlit as st
from config61 import CFG
from utils61 import BAND3_SHADOW_SALARY

def _overheads_monthly(
    supervisor_salaries: List[float],
    customer_covers_supervisors: bool,
    region: str,
    lock_overheads: bool
) -> float:
    """Compute monthly overheads = 61% of base annual instructor salary (÷12).
    Base = max(selected) if lock_overheads, else sum(selected).
    If customer provides, base = Band 3 salary for region.
    """
    if customer_covers_supervisors:
        base = BAND3_SHADOW_SALARY.get(region, 0.0)
    else:
        if lock_overheads and supervisor_salaries:
            base = max(supervisor_salaries)
        else:
            base = sum(supervisor_salaries)
    return (base * 0.61) / 12.0

def _instructors_monthly(
    supervisor_salaries: List[float],
    effective_pct: float,
    customer_covers_supervisors: bool
) -> float:
    if customer_covers_supervisors:
        # Salary is removed when customer provides instructor(s).
        return 0.0
    pct = float(effective_pct) / 100.0
    return sum((s * pct) / 12.0 for s in supervisor_salaries)

def generate_host_quote(
    *,
    workshop_hours: float,  # kept for signature compatibility
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
    lock_overheads: bool
) -> Tuple[pd.DataFrame, Dict]:
    breakdown: Dict[str, float] = {}

    # Prisoner wages (monthly)
    breakdown["Prisoner wages"] = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)

    # Instructors (monthly) with effective % unless customer provides
    instructors_m = _instructors_monthly(supervisor_salaries, effective_pct, customer_covers_supervisors)
    if customer_covers_supervisors:
        breakdown["Instructor salary (removed; customer provides)"] = 0.0
        breakdown["Shadow Band 3 (base for overheads)"] = BAND3_SHADOW_SALARY.get(region, 0.0) / 12.0
    breakdown["Instructors"] = instructors_m

    # Overheads (61% base)
    overheads_m = _overheads_monthly(supervisor_salaries, customer_covers_supervisors, region, lock_overheads)
    breakdown["Overheads (61%)"] = overheads_m

    # Dev charge (Commercial only) — applied to overheads only
    dev_m = overheads_m * (float(st.session_state.get("dev_rate", 0.0)) if customer_type == "Commercial" else 0.0)
    # `dev_rate` is set in newapp61.py into session for consistency with original UX
    breakdown["Development charge (applied)"] = dev_m

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