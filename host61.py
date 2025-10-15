# host61.py
from __future__ import annotations

import pandas as pd

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _dev_rate_from_support(s: str) -> float:
    """
    Map Employment Support choice to development percentage
    (as used elsewhere in the app).
    """
    if s == "None":
        return 0.20
    if s in ("Employment on release/RoTL", "Post release"):
        return 0.10
    return 0.00


def _fmt(val: float) -> float:
    try:
        return float(val)
    except Exception:
        return 0.0


def _money(x: float) -> float:
    """Round to 2dp for stable downstream CSV/HTML rendering."""
    return round(float(x), 2)


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

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
    instructor_allocation: float = 100.0,  # kept for backward-compatibility; not used if auto = True
    lock_overheads: bool = False,

    # NEW – centralized “additional prison benefits” hook
    apply_benefits: bool = False,
    benefits_desc: str = "",
    benefits_discount_pc: float = 0.10,  # 10% by default
    auto_instructor_allocation: bool = True,  # use workshop_hours/contracts (your current behaviour)
):
    """
    Build the Host quote table. Returns (df, context).

    Behaviour:
    - Instructor salary base is derived from selected instructor titles.
    - Effective allocation %:
        * If auto_instructor_allocation = True:
              pct = min(100, (workshop_hours / 37.5) * (1/contracts) * 100)
          else:
              pct = instructor_allocation
    - If apply_benefits, discount% is applied to instructor salary BEFORE overheads/dev.
    - Overheads are 61% of the (possibly discounted) weekly instructor base used as ‘shadow cost’.
      Shadow rule when customer provides instructors:
          instructor salary line = 0, but overhead base may still come from titles if lock_overheads=True:
              overhead_base_weekly = (max(salaries)/52) * pct
          otherwise 0.
    - Development is a percentage of Overheads (dev_rate from employment_support).
    - Table rows created only for non-zero amounts (except Subtotal/VAT/Grand Total).
    """

    # ---------- Effective instructor allocation ----------
    pct_auto = 0.0
    try:
        if workshop_hours > 0 and contracts > 0:
            pct_auto = (workshop_hours / 37.5) * (1.0 / max(1, contracts)) * 100.0
    except Exception:
        pct_auto = 0.0
    pct_auto = max(0.0, min(100.0, pct_auto))
    eff_pct = pct_auto if auto_instructor_allocation else float(instructor_allocation or 0.0)
    eff_pct = max(0.0, min(100.0, eff_pct))

    # ---------- Weekly instructor base ----------
    # Base weekly from chosen titles (sum) unless locked overheads require max.
    sum_weekly = sum((_fmt(s) / 52.0) for s in (supervisor_salaries or []))
    max_weekly = max([_fmt(s) for s in (supervisor_salaries or [0.0])]) / 52.0 if supervisor_salaries else 0.0

    # Instructor salary (weekly) that we actually CHARGE:
    inst_weekly_charge = sum_weekly * (eff_pct / 100.0) if not customer_covers_supervisors else 0.0

    # Apply benefits discount to instructor charge (before overheads/dev calcs)
    if apply_benefits and inst_weekly_charge > 0:
        inst_weekly_charge *= (1.0 - float(benefits_discount_pc or 0.0))

    # The base to use for overheads ("shadow"):
    if customer_covers_supervisors:
        # if “lock_overheads”, still build shadow from the highest title
        overhead_base_weekly = max_weekly * (eff_pct / 100.0) if lock_overheads and supervisor_salaries else 0.0
    else:
        # if locked, overheads can be based on highest; else use actual sum
        base_weekly = max_weekly if (lock_overheads and supervisor_salaries) else sum_weekly
        # IMPORTANT: benefits discount affects only the instructor salary we charge,
        # but overheads should also be based on the discounted base (as per your rule).
        base_weekly *= (eff_pct / 100.0)
        if apply_benefits and base_weekly > 0:
            base_weekly *= (1.0 - float(benefits_discount_pc or 0.0))
        overhead_base_weekly = base_weekly

    # ---------- Overheads & Development ----------
    overheads_weekly = overhead_base_weekly * 0.61
    dev_rate = _dev_rate_from_support(employment_support)
    dev_weekly_before_reduction = overheads_weekly * dev_rate

    # Prisoner wages (weekly)
    prisoner_wages_weekly = _fmt(num_prisoners) * _fmt(prisoner_salary)

    # ---------- Totals (monthly) ----------
    inst_monthly = inst_weekly_charge * 52.0 / 12.0
    overheads_monthly = overheads_weekly * 52.0 / 12.0
    dev_monthly_before = dev_weekly_before_reduction * 52.0 / 12.0
    prisoner_monthly = prisoner_wages_weekly * 52.0 / 12.0

    # Development reduction (only when benefits are ON and dev > 0):
    dev_reduction_monthly = 0.0
    if apply_benefits and dev_monthly_before > 0.0:
        dev_reduction_monthly = dev_monthly_before * float(benefits_discount_pc or 0.0)

    dev_monthly_after = max(0.0, dev_monthly_before - dev_reduction_monthly)

    # Subtotal ex VAT (host has no “unit-level” rows)
    subtotal_ex_vat = prisoner_monthly + inst_monthly + overheads_monthly + dev_monthly_after
    vat = subtotal_ex_vat * 0.20
    grand_ex_vat = subtotal_ex_vat
    grand_inc_vat = subtotal_ex_vat + vat

    # ---------- Build rows (suppress 0 lines except totals) ----------
    rows = []

    if prisoner_monthly != 0:
        rows.append({"Item": "Prisoner Wages", "Amount (£)": _money(prisoner_monthly)})

    if inst_monthly != 0:
        rows.append({"Item": "Instructor Salary", "Amount (£)": _money(inst_monthly)})

    if overheads_monthly != 0:
        rows.append({"Item": "Overheads", "Amount (£)": _money(overheads_monthly)})

    if dev_monthly_before != 0:
        rows.append({"Item": "Development charge", "Amount (£)": _money(dev_monthly_before)})

    if dev_reduction_monthly > 0:
        rows.append({"Item": "Development discount (benefits)", "Amount (£)": _money(-dev_reduction_monthly)})

    if dev_monthly_after != 0 and dev_monthly_after != dev_monthly_before:
        rows.append({"Item": "Revised development charge", "Amount (£)": _money(dev_monthly_after)})

    # Always include totals
    rows.append({"Item": "Subtotal (ex VAT)", "Amount (£)": _money(subtotal_ex_vat)})
    rows.append({"Item": "VAT (20%)", "Amount (£)": _money(vat)})
    rows.append({"Item": "Grand Total (ex VAT)", "Amount (£)": _money(grand_ex_vat)})
    rows.append({"Item": "Grand Total (inc VAT)", "Amount (£)": _money(grand_inc_vat)})

    df = pd.DataFrame(rows)

    # Context for CSV or HTML header blocks
    ctx = {
        "effective_instructor_pct": eff_pct,
        "apply_benefits": bool(apply_benefits),
        "benefits_desc": benefits_desc or "",
        "benefits_discount_pc": float(benefits_discount_pc or 0.0),
        "dev_rate": dev_rate,
    }
    return df, ctx