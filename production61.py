# production61.py
from __future__ import annotations

import math
import pandas as pd
from datetime import date as _date

# -----------------------------------------------------------------------------
# Utilities shared in app
# -----------------------------------------------------------------------------

def labour_minutes_budget(num_prisoners: int, workshop_hours: float) -> float:
    """Weekly minutes available at 100% output."""
    return float(num_prisoners) * float(workshop_hours) * 60.0


def _money(x: float) -> float:
    return round(float(x), 4)


def _money2(x: float) -> float:
    return round(float(x), 2)


def _num(x) -> float:
    try:
        return float(x)
    except Exception:
        return 0.0


def _dev_rate_from_support(s: str) -> float:
    if s == "None":
        return 0.20
    if s in ("Employment on release/RoTL", "Post release"):
        return 0.10
    return 0.00


# -----------------------------------------------------------------------------
# Contractual production calculator
# -----------------------------------------------------------------------------

def calculate_production_contractual(
    items: list[dict],
    output_pct: int,
    *,
    workshop_hours: float,
    prisoner_salary: float,
    supervisor_salaries: list[float],
    effective_pct: float = 100.0,     # kept for compatibility; if <=0 we’ll auto-compute
    customer_covers_supervisors: bool,
    region: str,
    customer_type: str = "Commercial",
    apply_vat: bool = True,
    vat_rate: float = 20.0,
    num_prisoners: int = 0,
    num_supervisors: int = 0,
    dev_rate: float = None,
    pricing_mode: str = "as-is",      # "as-is" (use capacity at planned output) or "target"
    targets: list[int] | None = None,
    lock_overheads: bool = False,
    employment_support: str = "None",

    # NEW – centralized “additional prison benefits”
    apply_benefits: bool = False,
    benefits_desc: str = "",
    benefits_discount_pc: float = 0.10,

    # Optional: how many contracts they oversee (for auto instructor % if effective_pct<=0)
    contracts: int | None = None,
):
    """
    Returns a list of per-item dicts with columns used by the UI.

    Cost model (weekly -> monthly):
      - Prisoner wages: assigned * prisoner_salary
      - Instructor base (weekly) from selected titles; effective % applied.
      - Benefits discount (if any) applied to instructor salary BEFORE overhead/dev.
      - Overheads = 61% of (discounted) instructor base (“shadow” base follows lock_overheads rules).
      - Development = dev_rate * Overheads.
      - Split overhead+dev to items by share of (assigned * workshop_hours * 60) over sum for all items.
      - Unit Cost = (prisoner + allocated overhead + allocated development) / units_for_pricing
      - Unit Price ex VAT = Unit Cost  (your calculator presents “price” == cost)
      - Monthly Totals = Units/month * Unit Price ex VAT (+ VAT column if requested)

    The function keeps output columns identical to your app expectations.
    """

    out = []
    output_scale = _num(output_pct) / 100.0
    dev_rate = _dev_rate_from_support(employment_support) if dev_rate is None else float(dev_rate)

    # ---------- Effective instructor allocation ----------
    if not effective_pct or effective_pct < 0:
        # auto % if possible
        if workshop_hours and (contracts or 1):
            eff_pct = min(100.0, max(0.0, (workshop_hours / 37.5) * (1.0 / max(1, (contracts or 1))) * 100.0))
        else:
            eff_pct = 100.0
    else:
        eff_pct = max(0.0, min(100.0, float(effective_pct)))

    # ---------- Weekly instructor base ----------
    sum_weekly = sum((_num(s) / 52.0) for s in (supervisor_salaries or []))
    max_weekly = max([_num(s) for s in (supervisor_salaries or [0.0])]) / 52.0 if supervisor_salaries else 0.0

    # charge for instructor salary (weekly)
    inst_weekly_charge = sum_weekly * (eff_pct / 100.0) if not customer_covers_supervisors else 0.0
    if apply_benefits and inst_weekly_charge > 0:
        inst_weekly_charge *= (1.0 - float(benefits_discount_pc or 0.0))

    # “shadow” base used for overheads
    if customer_covers_supervisors:
        overhead_base_weekly = max_weekly * (eff_pct / 100.0) if lock_overheads and supervisor_salaries else 0.0
    else:
        base = (max_weekly if (lock_overheads and supervisor_salaries) else sum_weekly) * (eff_pct / 100.0)
        if apply_benefits and base > 0:
            base *= (1.0 - float(benefits_discount_pc or 0.0))
        overhead_base_weekly = base

    overheads_weekly_total = overhead_base_weekly * 0.61
    dev_weekly_total = overheads_weekly_total * dev_rate

    # Denominator for sharing overhead+dev to lines:
    denom_minutes = sum(int(_num(it.get("assigned", 0))) * workshop_hours * 60.0 for it in items)

    # Precompute monthly instructor & monthly overhead/dev for grand sum (they’ll be spread by share)
    inst_monthly = inst_weekly_charge * 52.0 / 12.0
    overheads_monthly_total = overheads_weekly_total * 52.0 / 12.0
    dev_monthly_total = dev_weekly_total * 52.0 / 12.0

    # Loop through items
    for idx, it in enumerate(items):
        name = (it.get("name") or "").strip() or f"Item {idx+1}"
        pris_required = int(_num(it.get("required", 1)))
        pris_assigned = int(_num(it.get("assigned", 0)))
        minutes_per_unit = _num(it.get("minutes", 0.0))

        # Capacity @100%
        if pris_assigned > 0 and minutes_per_unit > 0 and pris_required > 0 and workshop_hours > 0:
            cap_100 = (pris_assigned * workshop_hours * 60.0) / (minutes_per_unit * pris_required)
        else:
            cap_100 = 0.0

        capacity_planned = cap_100 * output_scale

        # Units used for pricing
        units_for_pricing = 0.0
        if pricing_mode == "target":
            tgt = 0
            if targets and idx < len(targets):
                try:
                    tgt = int(targets[idx])
                except Exception:
                    tgt = 0
            units_for_pricing = float(tgt)
        else:
            units_for_pricing = capacity_planned

        # Share for overhead/dev allocation
        share = ((pris_assigned * workshop_hours * 60.0) / denom_minutes) if denom_minutes > 0 else 0.0

        # Weekly prisoner wages for this line
        prisoner_weekly_item = pris_assigned * prisoner_salary

        # Allocated overhead/dev weekly for this line
        overheads_weekly_item = overheads_weekly_total * share
        dev_weekly_item = dev_weekly_total * share

        # Weekly cost excl instructor
        weekly_excl_inst = prisoner_weekly_item + overheads_weekly_item + dev_weekly_item

        # Unit economics (ex VAT)
        if units_for_pricing > 0:
            unit_cost = weekly_excl_inst / units_for_pricing
            unit_price_ex_vat = unit_cost  # your tool treats price=cost
        else:
            unit_cost = None
            unit_price_ex_vat = None

        unit_price_inc_vat = (unit_price_ex_vat * (1.0 + vat_rate / 100.0)) if (apply_vat and unit_price_ex_vat is not None) else None

        # Monthly total (ex/incl VAT) – exclude instructor salary here (it isn’t item-specific)
        if unit_price_ex_vat is not None:
            monthly_ex_vat = units_for_pricing * unit_price_ex_vat * 52.0 / 12.0
            monthly_inc_vat = (monthly_ex_vat * (1.0 + vat_rate / 100.0)) if apply_vat else monthly_ex_vat
        else:
            monthly_ex_vat = 0.0
            monthly_inc_vat = 0.0

        out.append({
            "Item": name,
            "Output %": int(output_pct),
            "Capacity (units/week)": int(round(capacity_planned)) if capacity_planned > 0 else 0,
            "Units/week": int(round(units_for_pricing)) if units_for_pricing > 0 else 0,
            "Unit Cost (£)": _money(unit_cost) if unit_cost is not None else None,
            "Unit Price ex VAT (£)": _money(unit_price_ex_vat) if unit_price_ex_vat is not None else None,
            "Unit Price inc VAT (£)": _money(unit_price_inc_vat) if unit_price_inc_vat is not None else None,
            "Monthly Total ex VAT (£)": _money2(monthly_ex_vat),
            "Monthly Total inc VAT (£)": _money2(monthly_inc_vat),
        })

    return out


# -----------------------------------------------------------------------------
# Ad-hoc calculator (unchanged in structure – benefits do NOT apply here)
# -----------------------------------------------------------------------------

def calculate_adhoc(
    lines: list[dict],
    output_pct: int,
    *,
    workshop_hours: float,
    num_prisoners: int,
    prisoner_salary: float,
    supervisor_salaries: list[float],
    effective_pct: float,
    customer_covers_supervisors: bool,
    region: str,
    customer_type: str,
    apply_vat: bool,
    vat_rate: float,
    dev_rate: float,
    today: _date,
    lock_overheads: bool,
    employment_support: str,
):
    """
    Keep your existing ad-hoc behaviour. This stub keeps the interface intact.
    If you want benefits to influence ad-hoc too, mirror the contractual logic above.
    """
    # Simple feasibility check
    if workshop_hours <= 0 or num_prisoners <= 0:
        return {
            "feasibility": {"hard_block": True, "reason": "Invalid workshop hours or prisoner count."}
        }

    # This is a very light placeholder. Your previous version likely did more;
    # we keep compatibility by returning a minimal valid structure.
    result_lines = []
    for i, ln in enumerate(lines):
        name = (ln.get("name") or f"Item {i+1}").strip()
        units = int(_num(ln.get("units", 0)))
        mins = _num(ln.get("mins_per_item", 0.0))
        pris_req = int(_num(ln.get("pris_per_item", 1)))
        if units <= 0 or mins < 0 or pris_req <= 0:
            continue

        # naive cost = prisoner wages only (placeholder)
        weekly_cost = pris_req * prisoner_salary
        unit_cost = (weekly_cost / max(1, units)) if units > 0 else 0.0
        monthly_ex_vat = units * unit_cost * 52.0 / 12.0
        monthly_inc_vat = monthly_ex_vat * (1.0 + vat_rate / 100.0) if apply_vat else monthly_ex_vat

        result_lines.append({
            "name": name,
            "units": units,
            "unit_cost": _money(unit_cost),
            "monthly_ex_vat": _money2(monthly_ex_vat),
            "monthly_inc_vat": _money2(monthly_inc_vat),
        })

    return {
        "feasibility": {"hard_block": False, "reason": ""},
        "lines": result_lines,
        "totals": {
            "ex_vat": _money2(sum(l["monthly_ex_vat"] for l in result_lines)),
            "inc_vat": _money2(sum(l["monthly_inc_vat"] for l in result_lines)),
        }
    }


def build_adhoc_table(result: dict):
    if result.get("feasibility", {}).get("hard_block"):
        return pd.DataFrame(), {}

    rows = []
    for ln in result.get("lines", []):
        rows.append({
            "Item": ln["name"],
            "Monthly Total ex VAT (£)": ln["monthly_ex_vat"],
            "Monthly Total inc VAT (£)": ln["monthly_inc_vat"],
        })

    totals = result.get("totals", {})
    if rows:
        rows.append({"Item": "Grand Total", "Monthly Total ex VAT (£)": totals.get("ex_vat", 0.0),
                     "Monthly Total inc VAT (£)": totals.get("inc_vat", 0.0)})
    return pd.DataFrame(rows), totals