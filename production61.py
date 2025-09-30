# production61.py
# Contractual & Ad-hoc production using instructor-only model
# - Instructor wage adjusted by % allocation
# - Overheads = 61% of the same adjusted wage
# - If customer provides instructor: wage=0; overheads=61% of Band3 (adjusted by %)
# - Unit price (weekly) + Monthly totals (units/week × 52/12)
from typing import List, Dict, Optional
from datetime import date, timedelta
import math

from utils61 import BAND3_SHADOW_SALARY

WEEKS_PER_MONTH = 52.0 / 12.0

# ---------- Helper ----------
def labour_minutes_budget(num_pris: int, hours: float) -> float:
    return max(0.0, float(num_pris) * float(hours) * 60.0)

def _weekly_instructor_and_overheads(
    supervisor_salaries: List[float],
    effective_pct: float,
    customer_covers_supervisors: bool,
    region: str,
    lock_overheads: bool,
):
    pct = float(effective_pct) / 100.0
    # Instructor wage (weekly)
    if customer_covers_supervisors:
        inst_weekly = 0.0
    else:
        inst_weekly = sum((s / 52.0) * pct for s in supervisor_salaries)
    # Overheads base (weekly)
    if customer_covers_supervisors:
        base_overheads_w = (BAND3_SHADOW_SALARY.get(region, 0.0) / 52.0) * pct
    else:
        if lock_overheads and supervisor_salaries:
            base_overheads_w = (max(supervisor_salaries) / 52.0) * pct
        else:
            base_overheads_w = sum((s / 52.0) * pct for s in supervisor_salaries)
    overheads_weekly = 0.61 * base_overheads_w
    return inst_weekly, overheads_weekly

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
    num_prisoners: int,
    num_supervisors: int,
    lock_overheads: bool,
    region: str,
    dev_rate: float = 0.0,
    pricing_mode: str = "as-is",
    targets: Optional[List[int]] = None,
) -> List[Dict]:
    inst_weekly_total, overheads_weekly = _weekly_instructor_and_overheads(
        supervisor_salaries, effective_pct, customer_covers_supervisors, region, lock_overheads
    )
    dev_weekly_total = overheads_weekly * (float(dev_rate) if customer_type == "Commercial" else 0.0)

    denom = sum(int(it.get("assigned", 0)) * workshop_hours * 60.0 for it in items)
    output_scale = float(output_pct) / 100.0

    results: List[Dict] = []
    for idx, it in enumerate(items):
        name = (it.get("name") or "").strip() or f"Item {idx+1}"
        mins_per_unit = float(it.get("minutes", 0.0))
        pris_required = int(it.get("required", 1))
        pris_assigned = int(it.get("assigned", 0))

        # Capacity (weekly)
        if pris_assigned > 0 and mins_per_unit > 0 and pris_required > 0 and workshop_hours > 0:
            cap_100 = (pris_assigned * workshop_hours * 60.0) / (mins_per_unit * pris_required)
        else:
            cap_100 = 0.0
        capacity_units_w = cap_100 * output_scale

        # Share of minutes
        share = ((pris_assigned * workshop_hours * 60.0) / denom) if denom > 0 else 0.0

        # Cost per item (weekly share)
        prisoners_weekly_item = pris_assigned * prisoner_salary
        inst_weekly_item      = inst_weekly_total * share
        overheads_weekly_item = overheads_weekly * share
        dev_weekly_item       = dev_weekly_total * share
        weekly_cost_item      = prisoners_weekly_item + inst_weekly_item + overheads_weekly_item + dev_weekly_item

        # Units to price on
        if pricing_mode == "target":
            tgt = 0
            if targets and idx < len(targets):
                try: tgt = int(targets[idx])
                except Exception: tgt = 0
            units_w = float(tgt)
        else:
            units_w = capacity_units_w

        # Feasibility
        available_minutes_item = pris_assigned * workshop_hours * 60.0 * output_scale
        required_minutes_item  = units_w * mins_per_unit * pris_required
        feasible = (required_minutes_item <= (available_minutes_item + 1e-6))
        note = None
        if pricing_mode == "target" and not feasible:
            note = f"Target requires {required_minutes_item:,.0f} mins vs available {available_minutes_item:,.0f} mins; exceeds capacity."

        # Pricing
        unit_cost_ex_vat   = (weekly_cost_item / units_w) if units_w > 0 else None
        unit_price_ex_vat  = unit_cost_ex_vat
        unit_price_inc_vat = (unit_price_ex_vat * (1 + (float(vat_rate) / 100.0))) if (apply_vat and unit_price_ex_vat is not None) else unit_price_ex_vat

        # Monthly totals
        monthly_units          = units_w * WEEKS_PER_MONTH
        monthly_total_ex_vat   = (unit_price_ex_vat * monthly_units) if unit_price_ex_vat is not None else None
        monthly_total_inc_vat  = (unit_price_inc_vat * monthly_units) if unit_price_inc_vat is not None else None

        results.append({
            "Item": name,
            "Output %": int(output_pct),
            "Capacity (units/week)": 0 if capacity_units_w <= 0 else int(round(capacity_units_w)),
            "Units/week": 0 if units_w <= 0 else int(round(units_w)),
            "Unit Cost (£)": unit_cost_ex_vat,
            "Unit Price ex VAT (£)": unit_price_ex_vat,
            "Unit Price inc VAT (£)": unit_price_inc_vat,
            "Monthly Total ex VAT (£)": monthly_total_ex_vat,
            "Monthly Total inc VAT (£)": monthly_total_inc_vat,
            "Feasible": feasible if pricing_mode == "target" else None,
            "Note": note,
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
    customer_type: str,
    apply_vat: bool,
    vat_rate: float,
    lock_overheads: bool,
    region: str,
    today: date,
    dev_rate: float = 0.0,
) -> Dict:
    output_scale = float(output_pct) / 100.0
    hours_per_day = float(workshop_hours) / 5.0
    daily_minutes_capacity_per_prisoner = hours_per_day * 60.0 * output_scale
    current_daily_capacity = num_prisoners * daily_minutes_capacity_per_prisoner
    minutes_per_week_capacity = max(1e-9, num_prisoners * workshop_hours * 60.0 * output_scale)

    inst_weekly_total, overheads_weekly = _weekly_instructor_and_overheads(
        supervisor_salaries, effective_pct, customer_covers_supervisors, region, lock_overheads
    )
    dev_weekly_total = overheads_weekly * (float(dev_rate) if customer_type == "Commercial" else 0.0)

    prisoners_weekly_cost = num_prisoners * prisoner_salary
    weekly_cost_total = prisoners_weekly_cost + inst_weekly_total + overheads_weekly + dev_weekly_total
    cost_per_minute = weekly_cost_total / minutes_per_week_capacity

    per_line, total_job_minutes, earliest_wd_available = [], 0.0, None
    for ln in lines:
        mins_per_unit = float(ln["mins_per_item"]) * int(ln["pris_per_item"])
        unit_cost_ex_vat = cost_per_minute * mins_per_unit
        unit_cost_inc_vat = unit_cost_ex_vat * (1 + (float(vat_rate) / 100.0)) if (customer_type == "Commercial" and apply_vat) else unit_cost_ex_vat

        total_line_minutes = int(ln["units"]) * mins_per_unit
        total_job_minutes += total_line_minutes

        wd_available = _working_days_between(today, ln["deadline"])
        if earliest_wd_available is None or wd_available < earliest_wd_available:
            earliest_wd_available = wd_available
        wd_needed_line_alone = math.ceil(total_line_minutes / current_daily_capacity) if current_daily_capacity > 0 else float("inf")

        per_line.append({
            "name": ln["name"],
            "