# production61.py
# Production model (Contractual + Ad-hoc) using instructor-only overheads:
# - Instructor salary (removed if customer provides; still use Band3 for overhead base)
# - Overheads = 61% of instructor base (sum or highest if locked)
# - Prisoner wages included
# - Dev charge (Commercial) applied to overheads only
# - Unit cost and Unit price; plus Monthly totals (Units/week × 52/12)
from typing import List, Dict, Optional
from datetime import date, timedelta
import math
import streamlit as st
from config61 import CFG
from utils61 import BAND3_SHADOW_SALARY

WEEKS_PER_MONTH = 52.0 / 12.0

# ---------- Helpers ----------
def labour_minutes_budget(num_pris: int, hours: float) -> float:
    return max(0.0, float(num_pris) * float(hours) * 60.0)

def _overheads_weekly(supervisor_salaries: List[float], customer_covers_supervisors: bool, region: str, lock_overheads: bool) -> float:
    if customer_covers_supervisors:
        base = BAND3_SHADOW_SALARY.get(region, 0.0)
    else:
        if lock_overheads and supervisor_salaries:
            base = max(supervisor_salaries)
        else:
            base = sum(supervisor_salaries)
    return (base * 0.61) / 52.0

def _instructors_weekly(supervisor_salaries: List[float], effective_pct: float, customer_covers_supervisors: bool) -> float:
    if customer_covers_supervisors:
        return 0.0
    pct = float(effective_pct) / 100.0
    return sum((s * pct) / 52.0 for s in supervisor_salaries)

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
    inst_weekly_total = _instructors_weekly(supervisor_salaries, effective_pct, customer_covers_supervisors)
    overheads_weekly = _overheads_weekly(supervisor_salaries, customer_covers_supervisors, region, lock_overheads)
    dev_weekly_total = overheads_weekly * (float(dev_rate) if customer_type == "Commercial" else 0.0)

    denom = sum(int(it.get("assigned", 0)) * workshop_hours * 60.0 for it in items)
    output_scale = float(output_pct) / 100.0

    results: List[Dict] = []
    for idx, it in enumerate(items):
        name = (it.get("name") or "").strip() or f"Item {idx+1}"
        mins_per_unit = float(it.get("minutes", 0.0))
        pris_required = int(it.get("required", 1))
        pris_assigned = int(it.get("assigned", 0))

        # Capacity
        if pris_assigned > 0 and mins_per_unit > 0 and pris_required > 0 and workshop_hours > 0:
            cap_100 = (pris_assigned * workshop_hours * 60.0) / (mins_per_unit * pris_required)
        else:
            cap_100 = 0.0
        capacity_units_week = cap_100 * output_scale

        # Share of minutes
        share = ((pris_assigned * workshop_hours * 60.0) / denom) if denom > 0 else 0.0

        # Cost components (weekly, per item share)
        prisoners_weekly_item = pris_assigned * prisoner_salary
        inst_weekly_item = inst_weekly_total * share
        overheads_weekly_item = overheads_weekly * share
        dev_weekly_item = dev_weekly_total * share
        weekly_cost_item = prisoners_weekly_item + inst_weekly_item + overheads_weekly_item + dev_weekly_item

        # Units for pricing
        if pricing_mode == "target":
            tgt = 0
            if targets and idx < len(targets):
                try:
                    tgt = int(targets[idx])
                except Exception:
                    tgt = 0
            units_week = float(tgt)
        else:
            units_week = capacity_units_week

        # Feasibility (minutes check)
        available_minutes_item = pris_assigned * workshop_hours * 60.0 * output_scale
        required_minutes_item = units_week * mins_per_unit * pris_required
        feasible = (required_minutes_item <= (available_minutes_item + 1e-6))
        note = None
        if pricing_mode == "target" and not feasible:
            note = (
                f"Target requires {required_minutes_item:,.0f} mins vs "
                f"available {available_minutes_item:,.0f} mins; exceeds capacity."
            )

        # Unit cost/price (weekly basis)
        unit_cost_ex_vat = (weekly_cost_item / units_week) if units_week > 0 else None
        unit_price_ex_vat = unit_cost_ex_vat
        unit_price_inc_vat = (unit_price_ex_vat * (1 + (float(vat_rate) / 100.0))) if (apply_vat and unit_price_ex_vat is not None) else unit_price_ex_vat

        # Monthly totals
        monthly_units = units_week * WEEKS_PER_MONTH
        monthly_total_ex_vat = (unit_price_ex_vat * monthly_units) if unit_price_ex_vat is not None else None
        monthly_total_inc_vat = (unit_price_inc_vat * monthly_units) if unit_price_inc_vat is not None else None

        results.append({
            "Item": name,
            "Output %": int(output_pct),
            "Capacity (units/week)": 0 if capacity_units_week <= 0 else int(round(capacity_units_week)),
            "Units/week": 0 if units_week <= 0 else int(round(units_week)),
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

    inst_weekly_total = _instructors_weekly(supervisor_salaries, effective_pct, customer_covers_supervisors)
    overheads_weekly = _overheads_weekly(supervisor_salaries, customer_covers_supervisors, region, lock_overheads)
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

        # Monthly totals for ad-hoc line (units are one-off; show monthly cost = line_total × (1/4.333)?)
        # For ad-hoc (job), we just show line totals; monthly roll-up isn't typical. Keeping line totals only.
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
        reason = (
            f"Requested total minutes ({total_job_minutes:,.0f}) exceed available minutes by the earliest deadline "
            f"({available_total_minutes_by_deadline:,.0f}). Reduce units, add prisoners, increase hours, extend deadline or lower Output%."
        )

    totals_ex = sum(p["line_total_ex_vat"] for p in per_line)
    totals_inc = sum(p["line_total_inc_vat"] for p in per_line)

    return {
        "per_line": per_line,
        "totals": {"ex_vat": totals_ex, "inc_vat": totals_inc},
        "capacity": {"current_daily_capacity": current_daily_capacity, "minutes_per_week_capacity": minutes_per_week_capacity},
        "feasibility": {"earliest_wd_available": earliest_wd_available, "wd_needed_all": wd_needed_all, "hard_block": hard_block, "reason": reason},
    }