from typing import List, Dict, Tuple, Optional
from datetime import date, timedelta
import math

from config61 import CFG

# ---------- Helpers ----------
def labour_minutes_budget(num_pris: int, hours: float) -> float:
    return max(0.0, float(num_pris) * float(hours) * 60.0)

# ---------- Contractual ----------
def calculate_production_contractual(
    items: List[Dict],
    output_pct: int,
    *,
    workshop_hours: float,
    prisoner_salary: float,
    supervisor_salaries: List[float],
    effective_pct: float,
    customer_covers_supervisors: bool,
    customer_type: str,
    support: str,           # <-- NEW for dev charge reductions
    apply_vat: bool,
    vat_rate: float,
    num_prisoners: int,
    num_supervisors: int,
    lock_overheads: bool,   # <-- NEW from sidebar
    dev_rate: float,        # kept for compatibility, but ignored (we use breakdown)
    pricing_mode: str = "as-is",
    targets: Optional[List[int]] = None,
) -> Tuple[List[Dict], Dict]:
    """
    Production cost calculator (contractual).
    - Overheads = 61% of instructor costs (or Band 3 shadow if customer provides).
    - Development charge shown as base, reductions, applied.
    """

    # Instructor costs (weekly)
    inst_weekly_total = 0.0
    if not customer_covers_supervisors and supervisor_salaries:
        if lock_overheads:
            # Use highest salary only for overheads
            inst_weekly_total = (max(supervisor_salaries) / 52.0) * (float(effective_pct) / 100.0)
        else:
            inst_weekly_total = sum((s / 52.0) * (float(effective_pct) / 100.0) for s in supervisor_salaries)

    # Overheads = 61% of instructor cost
    overheads_weekly = inst_weekly_total * 0.61

    # Development charge breakdown
    dev_base = overheads_weekly * 0.20
    dev_reduction = 0.0
    if customer_type == "Commercial":
        if support in ("Employment on release/RoTL", "Post release"):
            dev_reduction = -overheads_weekly * 0.10
        elif support == "Both":
            dev_reduction = -overheads_weekly * 0.20
    dev_applied = dev_base + dev_reduction

    # Denominator for share
    denom = sum(int(it.get("assigned", 0)) * workshop_hours * 60.0 for it in items)
    output_scale = float(output_pct) / 100.0

    results: List[Dict] = []
    grand_monthly_total = 0.0

    for idx, it in enumerate(items):
        name = (it.get("name") or "").strip() or f"Item {idx+1}"
        mins_per_unit = float(it.get("minutes", 0))
        pris_required = int(it.get("required", 1))
        pris_assigned = int(it.get("assigned", 0))

        if pris_assigned > 0 and mins_per_unit > 0 and pris_required > 0 and workshop_hours > 0:
            cap_100 = (pris_assigned * workshop_hours * 60.0) / (mins_per_unit * pris_required)
        else:
            cap_100 = 0.0
        capacity_units = cap_100 * output_scale

        share = ((pris_assigned * workshop_hours * 60.0) / denom) if denom > 0 else 0.0

        prisoner_weekly_item = pris_assigned * prisoner_salary
        inst_weekly_item      = inst_weekly_total * share
        overheads_weekly_item = overheads_weekly * share
        dev_weekly_item       = dev_applied * share
        weekly_cost_item      = prisoner_weekly_item + inst_weekly_item + overheads_weekly_item + dev_weekly_item

        if pricing_mode == "target":
            tgt = 0
            if targets and idx < len(targets):
                try: tgt = int(targets[idx])
                except Exception: tgt = 0
            units_for_pricing = float(tgt)
        else:
            units_for_pricing = capacity_units

        available_minutes_item = pris_assigned * workshop_hours * 60.0 * output_scale
        required_minutes_item  = units_for_pricing * mins_per_unit * pris_required
        feasible = (required_minutes_item <= (available_minutes_item + 1e-6))
        note = None
        if pricing_mode == "target" and not feasible:
            note = (
                f"Target requires {required_minutes_item:,.0f} mins vs "
                f"available {available_minutes_item:,.0f} mins; exceeds capacity."
            )

        unit_cost_ex_vat = (weekly_cost_item / units_for_pricing) if units_for_pricing > 0 else None
        monthly_total = (units_for_pricing * (unit_cost_ex_vat or 0.0)) * (52.0 / 12.0)

        unit_price_ex_vat = unit_cost_ex_vat
        unit_price_inc_vat = None
        if unit_price_ex_vat is not None:
            if customer_type == "Commercial" and apply_vat:
                unit_price_inc_vat = unit_price_ex_vat * (1 + (float(vat_rate) / 100.0))
            else:
                unit_price_inc_vat = unit_price_ex_vat

        grand_monthly_total += monthly_total

        results.append({
            "Item": name,
            "Output %": int(output_pct),
            "Capacity (units/week)": 0 if capacity_units <= 0 else int(round(capacity_units)),
            "Units/week": 0 if units_for_pricing <= 0 else int(round(units_for_pricing)),
            "Unit Cost (£)": unit_cost_ex_vat,
            "Unit Price ex VAT (£)": unit_price_ex_vat,
            "Unit Price inc VAT (£)": unit_price_inc_vat,
            "Monthly Total (£)": monthly_total,
            "Feasible": feasible if pricing_mode == "target" else None,
            "Note": note,
        })

    ctx = {
        "overheads_weekly": overheads_weekly,
        "dev_base": dev_base,
        "dev_reduction": dev_reduction,
        "dev_applied": dev_applied,
        "grand_monthly_total": grand_monthly_total,
    }

    return results, ctx