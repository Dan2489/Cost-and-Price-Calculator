# production61.py
from typing import List, Dict, Tuple, Optional
from datetime import date, timedelta
import math

# Band 3 shadow costs (annual, used when customer provides instructor)
BAND3_COSTS = {
    "Outer London": 45855.97,
    "Inner London": 49202.70,
    "National": 42247.81,
}

# ---------- Helpers ----------
def labour_minutes_budget(num_pris: int, hours: float) -> float:
    """Total labour minutes available per week at 100% output."""
    return max(0.0, float(num_pris) * float(hours) * 60.0)

def _overhead_weekly_base(
    *,
    customer_covers_supervisors: bool,
    supervisor_salaries: List[float],
    region: str,
    effective_pct: float,
    lock_overheads: bool,
) -> float:
    """
    Returns the *weekly* base used to calculate overheads before the 61% multiplier.
    - If customer provides instructor(s): use Band 3 region shadow cost.
    - Else: use sum of selected instructor salaries.
    - If lock_overheads: use the highest single instructor salary (or the shadow salary) instead of sum.
    All of the above are pro-rated by effective_pct (instructor allocation).
    """
    eff = float(effective_pct) / 100.0

    if customer_covers_supervisors:
        shadow_annual = BAND3_COSTS.get(region, BAND3_COSTS["National"])
        base = (shadow_annual / 52.0) * eff
        # If locking, still use the same shadow (it *is* already a single cost)
        if lock_overheads:
            return base
        return base

    # Customer does NOT provide instructors → use chosen salaries
    if not supervisor_salaries:
        return 0.0

    if lock_overheads:
        highest = max(supervisor_salaries)
        return (highest / 52.0) * eff

    total_weekly = sum((s / 52.0) * eff for s in supervisor_salaries)
    return total_weekly

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
    pricing_mode: str = "as-is",          # "as-is" or "target"
    targets: Optional[List[int]] = None,  # per-item target units/week if "target"
    lock_overheads: bool = False,
    employment_support: Optional[str] = None,
    recommended_allocation: Optional[float] = None,
    **_,  # ignore any future extra kwargs safely
) -> List[Dict]:
    """
    Calculates per-item costs using:
      - Prisoner wages (weekly): assigned_prisoners * prisoner_salary
      - Instructor cost (weekly): selected salaries * effective_pct (unless customer provides -> 0)
      - Overheads (weekly): 61% of weekly instructor-base (shadow Band 3 if customer provides)
      - Development charge (weekly): dev_rate * overheads_weekly (Commercial only)
    Then spreads shared weekly costs by each item's share of assigned labour minutes.
    Unit costs are (weekly_cost_item / units_for_pricing). Monthly totals = units/week * unit_cost * 52/12.
    """
    output_scale = float(output_pct) / 100.0

    # Overheads (61%) weekly, from base determined by instructor costs or shadow Band 3
    overhead_base_weekly = _overhead_weekly_base(
        customer_covers_supervisors=customer_covers_supervisors,
        supervisor_salaries=supervisor_salaries,
        region=region,
        effective_pct=effective_pct,
        lock_overheads=lock_overheads,
    )
    overheads_weekly = overhead_base_weekly * 0.61

    # Instructor weekly total (if customer covers, this is zero for pricing)
    inst_weekly_total = 0.0 if customer_covers_supervisors else sum(
        (s / 52.0) * (float(effective_pct) / 100.0) for s in supervisor_salaries
    )

    # Development charge only for Commercial
    dev_weekly_total = (overheads_weekly * float(dev_rate)) if customer_type == "Commercial" else 0.0

    # Denominator for shares across items
    denom = sum(int(it.get("assigned", 0)) * workshop_hours * 60.0 for it in items)

    results: List[Dict] = []
    for idx, it in enumerate(items):
        name = (it.get("name") or "").strip() or f"Item {idx+1}"
        mins_per_unit = float(it.get("minutes", 0))
        pris_required = int(it.get("required", 1))
        pris_assigned = int(it.get("assigned", 0))

        # Capacity at 100% and at selected Output%
        if pris_assigned > 0 and mins_per_unit > 0 and pris_required > 0 and workshop_hours > 0:
            cap_100 = (pris_assigned * workshop_hours * 60.0) / (mins_per_unit * pris_required)
        else:
            cap_100 = 0.0
        capacity_units = cap_100 * output_scale

        # Proportional share (by minutes of assigned labour, unscaled by output)
        share = ((pris_assigned * workshop_hours * 60.0) / denom) if denom > 0 else 0.0

        # Weekly components for this item
        prisoner_weekly_item = pris_assigned * prisoner_salary
        inst_weekly_item      = inst_weekly_total * share
        overheads_weekly_item = overheads_weekly * share
        dev_weekly_item       = dev_weekly_total * share
        weekly_cost_item      = prisoner_weekly_item + inst_weekly_item + overheads_weekly_item + dev_weekly_item

        # Units used for pricing
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

        # Feasibility for target mode
        available_minutes_item = pris_assigned * workshop_hours * 60.0 * output_scale
        required_minutes_item  = units_for_pricing * mins_per_unit * pris_required
        feasible = (required_minutes_item <= (available_minutes_item + 1e-6))
        note = None
        if pricing_mode == "target" and not feasible:
            note = (
                f"Target requires {required_minutes_item:,.0f} mins vs "
                f"available {available_minutes_item:,.0f} mins; exceeds capacity."
            )

        # Unit cost, prices and monthly totals
        unit_cost_ex_vat = (weekly_cost_item / units_for_pricing) if units_for_pricing > 0 else None
        if unit_cost_ex_vat is not None and (customer_type == "Commercial" and apply_vat):
            unit_price_inc_vat = unit_cost_ex_vat * (1 + (float(vat_rate) / 100.0))
        else:
            unit_price_inc_vat = unit_cost_ex_vat

        monthly_total_ex_vat = (units_for_pricing * unit_cost_ex_vat * 52 / 12) if unit_cost_ex_vat else None
        monthly_total_inc_vat = (units_for_pricing * unit_price_inc_vat * 52 / 12) if unit_price_inc_vat else None

        results.append({
            "Item": name,
            "Output %": int(output_pct),
            "Pricing mode": "Target units/week" if pricing_mode == "target" else "As-is (max units)",
            "Capacity (units/week)": 0 if capacity_units <= 0 else int(round(capacity_units)),
            "Units/week": 0 if units_for_pricing <= 0 else int(round(units_for_pricing)),
            "Unit Cost (£)": unit_cost_ex_vat,
            "Unit Price ex VAT (£)": unit_cost_ex_vat,  # ex VAT is same as cost in this model
            "Unit Price inc VAT (£)": unit_price_inc_vat,
            "Monthly Total ex VAT (£)": monthly_total_ex_vat,
            "Monthly Total inc VAT (£)": monthly_total_inc_vat,
            "Feasible": feasible if pricing_mode == "target" else None,
            "Note": note,
            # Optional visibility of the recommendation (harmless if you don't display it)
            "Recommended Allocation (%)": round(float(recommended_allocation), 1) if recommended_allocation is not None else None,
            # For downstream comparisons if needed:
            "_weekly_components": {
                "prisoner": prisoner_weekly_item,
                "instructor": inst_weekly_item,
                "overheads": overheads_weekly_item,
                "development": dev_weekly_item,
            }
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
    region: str,
    customer_type: str,
    apply_vat: bool,
    vat_rate: float,
    dev_rate: float,
    today: date,
    lock_overheads: bool = False,
    employment_support: Optional[str] = None,
    recommended_allocation: Optional[float] = None,
    **_,  # ignore any extra kwargs safely
) -> Dict:
    """
    Ad-hoc costing: builds a per-line cost using minutes and units, with the same 61% overhead logic.
    Also checks deadline feasibility (workdays) across all lines.
    """
    output_scale = float(output_pct) / 100.0

    # Weekly overhead base → 61%
    overhead_base_weekly = _overhead_weekly_base(
        customer_covers_supervisors=customer_covers_supervisors,
        supervisor_salaries=supervisor_salaries,
        region=region,
        effective_pct=effective_pct,
        lock_overheads=lock_overheads,
    )
    overheads_weekly = overhead_base_weekly * 0.61

    # Weekly instructor cost (0 if customer covers)
    inst_weekly_total = 0.0 if customer_covers_supervisors else sum(
        (s / 52.0) * (float(effective_pct) / 100.0) for s in supervisor_salaries
    )

    # Dev charge (Commercial only)
    dev_weekly_total = (overheads_weekly * float(dev_rate)) if customer_type == "Commercial" else 0.0

    # Capacity
    hours_per_day = float(workshop_hours) / 5.0
    daily_minutes_capacity_per_prisoner = hours_per_day * 60.0 * output_scale
    current_daily_capacity = num_prisoners * daily_minutes_capacity_per_prisoner
    minutes_per_week_capacity = max(1e-9, num_prisoners * workshop_hours * 60.0 * output_scale)

    # Cost per minute
    prisoners_weekly_cost = num_prisoners * prisoner_salary
    weekly_cost_total = prisoners_weekly_cost + inst_weekly_total + overheads_weekly + dev_weekly_total
    cost_per_minute = weekly_cost_total / minutes_per_week_capacity

    per_line, total_job_minutes, earliest_wd_available = [], 0.0, None
    for ln in lines:
        mins_per_unit = float(ln["mins_per_item"]) * int(ln["pris_per_item"])
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

def build_adhoc_table(result: Dict) -> Tuple[Dict, Dict]:
    """
    Convert calculate_adhoc(...) result into a table structure used by the app.
    Returns (df, totals) where df has the expected columns.
    """
    import pandas as pd

    col_headers = [
        "Item",
        "Units",
        "Unit Cost (ex VAT £)",
        "Unit Cost (inc VAT £)",
        "Line Total (ex VAT £)",
        "Line Total (inc VAT £)",
    ]
    rows = []
    for p in result.get("per_line", []):
        rows.append([
            p.get("name", "—"),
            int(p.get("units", 0)),
            float(p.get("unit_cost_ex_vat", 0.0)),
            float(p.get("unit_cost_inc_vat", 0.0)),
            float(p.get("line_total_ex_vat", 0.0)),
            float(p.get("line_total_inc_vat", 0.0)),
        ])
    df = pd.DataFrame(rows, columns=col_headers)
    return df, result.get("totals", {"ex_vat": 0.0, "inc_vat": 0.0})