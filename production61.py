from typing import List, Dict, Optional
from datetime import date, timedelta
import math

def labour_minutes_budget(num_pris: int, hours: float) -> float:
    return max(0.0, float(num_pris) * float(hours) * 60.0)

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
    num_prisoners: int,
    num_supervisors: int,
    dev_rate: float,
    lock_overheads: bool,
    region: str,
    pricing_mode: str = "as-is",
    targets: Optional[List[int]] = None,
) -> List[Dict]:
    # Instructor costs
    if not customer_covers_supervisors:
        inst_weekly_total = sum((s / 52.0) * (float(effective_pct) / 100.0) for s in supervisor_salaries)
    else:
        inst_weekly_total = 0.0

    # Overheads = 61%
    if customer_covers_supervisors:
        shadow = {
            "Inner London": 49202.70,
            "Outer London": 45855.97,
            "National": 42247.81,
        }
        overheads_weekly = (shadow[region] * 0.61) / 52.0
    else:
        if lock_overheads:
            max_salary = max(supervisor_salaries) if supervisor_salaries else 0
            overheads_weekly = (max_salary * 0.61) / 52.0
        else:
            overheads_weekly = inst_weekly_total * 0.61

    # Development charge (applies except Public)
    dev_weekly_total = (overheads_weekly * float(dev_rate)) if customer_type != "Public" else 0.0

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
        inst_weekly_item = inst_weekly_total * share
        overheads_weekly_item = overheads_weekly * share
        dev_weekly_item = dev_weekly_total * share
        weekly_cost_item = prisoner_weekly_item + inst_weekly_item + overheads_weekly_item + dev_weekly_item

        if pricing_mode == "target":
            tgt = 0
            if targets and idx < len(targets):
                try: tgt = int(targets[idx])
                except Exception: tgt = 0
            units_for_pricing = float(tgt)
        else:
            units_for_pricing = capacity_units

        unit_cost_ex_vat = (weekly_cost_item / units_for_pricing) if units_for_pricing > 0 else None
        unit_price_ex_vat = unit_cost_ex_vat
        unit_price_inc_vat = (
            unit_price_ex_vat * (1 + (float(vat_rate) / 100.0))
            if unit_price_ex_vat is not None and customer_type == "Commercial" and apply_vat
            else unit_price_ex_vat
        )

        monthly_total = (
            (units_for_pricing * unit_price_ex_vat * 52.0 / 12.0) if unit_price_ex_vat is not None else None
        )

        results.append({
            "Item": name,
            "Capacity (units/week)": int(round(capacity_units)) if capacity_units > 0 else 0,
            "Units/week": int(round(units_for_pricing)) if units_for_pricing > 0 else 0,
            "Unit Cost (£)": unit_cost_ex_vat,
            "Unit Price ex VAT (£)": unit_price_ex_vat,
            "Unit Price inc VAT (£)": unit_price_inc_vat,
            "Monthly Total (£)": monthly_total,
        })
    return results