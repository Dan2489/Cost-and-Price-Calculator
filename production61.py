from typing import List, Dict, Optional
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
    lock_overheads: bool,
    region: str,
    dev_rate: float,
    pricing_mode: str = "as-is",
    targets: Optional[List[int]] = None,
) -> List[Dict]:
    output_scale = float(output_pct) / 100.0
    denom = sum(int(it.get("assigned", 0)) * workshop_hours * 60.0 for it in items)

    # Instructor weekly cost
    instructor_weekly = 0.0
    if not customer_covers_supervisors:
        instructor_weekly = sum((s / 52.0) * (effective_pct / 100.0) for s in supervisor_salaries)

    # Shadow cost for overheads
    shadow_band3 = 42248.0
    shadow_weekly = (shadow_band3 / 52.0) * (effective_pct / 100.0)

    if customer_covers_supervisors:
        base_for_overheads = shadow_weekly
    else:
        if lock_overheads and supervisor_salaries:
            highest = max(supervisor_salaries)
            base_for_overheads = (highest / 52.0) * (effective_pct / 100.0)
        else:
            base_for_overheads = instructor_weekly

    overheads_weekly = base_for_overheads * 0.61
    dev_weekly_total = (overheads_weekly * dev_rate) if customer_type == "Commercial" else 0.0

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
        inst_weekly_item      = instructor_weekly * share
        overheads_weekly_item = overheads_weekly * share
        dev_weekly_item       = dev_weekly_total * share
        weekly_cost_item      = prisoner_weekly_item + inst_weekly_item + overheads_weekly_item + dev_weekly_item

        if pricing_mode == "target":
            tgt = targets[idx] if targets and idx < len(targets) else 0
            units_for_pricing = float(tgt)
        else:
            units_for_pricing = capacity_units

        available_minutes_item = pris_assigned * workshop_hours * 60.0 * output_scale
        required_minutes_item  = units_for_pricing * mins_per_unit * pris_required
        feasible = (required_minutes_item <= (available_minutes_item + 1e-6))
        note = None
        if pricing_mode == "target" and not feasible:
            note = f"Target requires {required_minutes_item:,.0f} mins vs available {available_minutes_item:,.0f} mins."

        unit_cost_ex_vat = (weekly_cost_item / units_for_pricing) if units_for_pricing > 0 else None
        unit_price_ex_vat = unit_cost_ex_vat
        if unit_price_ex_vat is not None and apply_vat:
            unit_price_inc_vat = unit_price_ex_vat * (1 + (vat_rate / 100.0))
        else:
            unit_price_inc_vat = unit_price_ex_vat

        results.append({
            "Item": name,
            "Output %": int(output_pct),
            "Capacity (units/week)": int(round(capacity_units)) if capacity_units > 0 else 0,
            "Units/week": int(round(units_for_pricing)) if units_for_pricing > 0 else 0,
            "Unit Cost (£)": unit_cost_ex_vat,
            "Unit Price ex VAT (£)": unit_price_ex_vat,
            "Unit Price inc VAT (£)": unit_price_inc_vat,
            "Feasible": feasible if pricing_mode == "target" else None,
            "Note": note,
        })
    return results


def calculate_adhoc(
    lines: List[Dict],
    output_pct: int,
    *,
    workshop_hours: float,
    num_prisoners: int,
    prisoner_salary: float,
    supervisor_salaries: List[float],
    effective_pct: float,
    customer_covers_supervisors: bool,
    customer_type: str,
    apply_vat: bool,
    vat_rate: float,
    region: str,
    lock_overheads: bool,
    dev_rate: float,
) -> Dict:
    output_scale = float(output_pct) / 100.0
    hours_per_day = workshop_hours / 5.0
    daily_minutes_capacity_per_prisoner = hours_per_day * 60.0 * output_scale
    current_daily_capacity = num_prisoners * daily_minutes_capacity_per_prisoner
    minutes_per_week_capacity = max(1e-9, num_prisoners * workshop_hours * 60.0 * output_scale)

    # Instructor weekly cost
    instructor_weekly = 0.0
    if not customer_covers_supervisors:
        instructor_weekly = sum((s / 52.0) * (effective_pct / 100.0) for s in supervisor_salaries)

    # Shadow cost
    shadow_band3 = 42248.0
    shadow_weekly = (shadow_band3 / 52.0) * (effective_pct / 100.0)
    if customer_covers_supervisors:
        base_for_overheads = shadow_weekly
    else:
        if lock_overheads and supervisor_salaries:
            highest = max(supervisor_salaries)
            base_for_overheads = (highest / 52.0) * (effective_pct / 100.0)
        else:
            base_for_overheads = instructor_weekly

    overheads_weekly = base_for_overheads * 0.61
    dev_weekly_total = (overheads_weekly * dev_rate) if customer_type == "Commercial" else 0.0

    prisoners_weekly_cost = num_prisoners * prisoner_salary
    weekly_cost_total = prisoners_weekly_cost + instructor_weekly + overheads_weekly + dev_weekly_total
    cost_per_minute = weekly_cost_total / minutes_per_week_capacity

    per_line, totals_ex, totals_inc = [], 0.0, 0.0
    for ln in lines:
        mins_per_unit = float(ln["mins_per_item"]) * int(ln["pris_per_item"])
        unit_cost_ex_vat = cost_per_minute * mins_per_unit
        unit_cost_inc_vat = unit_cost_ex_vat * (1 + (vat_rate / 100.0)) if apply_vat else unit_cost_ex_vat
        totals_ex += unit_cost_ex_vat * int(ln["units"])
        totals_inc += unit_cost_inc_vat * int(ln["units"])
        per_line.append({
            "name": ln["name"],
            "units": int(ln["units"]),
            "unit_cost_ex_vat": unit_cost_ex_vat,
            "unit_cost_inc_vat": unit_cost_inc_vat,
        })

    return {"per_line": per_line, "totals": {"ex_vat": totals_ex, "inc_vat": totals_inc}}