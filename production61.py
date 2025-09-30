from typing import List, Dict, Optional
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
    apply_vat: bool,
    vat_rate: float,
    area_m2: float,
    usage_key: str,
    num_prisoners: int,
    num_supervisors: int,
    dev_rate: float,
    lock_overheads: bool,
    pricing_mode: str = "as-is",
    targets: Optional[List[int]] = None,
) -> List[Dict]:
    # Instructor wages
    inst_weekly_total = (
        sum((s / 52.0) * (float(effective_pct) / 100.0) for s in supervisor_salaries)
        if not customer_covers_supervisors else 0.0
    )

    # Overheads = 61% of instructor salaries
    if lock_overheads and supervisor_salaries:
        highest = max(supervisor_salaries)
        overheads_weekly = (highest / 52.0) * 0.61
    else:
        overheads_weekly = inst_weekly_total * 0.61

    # Development charge (applies only to Commercial)
    dev_weekly_total = 0.0
    if customer_type == "Commercial":
        dev_weekly_total = overheads_weekly * float(dev_rate)

    denom = sum(int(it.get("assigned", 0)) * workshop_hours * 60.0 for it in items)
    output_scale = float(output_pct) / 100.0

    results: List[Dict] = []
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
        dev_weekly_item       = dev_weekly_total * share
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
        unit_price_ex_vat = unit_cost_ex_vat
        if unit_price_ex_vat is not None and apply_vat:
            unit_price_inc_vat = unit_price_ex_vat * (1 + (float(vat_rate) / 100.0))
        else:
            unit_price_inc_vat = unit_price_ex_vat

        # Monthly totals
        monthly_total = None
        if units_for_pricing > 0 and unit_cost_ex_vat:
            monthly_total = units_for_pricing * unit_cost_ex_vat * (52.0 / 12.0)

        results.append({
            "Item": name,
            "Output %": int(output_pct),
            "Pricing mode": "Target units/week" if pricing_mode == "target" else "As-is (max units)",
            "Capacity (units/week)": 0 if capacity_units <= 0 else int(round(capacity_units)),
            "Units/week": 0 if units_for_pricing <= 0 else int(round(units_for_pricing)),
            "Unit Cost (£)": unit_cost_ex_vat,
            "Unit Price ex VAT (£)": unit_price_ex_vat,
            "Unit Price inc VAT (£)": unit_price_inc_vat,
            "Monthly Total (£)": monthly_total,
            "Feasible": feasible if pricing_mode == "target" else None,
            "Note": note,
        })

    # Grand total row (only for display)
    grand_total = sum(r["Monthly Total (£)"] or 0 for r in results)
    results.append({
        "Item": "Grand Total",
        "Output %": None,
        "Pricing mode": None,
        "Capacity (units/week)": None,
        "Units/week": None,
        "Unit Cost (£)": None,
        "Unit Price ex VAT (£)": None,
        "Unit Price inc VAT (£)": None,
        "Monthly Total (£)": grand_total,
        "Feasible": None,
        "Note": None,
    })

    return results