# production61.py
# Production costing using instructor salaries + 61% overheads (no utilities)
from typing import List, Dict, Optional
from datetime import date, timedelta
import math
import streamlit as st
from config61 import CFG
from tariff61 import BAND3_SHADOW_COSTS

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
    customer_covers_supervisors: bool,
    customer_type: str,
    apply_vat: bool,
    vat_rate: float,
    num_prisoners: int,
    num_supervisors: int,
    lock_overheads: bool,
    region: str,
    pricing_mode: str = "as-is",
    targets: Optional[List[int]] = None,
) -> List[Dict]:
    # Instructor costs
    if not customer_covers_supervisors:
        inst_weekly_total = sum((s / 52.0) for s in supervisor_salaries)
    else:
        band3_salary = BAND3_SHADOW_COSTS.get(region, 0.0)
        inst_weekly_total = 0.0
        shadow_weekly = band3_salary / 52.0
    # Overheads
    if lock_overheads and supervisor_salaries:
        highest_cost = max(supervisor_salaries)
        overheads_weekly = (highest_cost * 0.61) / 52.0
    else:
        ref_cost = (sum(supervisor_salaries) if supervisor_salaries else BAND3_SHADOW_COSTS.get(region, 0.0))
        overheads_weekly = (ref_cost * 0.61) / 52.0

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
        weekly_cost_item = prisoner_weekly_item + inst_weekly_item + overheads_weekly_item

        # Add shadow cost if customer provides instructor
        if customer_covers_supervisors:
            weekly_cost_item += shadow_weekly * share

        if pricing_mode == "target":
            tgt = 0
            if targets and idx < len(targets):
                try:
                    tgt = int(targets[idx])
                except Exception:
                    tgt = 0
            units_for_pricing = float(tgt)
        else:
            units_for_pricing = capacity_units

        available_minutes_item = pris_assigned * workshop_hours * 60.0 * output_scale
        required_minutes_item = units_for_pricing * mins_per_unit * pris_required
        feasible = (required_minutes_item <= (available_minutes_item + 1e-6))
        note = None
        if pricing_mode == "target" and not feasible:
            note = (f"Target requires {required_minutes_item:,.0f} mins vs "
                    f"available {available_minutes_item:,.0f} mins; exceeds capacity.")

        unit_cost_ex_vat = (weekly_cost_item / units_for_pricing) if units_for_pricing > 0 else None
        unit_price_ex_vat = unit_cost_ex_vat
        unit_price_inc_vat = unit_price_ex_vat * (1 + (float(vat_rate) / 100.0)) if unit_price_ex_vat else None

        results.append({
            "Item": name,
            "Output %": int(output_pct),
            "Capacity (units/week)": 0 if capacity_units <= 0 else int(round(capacity_units)),
            "Units/week": 0 if units_for_pricing <= 0 else int(round(units_for_pricing)),
            "Unit Cost (£)": unit_cost_ex_vat,
            "Unit Price ex VAT (£)": unit_price_ex_vat,
            "Unit Price inc VAT (£)": unit_price_inc_vat,
            "Feasible": feasible if pricing_mode == "target" else None,
            "Note": note,
        })
    return results

# ---------- Ad-hoc ----------
def _working_days_between(start: date, end: date) -> int:
    if end < start:
        return 0
    days, d = 0, start
    while d <= end:
        if d.weekday() < 5:
            days += 1
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
    customer_covers_supervisors: bool,
    customer_type: str,
    apply_vat: bool,
    vat_rate: float,
    lock_overheads: bool,
    region: str,
    today: date,
) -> Dict:
    output_scale = float(output_pct) / 100.0
    hours_per_day = float(workshop_hours) / 5.0
    daily_minutes_capacity_per_prisoner = hours_per_day * 60.0 * output_scale
    current_daily_capacity = num_prisoners * daily_minutes_capacity_per_prisoner
    minutes_per_week_capacity = max(1e-9, num_prisoners * workshop_hours * 60.0 * output_scale)

    # Instructor costs
    if not customer_covers_supervisors:
        inst_weekly_total = sum((s / 52.0) for s in supervisor_salaries)
    else:
        band3_salary = BAND3_SHADOW_COSTS.get(region, 0.0)
        inst_weekly_total = 0.0
        shadow_weekly = band3_salary / 52.0

    # Overheads
    if lock_overheads and supervisor_salaries:
        highest_cost = max(supervisor_salaries)
        overheads_weekly = (highest_cost * 0.61) / 52.0
    else:
        ref_cost = (sum(supervisor_salaries) if supervisor_salaries else BAND3_SHADOW_COSTS.get(region, 0.0))
        overheads_weekly = (ref_cost * 0.61) / 52.0

    prisoners_weekly_cost = num_prisoners * prisoner_salary
    weekly_cost_total = prisoners_weekly_cost + inst_weekly_total + overheads_weekly
    if customer_covers_supervisors:
        weekly_cost_total += shadow_weekly

    cost_per_minute = weekly_cost_total / minutes_per_week_capacity
    per_line, total_job_minutes, earliest_wd_available = [], 0.0, None

    for ln in lines:
        mins_per_unit = float(ln["mins_per_item"]) * int(ln["pris_per_item"])
        unit_cost_ex_vat = cost_per_minute * mins_per_unit
        unit_cost_inc_vat = unit_cost_ex_vat * (1 + (float(vat_rate) / 100.0)) if customer_type == "Commercial" and apply_vat else unit_cost_ex_vat
        total_line_minutes = int(ln["units"]) * mins_per_unit
        total_job_minutes += total_line_minutes

        wd_available = _working_days_between(today, ln["deadline"])
        if earliest_wd_available is None or wd_available < earliest_wd_available:
            earliest_wd_available = wd_available
        wd_needed_line_alone = math.ceil(total_line_minutes / current_daily_capacity) if current_daily_capacity > 0 else float("inf")

        per_line.append({
            "name": ln["name"],
            "units": int(ln["units"]),
            "unit_cost_ex_vat": unit_cost_ex_vat,
            "unit_cost_inc_vat": unit_cost_inc_vat,
            "line_total_ex_vat": unit_cost_ex_vat * int(ln["units"]),
            "line_total_inc_vat": unit_cost_inc_vat * int(ln["units"]),
            "wd_available": wd_available,
            "wd_needed_line_alone": wd_needed_line_alone,
        })

    wd_needed_all = math.ceil(total_job_minutes / current_daily_capacity) if current_daily_capacity > 0 else float("inf")
    earliest_wd_available = earliest_wd_available or 0
    available_total_minutes_by_deadline = current_daily_capacity * earliest_wd_available
    hard_block = total_job_minutes > available_total_minutes_by_deadline
    reason = None
    if hard_block:
        reason = (f"Requested total minutes ({total_job_minutes:,.0f}) exceed available minutes "
                  f"({available_total_minutes_by_deadline:,.0f}) by earliest deadline.")

    totals_ex = sum(p["line_total_ex_vat"] for p in per_line)
    totals_inc = sum(p["line_total_inc_vat"] for p in per_line)

    return {
        "per_line": per_line,
        "totals": {"ex_vat": totals_ex, "inc_vat": totals_inc},
        "capacity": {"current_daily_capacity": current_daily_capacity, "minutes_per_week_capacity": minutes_per_week_capacity},
        "feasibility": {"earliest_wd_available": earliest_wd_available, "wd_needed_all": wd_needed_all, "hard_block": hard_block, "reason": reason},
    }