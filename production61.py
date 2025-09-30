import pandas as pd
from typing import List, Dict
from utils61 import BAND3_SHADOW

def calculate_production_costs(
    items: List[Dict],
    workshop_hours: float,
    prisoner_salary: float,
    supervisor_salaries: List[float],
    effective_pct: float,
    customer_covers_supervisors: bool,
    customer_type: str,
    output_pct: int,
    lock_overheads: bool,
    dev_rate: float,
) -> List[Dict]:
    # Prisoner wages (weekly)
    prisoner_weekly = float(prisoner_salary) * float(items[0].get("assigned", 0))

    # Instructor costs
    instructor_weekly = 0.0
    if not customer_covers_supervisors:
        instructor_weekly = sum((s / 52.0) * (effective_pct / 100.0) for s in supervisor_salaries)

    # Overheads = 61% of instructor costs or shadow
    if customer_covers_supervisors:
        region = items[0].get("region", "National")
        base = BAND3_SHADOW.get(region, BAND3_SHADOW["National"])
        overheads_weekly = (base / 52.0) * 0.61
    else:
        if lock_overheads and supervisor_salaries:
            highest = max(supervisor_salaries)
            base = (highest / 52.0) * (effective_pct / 100.0)
            overheads_weekly = base * 0.61
        else:
            overheads_weekly = instructor_weekly * 0.61

    # Development charge (Commercial only)
    dev_weekly = 0.0
    if customer_type == "Commercial":
        dev_weekly = (instructor_weekly + overheads_weekly) * float(dev_rate)

    # Total weekly costs
    weekly_total = prisoner_weekly + instructor_weekly + overheads_weekly + dev_weekly

    results: List[Dict] = []
    for idx, it in enumerate(items):
        name = (it.get("name") or f"Item {idx+1}").strip()
        assigned = int(it.get("assigned", 0))
        mins_per_unit = float(it.get("minutes", 0))
        required = int(it.get("required", 1))

        # capacity calc
        if assigned > 0 and mins_per_unit > 0 and workshop_hours > 0:
            cap_100 = (assigned * workshop_hours * 60.0) / (mins_per_unit * required)
        else:
            cap_100 = 0.0
        capacity_units = cap_100 * (output_pct / 100.0)

        # Costs split equally across items (single item for now)
        prisoner_item = prisoner_weekly
        inst_item = instructor_weekly
        ovh_item = overheads_weekly
        dev_item = dev_weekly
        weekly_cost = prisoner_item + inst_item + ovh_item + dev_item

        unit_cost = (weekly_cost / capacity_units) if capacity_units > 0 else None
        monthly_total = (capacity_units * (unit_cost or 0)) * (52.0 / 12.0)

        results.append({
            "Item": name,
            "Capacity (units/week)": int(capacity_units) if capacity_units > 0 else 0,
            "Unit Cost (£)": unit_cost,
            "Weekly Cost (£)": weekly_cost,
            "Monthly Total (£)": monthly_total,
        })
    return results

def production_summary_table(results: List[Dict]) -> pd.DataFrame:
    return pd.DataFrame(results)