from typing import List, Dict, Tuple, Optional
from datetime import date, timedelta
import math
import pandas as pd
from tariff61 import BAND3_COSTS

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
    region: str,
    customer_type: str,
    apply_vat: bool,
    vat_rate: float,
    num_prisoners: int,
    num_supervisors: int,
    dev_rate: float,
    pricing_mode: str = "as-is",
    targets: Optional[List[int]] = None,
    lock_overheads: bool = False,
    employment_support: str = "None",
) -> List[Dict]:
    # Prisoner wages weekly
    prisoner_weekly = num_prisoners * prisoner_salary

    # Instructor salary weekly
    if not customer_covers_supervisors:
        inst_weekly_total = sum((s / 52.0) * (effective_pct / 100.0) for s in supervisor_salaries)
    else:
        inst_weekly_total = 0.0

    # Overheads base
    if customer_covers_supervisors:
        shadow = BAND3_COSTS.get(region, BAND3_COSTS["National"])
        overhead_base = (shadow / 52.0) * (effective_pct / 100.0)
    else:
        overhead_base = inst_weekly_total

    if lock_overheads and supervisor_salaries:
        overhead_base = (max(supervisor_salaries) / 52.0) * (effective_pct / 100.0)

    overheads_weekly = overhead_base * 0.61

    # Development charge logic (always 20%)
    full_dev_charge = overheads_weekly * 0.20

    reduction_val = 0.0
    if employment_support == "Employment on release/RoTL":
        reduction_val = -abs(overheads_weekly * 0.10)
    elif employment_support == "Post release":
        reduction_val = -abs(overheads_weekly * 0.10)
    elif employment_support == "Both":
        reduction_val = -abs(overheads_weekly * 0.20)

    revised_dev_charge = full_dev_charge + reduction_val

    # Totals (weekly)
    base_weekly_total = prisoner_weekly + inst_weekly_total + overheads_weekly
    total_weekly = base_weekly_total + revised_dev_charge

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
        dev_weekly_item       = revised_dev_charge * share
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

        # Costs
        unit_cost_ex_vat = (weekly_cost_item / units_for_pricing) if units_for_pricing > 0 else None
        unit_price_ex_vat = unit_cost_ex_vat
        if unit_price_ex_vat is not None and (customer_type == "Commercial" and apply_vat):
            unit_price_inc_vat = unit_price_ex_vat * (1 + (vat_rate / 100.0))
        else:
            unit_price_inc_vat = unit_price_ex_vat

        monthly_total_ex_vat = (units_for_pricing * unit_cost_ex_vat * 52 / 12) if unit_cost_ex_vat else None
        monthly_total_inc_vat = (units_for_pricing * unit_price_inc_vat * 52 / 12) if unit_price_inc_vat else None

        results.append({
            "Item": name,
            "Output %": int(output_pct),
            "Capacity (units/week)": 0 if capacity_units <= 0 else int(round(capacity_units)),
            "Units/week": 0 if units_for_pricing <= 0 else int(round(units_for_pricing)),
            "Unit Cost (£)": unit_cost_ex_vat,
            "Unit Price ex VAT (£)": unit_price_ex_vat,
            "Unit Price inc VAT (£)": unit_price_inc_vat,
            "Monthly Total ex VAT (£)": monthly_total_ex_vat,
            "Monthly Total inc VAT (£)": monthly_total_inc_vat,
            "Feasible": feasible if pricing_mode == "target" else None,
            "Note": note,
            "Prisoner Wages": prisoner_weekly_item,
            "Instructor Salary": inst_weekly_item,
            "Overheads (61%)": overheads_weekly_item,
            "Development Charge": full_dev_charge * share,
            "Development Charge Reduction (Support Applied)": reduction_val * share if reduction_val != 0 else 0.0,
            "Revised Development Charge": dev_weekly_item,
        })
    return results

# ---------- Ad-hoc ----------
def _working_days_between(start: date, end: date) -> int:
    if end < start: return 0
    days, d = 0, start
    while d <= end:
        if d.weekday() < 5: days += 1
        d += timedelta(days=1)
    return days

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
    region: str,
    customer_type: str,
    apply_vat: bool,
    vat_rate: float,
    dev_rate: float,
    today: date,
    lock_overheads: bool = False,
    employment_support: str = "None",
) -> Dict:
    output_scale = float(output_pct) / 100.0
    hours_per_day = float(workshop_hours) / 5.0
    daily_minutes_capacity_per_prisoner = hours_per_day * 60.0 * output_scale
    current_daily_capacity = num_prisoners * daily_minutes_capacity_per_prisoner
    minutes_per_week_capacity = max(1e-9, num_prisoners * workshop_hours * 60.0 * output_scale)

    # Prisoner wages weekly
    prisoner_weekly = num_prisoners * prisoner_salary

    # Instructor salary weekly
    if not customer_covers_supervisors:
        inst_weekly_total = sum((s / 52.0) * (effective_pct / 100.0) for s in supervisor_salaries)
    else:
        inst_weekly_total = 0.0

    # Overheads base
    if customer_covers_supervisors:
        shadow = BAND3_COSTS.get(region, BAND3_COSTS["National"])
        overhead_base = (shadow / 52.0) * (effective_pct / 100.0)
    else:
        overhead_base = inst_weekly_total

    if lock_overheads and supervisor_salaries:
        overhead_base = (max(supervisor_salaries) / 52.0) * (effective_pct / 100.0)

    overheads_weekly = overhead_base * 0.61

    # Development charge logic (always 20%)
    full_dev_charge = overheads_weekly * 0.20

    reduction_val = 0.0
    if employment_support == "Employment on release/RoTL":
        reduction_val = -abs(overheads_weekly * 0.10)
    elif employment_support == "Post release":
        reduction_val = -abs(overheads_weekly * 0.10)
    elif employment_support == "Both":
        reduction_val = -abs(overheads_weekly * 0.20)

    revised_dev_charge = full_dev_charge + reduction_val

    weekly_cost_total = prisoner_weekly + inst_weekly_total + overheads_weekly + revised_dev_charge
    cost_per_minute = weekly_cost_total / minutes_per_week_capacity

    per_line, total_job_minutes, earliest_wd_available = [], 0.0, None
    for ln in lines:
        mins_per_unit = float(ln["mins_per_item"]) * int(ln["pris_per_item"])
        unit_cost_ex_vat = cost_per_minute * mins_per_unit
        if customer_type == "Commercial" and apply_vat:
            unit_cost_inc_vat = unit_cost_ex_vat * (1 + (vat_rate / 100.0))
        else:
            unit_cost_inc_vat = unit_cost_ex_vat

        total_line_minutes = int(ln["units"]) * mins_per_unit
        total_job_minutes += total_line_minutes
        wd_available = _working_days_between(today, ln["deadline"])
        if earliest_wd_available is None or wd_available < earliest_wd_available:
            earliest_wd_available = wd_available
        wd_needed_line_alone = math.ceil(total_line_minutes / current_daily_capacity) if current_daily_capacity > 0 else float("inf")

        per_line.append({
            "Item": ln["name"],
            "Units": int(ln["units"]),
            "Unit Cost (ex VAT £)": unit_cost_ex_vat,
            "Unit Cost (inc VAT £)": unit_cost_inc_vat,
            "Line Total (ex VAT £)": unit_cost_ex_vat * int(ln["units"]),
            "Line Total (inc VAT £)": unit_cost_inc_vat * int(ln["units"]),
            "Prisoner Wages": prisoner_weekly,
            "Instructor Salary": inst_weekly_total,
            "Overheads (61%)": overheads_weekly,
            "Development Charge": full_dev_charge,
            "Development Charge Reduction (Support Applied)": reduction_val if reduction_val != 0 else 0.0,
            "Revised Development Charge": revised_dev_charge,
            "wd_available": wd_available,
            "wd_needed_line_alone": wd_needed_line_alone,
        })

    wd_needed_all = math.ceil(total_job_minutes / current_daily_capacity) if current_daily_capacity > 0 else float("inf")
    earliest_wd_available = earliest_wd_available or 0
    available_total_minutes_by_deadline = current_daily_capacity * earliest_wd_available
    hard_block = total_job_minutes > available_total_minutes_by_deadline
    reason = None
    if hard_block:
        reason = (
            f"Requested total minutes ({total_job_minutes:,.0f}) exceed available minutes by the earliest deadline "
            f"({available_total_minutes_by_deadline:,.0f}). Reduce units, add prisoners, increase hours, extend deadline or lower Output%."
        )

    totals_ex = sum(p["Line Total (ex VAT £)"] for p in per_line)
    totals_inc = sum(p["Line Total (inc VAT £)"] for p in per_line)

    return {
        "per_line": per_line,
        "totals": {"ex_vat": totals_ex, "inc_vat": totals_inc},
        "capacity": {"current_daily_capacity": current_daily_capacity, "minutes_per_week_capacity": minutes_per_week_capacity},
        "feasibility": {"earliest_wd_available": earliest_wd_available, "wd_needed_all": wd_needed_all, "hard_block": hard_block, "reason": reason},
    }