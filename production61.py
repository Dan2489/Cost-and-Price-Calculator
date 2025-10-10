import pandas as pd
import math
from datetime import date, timedelta
from config61 import CFG
from utils61 import fmt_currency

# Band 3 shadow costs (annual)
BAND3_COSTS = {
    "Outer London": 45855.97,
    "Inner London": 49202.70,
    "National": 42247.81,
}

# ---------- Helpers ----------
def labour_minutes_budget(num_pris: int, hours: float) -> float:
    return max(0.0, float(num_pris) * float(hours) * 60.0)

# ---------- Contractual ----------
def calculate_production_contractual(
    items,
    output_pct: int,
    *,
    workshop_hours: float,
    prisoner_salary: float,
    supervisor_salaries: list[float],
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
    targets=None,
    lock_overheads: bool = False,
    employment_support: str = "None",
):
    results = []
    # Development rate logic
    dev_rate = 0.20
    if employment_support in ("Employment on release/RoTL", "Post release"):
        dev_rate = 0.10
    elif employment_support == "Both":
        dev_rate = 0.00

    # Instructor weekly cost
    if not customer_covers_supervisors:
        inst_weekly_total = sum((s / 52.0) * (effective_pct / 100.0) for s in supervisor_salaries)
    else:
        inst_weekly_total = 0.0

    # Overhead base
    if customer_covers_supervisors:
        shadow = BAND3_COSTS.get(region, 42247.81)
        overhead_base = (shadow / 52.0) * (effective_pct / 100.0)
    else:
        overhead_base = inst_weekly_total

    if lock_overheads and supervisor_salaries:
        overhead_base = (max(supervisor_salaries) / 52.0) * (effective_pct / 100.0)

    overheads_weekly = overhead_base * 0.61
    dev_weekly_total = overheads_weekly * dev_rate

    for idx, it in enumerate(items):
        name = it.get("name", f"Item {idx+1}")
        mins_per_unit = float(it.get("minutes", 0))
        pris_required = int(it.get("required", 1))
        pris_assigned = int(it.get("assigned", 0))
        current_price = float(it.get("current_price", 0.0))

        cap_100 = (pris_assigned * workshop_hours * 60.0) / (mins_per_unit * pris_required) if pris_assigned > 0 else 0.0
        capacity_units = cap_100 * (output_pct / 100.0)

        share = (pris_assigned * workshop_hours * 60.0)
        total_minutes = sum(i["assigned"] * workshop_hours * 60.0 for i in items)
        share_ratio = share / total_minutes if total_minutes > 0 else 0.0

        prisoner_weekly_item = pris_assigned * prisoner_salary
        inst_weekly_item = inst_weekly_total * share_ratio
        overheads_weekly_item = overheads_weekly * share_ratio
        dev_weekly_item = dev_weekly_total * share_ratio
        weekly_cost_item = prisoner_weekly_item + inst_weekly_item + overheads_weekly_item + dev_weekly_item

        units_for_pricing = capacity_units if pricing_mode == "as-is" else float(it.get("target", 0))
        unit_cost_ex_vat = (weekly_cost_item / units_for_pricing) if units_for_pricing > 0 else 0.0
        monthly_total_ex_vat = unit_cost_ex_vat * units_for_pricing * 52 / 12 if unit_cost_ex_vat else 0.0

        # Uplift vs current price
        uplift_pct = ((unit_cost_ex_vat - current_price) / current_price * 100.0) if current_price > 0 else None

        results.append({
            "Item": name,
            "Output %": int(output_pct),
            "Capacity (units/week)": int(round(capacity_units)),
            "Units/week": int(round(units_for_pricing)),
            "Unit Price ex VAT (£)": unit_cost_ex_vat,
            "Monthly Total ex VAT (£)": monthly_total_ex_vat,
            "Instructor Cost (£)": inst_weekly_item * 52 / 12,
            "Overhead (£)": overheads_weekly_item * 52 / 12,
            "Development (£)": dev_weekly_item * 52 / 12,
            "Uplift vs Current (%)": uplift_pct,
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
    lines,
    output_pct: int,
    *,
    workshop_hours: float,
    num_prisoners: int,
    prisoner_salary: float,
    supervisor_salaries: list[float],
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
):
    dev_rate = 0.20
    if employment_support in ("Employment on release/RoTL", "Post release"):
        dev_rate = 0.10
    elif employment_support == "Both":
        dev_rate = 0.00

    output_scale = float(output_pct) / 100.0
    hours_per_day = float(workshop_hours) / 5.0
    daily_minutes_capacity_per_prisoner = hours_per_day * 60.0 * output_scale
    current_daily_capacity = num_prisoners * daily_minutes_capacity_per_prisoner

    # Instructor weekly
    if not customer_covers_supervisors:
        inst_weekly_total = sum((s / 52.0) * (effective_pct / 100.0) for s in supervisor_salaries)
    else:
        inst_weekly_total = 0.0
    if customer_covers_supervisors:
        shadow = BAND3_COSTS.get(region, 42247.81)
        overhead_base = (shadow / 52.0) * (effective_pct / 100.0)
    else:
        overhead_base = inst_weekly_total
    if lock_overheads and supervisor_salaries:
        overhead_base = (max(supervisor_salaries) / 52.0) * (effective_pct / 100.0)
    overheads_weekly = overhead_base * 0.61
    dev_weekly_total = overheads_weekly * dev_rate

    per_line = []
    for ln in lines:
        mins_per_unit = float(ln["mins_per_item"]) * int(ln["pris_per_item"])
        units = int(ln["units"])
        current_price = float(ln.get("current_price", 0.0))

        prisoner_weekly_cost = num_prisoners * prisoner_salary
        weekly_cost_total = prisoner_weekly_cost + inst_weekly_total + overheads_weekly + dev_weekly_total
        unit_cost_ex_vat = (weekly_cost_total / (num_prisoners * workshop_hours * 60.0)) * mins_per_unit
        monthly_total_ex_vat = unit_cost_ex_vat * units * 52 / 12 if unit_cost_ex_vat else 0.0
        uplift_pct = ((unit_cost_ex_vat - current_price) / current_price * 100.0) if current_price > 0 else None

        per_line.append({
            "Item": ln["name"],
            "Units": units,
            "Unit Price ex VAT (£)": unit_cost_ex_vat,
            "Monthly Total ex VAT (£)": monthly_total_ex_vat,
            "Instructor Cost (£)": inst_weekly_total * 52 / 12,
            "Overhead (£)": overheads_weekly * 52 / 12,
            "Development (£)": dev_weekly_total * 52 / 12,
            "Uplift vs Current (%)": uplift_pct,
        })

    return {"per_line": per_line}


# ---------- Comparison ----------
def build_production_comparison(supervisor_salaries, region, employment_support, lock_overheads, customer_covers_supervisors):
    """Build simple Instructor % comparison table for production view."""
    recommended_pct = 100.0  # will be overridden externally if needed
    scenarios = {
        "100%": 100.0,
        "Recommended": recommended_pct,
        "50%": 50.0,
        "25%": 25.0,
    }

    rows = []
    for label, pct in scenarios.items():
        if not customer_covers_supervisors:
            inst_cost = sum((s / 12.0) * (pct / 100.0) for s in supervisor_salaries)
        else:
            inst_cost = 0.0
        if customer_covers_supervisors:
            shadow = BAND3_COSTS.get(region, 42247.81)
            base_overhead = (shadow / 12.0) * (pct / 100.0)
        else:
            base_overhead = inst_cost
        if lock_overheads and supervisor_salaries:
            base_overhead = (max(supervisor_salaries) / 12.0) * (pct / 100.0)
        overhead = base_overhead * 0.61
        dev_rate = 0.20
        if employment_support in ("Employment on release/RoTL", "Post release"):
            dev_rate = 0.10
        elif employment_support == "Both":
            dev_rate = 0.00
        dev_charge = overhead * dev_rate
        total = inst_cost + overhead + dev_charge
        rows.append({
            "Scenario": label,
            "Instructor %": f"{pct:.1f}%",
            "Instructor Cost (£)": fmt_currency(inst_cost),
            "Overhead (£)": fmt_currency(overhead),
            "Development (£)": fmt_currency(dev_charge),
            "Total Monthly ex VAT (£)": fmt_currency(total),
        })
    return pd.DataFrame(rows)


# ---------- Ad-hoc table builder ----------
def build_adhoc_table(result: dict):
    per_line = result.get("per_line", [])
    df = pd.DataFrame(per_line)
    for c in df.columns:
        if "£" in c or "Total" in c or "Price" in c:
            df[c] = df[c].apply(fmt_currency)
    totals = {
        "Total Monthly ex VAT (£)": fmt_currency(df["Monthly Total ex VAT (£)"].apply(lambda x: float(str(x).replace("£", "").replace(",", ""))).sum())
    }
    return df, totals