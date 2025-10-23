# production61.py
from typing import List, Dict, Optional
from datetime import date, timedelta
import math

# Band 3 shadow costs (annual)
BAND3_COSTS = {
    "Outer London": 45855.97,
    "Inner London": 49202.70,
    "National": 42247.81,
}


def labour_minutes_budget(num_pris: int, hours: float) -> float:
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


def _dev_rate_from_support(employment_support: str) -> float:
    """
    Dev charge baseline is 20%.
    - If employment_support == "Both" -> 0%
    - If either of the two options ("Employment on release/RoTL" or "Post release") -> 10%
    - Else (None/other) -> 20%
    """
    s = (employment_support or "").lower()
    if "both" in s:
        return 0.0
    if "employment on release/rotl" in s or "post release" in s:
        return 0.10
    return 0.20


def calculate_production_contractual(
    items: List[Dict],
    output_pct: int,
    *,
    workshop_hours: float,
    prisoner_salary: float,
    supervisor_salaries: List[float],
    customer_covers_supervisors: bool,
    region: str,
    customer_type: str,
    apply_vat: bool,
    vat_rate: float,
    num_prisoners: int,
    num_supervisors: int,
    pricing_mode: str = "as-is",              # "as-is" | "target"
    targets: Optional[List[int]] = None,
    employment_support: str = "None",
    contracts: int = 1,
    additional_benefits: bool = False,        # NEW: to enable the 10% instructor-cost discount when ES="Both"
) -> List[Dict]:
    """
    Contractual mode with full breakdown.

    Breakdown rules (per your spec):
      - Instructor cost = instructor salaries apportioned by (workshop_hours / 37.5 / contracts)
      - Overheads = 61% of Instructor cost (or 61% of shadow if customer_covers_supervisors=True)
      - Development charge = dev_rate(employment_support) * (Instructor cost + Overheads)
      - Development discount is implicit when dev_rate < 20% (we expose before/discount/revised values)
      - Additional benefit discount: ONLY if employment_support == "Both" AND additional_benefits=True,
        equals 10% of Instructor cost (monthly)

    Unit pricing:
      - "Unit Cost (£)" fields remain as before (all-in cost path, ex VAT) for backward compatibility
      - NEW: "Unit Cost from Prisoner Wages (£)" = (pris_assigned * prisoner_salary) / units (weekly base)
      - NEW: "Units to cover fixed costs (per month)" = monthly_fixed_costs / (Unit Cost from Prisoner Wages * 52/12)

    NOTE: This function returns per-item rows. The breakdown values are repeated per-item using the item's
    share of total assigned minutes to apportion weekly instructor/overhead/dev pools.
    """
    # Hours/contract fraction
    hours_frac = (float(workshop_hours) / 37.5) if workshop_hours > 0 else 0.0
    contracts_safe = max(1, int(contracts))

    # Instructor weekly total (if customer provides instructors, this is 0; shadow is used for overhead base)
    if not customer_covers_supervisors:
        inst_weekly_total = sum((s / 52.0) * hours_frac / contracts_safe for s in supervisor_salaries)
    else:
        inst_weekly_total = 0.0

    # Overhead base (shadow if customer provides; otherwise actual instructor cost)
    if customer_covers_supervisors:
        shadow = BAND3_COSTS.get(region, 42247.81)
        overhead_base_weekly = (shadow / 52.0) * hours_frac / contracts_safe
    else:
        overhead_base_weekly = inst_weekly_total

    overheads_weekly_total = overhead_base_weekly * 0.61

    # Development charge — derived from employment support
    # NEW: development runs against (instructor + overheads)
    dev_rate_eff = _dev_rate_from_support(employment_support)
    dev_weekly_total_at_20 = (inst_weekly_total + overheads_weekly_total) * 0.20
    dev_weekly_total_actual = (inst_weekly_total + overheads_weekly_total) * dev_rate_eff
    dev_weekly_discount = max(0.0, dev_weekly_total_at_20 - dev_weekly_total_actual)

    # Additional benefit discount — ONLY when ES == "Both" and flag is true
    # NEW rule for Production: 10% of instructor cost
    addl_benefit_weekly = 0.0
    if (employment_support == "Both") and additional_benefits:
        addl_benefit_weekly = inst_weekly_total * 0.10

    denom_minutes = sum(int(it.get("assigned", 0)) * workshop_hours * 60.0 for it in items)
    output_scale = float(output_pct) / 100.0

    results: List[Dict] = []
    for idx, it in enumerate(items):
        name = (it.get("name") or "").strip() or f"Item {idx+1}"
        mins_per_unit = float(it.get("minutes", 0))
        pris_required = int(it.get("required", 1))
        pris_assigned = int(it.get("assigned", 0))

        # Capacity at 100% and at output%
        if pris_assigned > 0 and mins_per_unit > 0 and pris_required > 0 and workshop_hours > 0:
            cap_100 = (pris_assigned * workshop_hours * 60.0) / (mins_per_unit * pris_required)
        else:
            cap_100 = 0.0
        capacity_units = cap_100 * output_scale

        # Share of total assigned minutes
        share = ((pris_assigned * workshop_hours * 60.0) / denom_minutes) if denom_minutes > 0 else 0.0

        # Weekly prisoner wages for this item
        prisoner_weekly_item = pris_assigned * prisoner_salary

        # Weekly pools allocated to the item (breakdown – EXCLUDES prisoner wages)
        inst_weekly_item = inst_weekly_total * share
        overheads_weekly_item = overheads_weekly_total * share
        dev_weekly_item_at_20 = dev_weekly_total_at_20 * share
        dev_weekly_item_actual = dev_weekly_total_actual * share
        dev_weekly_item_discount = dev_weekly_item_at_20 - dev_weekly_item_actual
        addl_benefit_weekly_item = addl_benefit_weekly * share

        # Units to price
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

        # Feasibility check (target mode)
        output_scale_local = float(output_pct) / 100.0
        available_minutes_item = pris_assigned * workshop_hours * 60.0 * output_scale_local
        required_minutes_item = units_for_pricing * mins_per_unit * pris_required
        feasible = (required_minutes_item <= (available_minutes_item + 1e-6))
        note = None
        if pricing_mode == "target" and not feasible:
            note = (
                f"Target requires {required_minutes_item:,.0f} mins vs "
                f"available {available_minutes_item:,.0f} mins; exceeds capacity."
            )

        # ============== Unit costs (legacy path maintained) ==============
        # Legacy "all-in" weekly cost includes everything
        weekly_cost_item_total = (
            prisoner_weekly_item
            + inst_weekly_item
            + overheads_weekly_item
            + dev_weekly_item_actual
            - addl_benefit_weekly_item
        )

        if units_for_pricing > 0:
            unit_cost_ex_vat = weekly_cost_item_total / units_for_pricing
        else:
            unit_cost_ex_vat = None

        unit_price_inc_vat = None
        if unit_cost_ex_vat is not None:
            unit_price_inc_vat = (
                unit_cost_ex_vat * (1 + (float(vat_rate) / 100.0))
                if (customer_type == "Commercial" and apply_vat)
                else unit_cost_ex_vat
            )

        monthly_total_ex_vat = (
            (units_for_pricing * unit_cost_ex_vat * 52 / 12) if (unit_cost_ex_vat is not None) else None
        )
        monthly_total_inc_vat = (
            (units_for_pricing * unit_price_inc_vat * 52 / 12) if (unit_price_inc_vat is not None) else None
        )

        # ============== NEW metrics for your breakdown ==============
        # "Fixed costs" exclude prisoner wages (as requested; same approach as Host)
        monthly_inst = inst_weekly_item * 52.0 / 12.0
        monthly_oh   = overheads_weekly_item * 52.0 / 12.0
        monthly_dev_before  = dev_weekly_item_at_20 * 52.0 / 12.0
        monthly_dev_discount = dev_weekly_item_discount * 52.0 / 12.0
        monthly_dev_revised  = dev_weekly_item_actual * 52.0 / 12.0
        monthly_addl_benefit = addl_benefit_weekly_item * 52.0 / 12.0

        monthly_fixed_costs_ex_prisoner = (
            monthly_inst
            + monthly_oh
            + monthly_dev_revised
            - monthly_addl_benefit
        )

        # Prisoner-only unit cost (weekly)
        if units_for_pricing > 0:
            unit_cost_from_prisoner = prisoner_weekly_item / units_for_pricing
        else:
            unit_cost_from_prisoner = None

        # Units per month needed to cover fixed costs
        # (monthly_fixed_costs) / (unit_cost_from_prisoner * 52/12)
        if unit_cost_from_prisoner and unit_cost_from_prisoner > 0:
            monthly_units_to_cover = monthly_fixed_costs_ex_prisoner / (unit_cost_from_prisoner * 52.0 / 12.0)
        else:
            monthly_units_to_cover = None

        # Output row
        results.append({
            "Item": name,
            "Output %": int(output_pct),
            "Capacity (units/week)": 0 if capacity_units <= 0 else int(round(capacity_units)),
            "Units/week": 0 if units_for_pricing <= 0 else int(round(units_for_pricing)),

            # Legacy columns (kept so your app keeps working)
            "Unit Cost (£)": unit_cost_ex_vat,
            "Unit Price ex VAT (£)": unit_cost_ex_vat,
            "Unit Price inc VAT (£)": unit_price_inc_vat,
            "Monthly Total ex VAT (£)": monthly_total_ex_vat,
            "Monthly Total inc VAT (£)": monthly_total_inc_vat,

            # NEW — breakdown (excludes prisoner wages)
            "Instructor cost (weekly £)": inst_weekly_item,
            "Overheads (weekly £)": overheads_weekly_item,
            "Development charge at 20% (weekly £)": dev_weekly_item_at_20,
            "Development discount (weekly £)": dev_weekly_item_discount,
            "Development revised (weekly £)": dev_weekly_item_actual,
            "Additional benefit discount (weekly £)": addl_benefit_weekly_item,

            "Instructor cost (monthly £)": monthly_inst,
            "Overheads (monthly £)": monthly_oh,
            "Development charge at 20% (monthly £)": monthly_dev_before,
            "Development discount (monthly £)": monthly_dev_discount,
            "Development revised (monthly £)": monthly_dev_revised,
            "Additional benefit discount (monthly £)": monthly_addl_benefit,

            "Monthly Fixed Costs excl Prisoner (£)": monthly_fixed_costs_ex_prisoner,

            # NEW — unit cost / cover metrics
            "Unit Cost from Prisoner Wages (£)": unit_cost_from_prisoner,
            "Units to cover fixed costs (per month)": monthly_units_to_cover,

            # Target feasibility
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
    customer_covers_supervisors: bool,
    region: str,
    customer_type: str,
    apply_vat: bool,
    vat_rate: float,
    today: date,
    employment_support: str = "None",
    contracts: int = 1,
) -> Dict:
    """
    Ad-hoc flow (UNCHANGED).
    """
    output_scale = float(output_pct) / 100.0
    hours_per_day = float(workshop_hours) / 5.0
    daily_minutes_capacity_per_prisoner = hours_per_day * 60.0 * output_scale
    current_daily_capacity = num_prisoners * daily_minutes_capacity_per_prisoner
    minutes_per_week_capacity = max(1e-9, num_prisoners * workshop_hours * 60.0 * output_scale)

    # Hours/contract fraction
    hours_frac = (float(workshop_hours) / 37.5) if workshop_hours > 0 else 0.0
    contracts_safe = max(1, int(contracts))

    # Instructor weekly total
    if not customer_covers_supervisors:
        inst_weekly_total = sum((s / 52.0) * hours_frac / contracts_safe for s in supervisor_salaries)
    else:
        inst_weekly_total = 0.0

    # Overheads base
    if customer_covers_supervisors:
        shadow = BAND3_COSTS.get(region, 42247.81)
        overhead_base = (shadow / 52.0) * hours_frac / contracts_safe
    else:
        overhead_base = inst_weekly_total

    overheads_weekly = overhead_base * 0.61
    dev_rate_eff = _dev_rate_from_support(employment_support)
    dev_weekly_total = (inst_weekly_total + overheads_weekly) * dev_rate_eff  # <- use (inst+oh) here too

    prisoners_weekly_cost = num_prisoners * prisoner_salary
    weekly_cost_total = prisoners_weekly_cost + inst_weekly_total + overheads_weekly + dev_weekly_total
    cost_per_minute = weekly_cost_total / minutes_per_week_capacity

    per_line, total_job_minutes, earliest_wd_available = [], 0.0, None
    for ln in lines:
        mins_per_unit = float(ln["mins_per_item"]) * int(ln["pris_per_item"])  # already in minutes
        unit_cost_ex_vat = cost_per_minute * mins_per_unit
        if customer_type == "Commercial" and apply_vat:
            unit_cost_inc_vat = unit_cost_ex_vat * (1 + (float(vat_rate) / 100.0))
        else:
            unit_cost_inc_vat = unit_cost_ex_vat

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


def build_adhoc_table(result: Dict):
    """Helper to produce the flat table used by newapp for Ad-hoc (UNCHANGED)."""
    rows = []
    for p in result.get("per_line", []):
        rows.append({
            "Item": p.get("name", "—"),
            "Units": p.get("units", 0),
            "Unit Cost (ex VAT £)": round(p.get("unit_cost_ex_vat", 0.0), 2),
            "Unit Cost (inc VAT £)": round(p.get("unit_cost_inc_vat", 0.0), 2),
            "Line Total (ex VAT £)": round(p.get("line_total_ex_vat", 0.0), 2),
            "Line Total (inc VAT £)": round(p.get("line_total_inc_vat", 0.0), 2),
        })
    import pandas as pd
    df = pd.DataFrame(rows, columns=[
        "Item", "Units", "Unit Cost (ex VAT £)", "Unit Cost (inc VAT £)",
        "Line Total (ex VAT £)", "Line Total (inc VAT £)"
    ])
    totals = result.get("totals", {})
    return df, totals