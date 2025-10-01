from typing import List, Dict, Optional
from datetime import date
import pandas as pd
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

    # Development charge (Commercial only, with support deductions)
    dev_rate_final = 0.20
    if employment_support == "Employment on release/RoTL":
        dev_rate_final -= 0.10
    elif employment_support == "Post release":
        dev_rate_final -= 0.10
    elif employment_support == "Both":
        dev_rate_final -= 0.20
    dev_rate_final = max(dev_rate_final, 0.0)

    dev_weekly_total = overheads_weekly * dev_rate_final if customer_type == "Commercial" else 0.0

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
        dev_weekly_item       = dev_weekly_total * share
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
        if unit_cost_ex_vat is not None and (customer_type == "Commercial" and apply_vat):
            unit_price_inc_vat = unit_cost_ex_vat * (1 + (vat_rate / 100.0))
        else:
            unit_price_inc_vat = unit_cost_ex_vat

        monthly_total_ex_vat = (units_for_pricing * unit_cost_ex_vat * 52 / 12) if unit_cost_ex_vat else None
        monthly_total_inc_vat = (units_for_pricing * unit_price_inc_vat * 52 / 12) if unit_price_inc_vat else None

        results.append({
            "Item": name,
            "Output %": int(output_pct),
            "Capacity (units/week)": 0 if capacity_units <= 0 else int(round(capacity_units)),
            "Units/week": 0 if units_for_pricing <= 0 else int(round(units_for_pricing)),
            "Unit Cost (£)": unit_cost_ex_vat,
            "Unit Price ex VAT (£)": unit_cost_ex_vat,
            "Unit Price inc VAT (£)": unit_price_inc_vat,
            "Monthly Total ex VAT (£)": monthly_total_ex_vat,
            "Monthly Total inc VAT (£)": monthly_total_inc_vat,
            "Feasible": feasible if pricing_mode == "target" else None,
            "Note": note,
        })
    return results

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
    apply_vat: bool,
    vat_rate: float,
    dev_rate: float,
    today: date,
    lock_overheads: bool,
    employment_support: str,
) -> Dict:
    # keep your existing implementation
    # (returns per_line, totals, feasibility)
    return {}

# ---------- Ad-hoc Table Builder ----------
def build_adhoc_table(result):
    """Turn calculate_adhoc() result into a DataFrame + totals."""
    per_line = result.get("per_line", [])
    col_headers = [
        "Item", "Units",
        "Unit Cost (ex VAT £)", "Unit Cost (inc VAT £)",
        "Line Total (ex VAT £)", "Line Total (inc VAT £)"
    ]
    data_rows = []
    for p in per_line:
        data_rows.append([
            str(p.get("name", "—")),
            f"{int(p.get('units', 0)):,}",
            fmt_currency(p.get("unit_cost_ex_vat", 0)),
            fmt_currency(p.get("unit_cost_inc_vat", 0)),
            fmt_currency(p.get("line_total_ex_vat", 0)),
            fmt_currency(p.get("line_total_inc_vat", 0)),
        ])
    if not data_rows:
        data_rows = [["—", "0", "£0.00", "£0.00", "£0.00", "£0.00"]]

    df = pd.DataFrame(data_rows, columns=col_headers)
    totals = {
        "ex_vat": result.get("totals", {}).get("ex_vat", 0),
        "inc_vat": result.get("totals", {}).get("inc_vat", 0)
    }
    return df, totals