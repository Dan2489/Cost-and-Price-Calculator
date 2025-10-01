# production61.py
from typing import List, Dict, Optional
from datetime import date, timedelta
import math
from tariff61 import BAND3_COSTS

# ---------- Helpers ----------
def labour_minutes_budget(num_pris: int, hours: float) -> float:
    """Available labour minutes per week at 100% output."""
    return max(0.0, float(num_pris) * float(hours) * 60.0)

def _working_days_between(start: date, end: date) -> int:
    if end < start: 
        return 0
    days, d = 0, start
    while d <= end:
        if d.weekday() < 5:
            days += 1
        d += timedelta(days=1)
    return days

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
    dev_rate: float,
    pricing_mode: str,                 # "as-is" or "target"
    targets: Optional[List[int]],
    lock_overheads: bool,
    num_prisoners: int,
    contracts_overseen: int,
) -> Dict:

    # Instructor weekly cost (apportioned by allocation% and contracts)
    if customer_covers_supervisors or len(supervisor_salaries) == 0:
        inst_weekly_total = 0.0
    else:
        share = (float(effective_pct) / 100.0) / max(1, int(contracts_overseen))
        inst_weekly_total = sum((s / 52.0) * share for s in supervisor_salaries)

    # Overheads base (61% rule)
    if customer_covers_supervisors:
        shadow = BAND3_COSTS.get(region, BAND3_COSTS["National"])
        overhead_base = (shadow / 52.0) * (float(effective_pct) / 100.0)
    else:
        overhead_base = inst_weekly_total

    if lock_overheads and supervisor_salaries:
        overhead_base = (max(supervisor_salaries) / 52.0) * (float(effective_pct) / 100.0)

    overheads_weekly = overhead_base * 0.61
    dev_weekly_total = overheads_weekly * (float(dev_rate) if customer_type == "Commercial" else 0.0)

    # Minutes
    available_100 = labour_minutes_budget(num_prisoners, workshop_hours)
    output_scale = float(output_pct) / 100.0
    available_planned = available_100 * output_scale

    denom = sum(int(it.get("assigned", 0)) * workshop_hours * 60.0 for it in items)

    per_rows: List[Dict] = []
    for idx, it in enumerate(items):
        name = (it.get("name") or "").strip() or f"Item {idx+1}"
        mins_per_unit = float(it.get("minutes", 0))
        pris_required = int(it.get("required", 1))
        pris_assigned = int(it.get("assigned", 0))

        cap_100 = 0.0
        if pris_assigned > 0 and mins_per_unit > 0 and pris_required > 0 and workshop_hours > 0:
            cap_100 = (pris_assigned * workshop_hours * 60.0) / (mins_per_unit * pris_required)
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
                try:
                    tgt = int(targets[idx])
                except Exception:
                    tgt = 0
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
        unit_price_inc_vat = (unit_price_ex_vat * 1.20) if (unit_price_ex_vat and customer_type == "Commercial") else unit_price_ex_vat

        monthly_total_ex_vat = (units_for_pricing * unit_cost_ex_vat * 52 / 12) if unit_cost_ex_vat else None
        monthly_total_inc_vat = (units_for_pricing * unit_price_inc_vat * 52 / 12) if unit_price_inc_vat else None

        per_rows.append({
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
            "Note": note if pricing_mode == "target" else None,
        })

    return {
        "per_item": per_rows,
        "minutes": {"available_100": available_100, "available_planned": available_planned}
    }

# ---------- Ad-hoc ----------
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
    dev_rate: float,
    lock_overheads: bool,
    contracts_overseen: int,
    today: date,
) -> Dict:
    output_scale = float(output_pct) / 100.0
    hours_per_day = float(workshop_hours) / 5.0
    daily_minutes_capacity_per_prisoner = hours_per_day * 60.0 * output_scale
    current_daily_capacity = num_prisoners * daily_minutes_capacity_per_prisoner
    minutes_per_week_capacity = max(1e-9, num_prisoners * workshop_hours * 60.0 * output_scale)

    # Instructor weekly cost
    if customer_covers_supervisors or len(supervisor_salaries) == 0:
        inst_weekly_total = 0.0
    else:
        share = (float(effective_pct) / 100.0) / max(1, int(contracts_overseen))
        inst_weekly_total = sum((s / 52.0) * share for s in supervisor_salaries)

    # Overheads (61%)
    if customer_covers_supervisors:
        shadow = BAND3_COSTS.get(region, BAND3_COSTS["National"])
        overhead_base = (shadow / 52.0) * (float(effective_pct) / 100.0)
    else:
        overhead_base = inst_weekly_total

    if lock_overheads and supervisor_salaries:
        overhead_base = (max(supervisor_salaries) / 52.0) * (float(effective_pct) / 100.0)

    overheads_weekly = overhead_base * 0.61
    dev_weekly_total = overheads_weekly * (float(dev_rate) if customer_type == "Commercial" else 0.0)
    prisoners_weekly_cost = num_prisoners * prisoner_salary
    weekly_cost_total = prisoners_weekly_cost + inst_weekly_total + overheads_weekly + dev_weekly_total
    cost_per_minute = weekly_cost_total / minutes_per_week_capacity

    per_line, total_job_minutes, earliest_wd_available = [], 0.0, None
    for ln in lines:
        mins_per_unit = float(ln["mins_per_item"]) * int(ln["pris_per_item"])
        unit_cost_ex_vat = cost_per_minute * mins_per_unit
        unit_cost_inc_vat = unit_cost_ex_vat * 1.20 if customer_type == "Commercial" else unit_cost_ex_vat

        total_line_minutes = int(ln["units"]) * mins_per_unit
        total_job_minutes += total_line_minutes
        wd_available = _working_days_between(today, ln["deadline"])
        if earliest_wd_available is None or wd_available < earliest_wd_available:
            earliest_wd_available = wd_available

        per_line.append({
            "Item": ln["name"],
            "Units": int(ln["units"]),
            "Unit Cost ex VAT (£)": unit_cost_ex_vat,
            "Unit Cost inc VAT (£)": unit_cost_inc_vat,
            "Total ex VAT (£)": unit_cost_ex_vat * int(ln["units"]),
            "Total inc VAT (£)": unit_cost_inc_vat * int(ln["units"]),
        })

    earliest_wd_available = earliest_wd_available or 0
    available_total_minutes_by_deadline = current_daily_capacity * earliest_wd_available
    hard_block = total_job_minutes > available_total_minutes_by_deadline

    # Feasibility advice (UK date)
    if hard_block:
        deficit = total_job_minutes - available_total_minutes_by_deadline
        extra_pris = None
        if earliest_wd_available > 0:
            extra_pris = math.ceil(deficit / (hours_per_day * 60.0 * earliest_wd_available))
        extra_days = math.ceil(deficit / current_daily_capacity) if current_daily_capacity > 0 else None
        advice = (
            f"Requested {total_job_minutes:,.0f} mins > available {available_total_minutes_by_deadline:,.0f} mins by deadline. "
            f"To meet demand, add {extra_pris or '?'} prisoner(s) or extend deadline by {extra_days or '?'} working day(s)."
        )
    else:
        finish_days = math.ceil(total_job_minutes / current_daily_capacity) if current_daily_capacity > 0 else 0
        finish_date = today
        days_added = 0
        while days_added < finish_days:
            finish_date += timedelta(days=1)
            if finish_date.weekday() < 5:
                days_added += 1
        advice = f"Earliest ready date: {finish_date.strftime('%d/%m/%Y')}"

    totals_ex = sum(p["Total ex VAT (£)"] for p in per_line)
    totals_inc = sum(p["Total inc VAT (£)"] for p in per_line)

    return {
        "per_line": per_line,
        "totals": {"ex_vat": totals_ex, "inc_vat": totals_inc},
        "capacity": {"current_daily_capacity": current_daily_capacity, "minutes_per_week_capacity": minutes_per_week_capacity},
        "feasibility": {"hard_block": hard_block, "advice": advice},
    }