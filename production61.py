import pandas as pd
import streamlit as st
from config61 import CFG

def calculate_production_costs(
    items,
    *,
    workshop_hours: float,
    prisoner_salary: float,
    supervisor_salaries: list,
    effective_pct: float,
    customer_covers_supervisors: bool,
    customer_type: str,
    output_pct: float,
    lock_overheads: bool,
):
    breakdowns = []
    overheads_total = 0.0

    # Prisoner wages (weekly then converted to monthly)
    for it in items:
        name = it.get("name", "Item")
        num_prisoners = int(it.get("assigned", 0))
        mins_per_unit = float(it.get("minutes", 0))
        units_week = int(it.get("units", 0))

        prisoner_cost_weekly = num_prisoners * prisoner_salary
        prisoner_cost_monthly = prisoner_cost_weekly * (52.0 / 12.0)

        # Instructor costs (monthly)
        instructor_costs = []
        for s in supervisor_salaries:
            instructor_costs.append((s / 12.0) * (effective_pct / 100.0))
        if not customer_covers_supervisors:
            inst_monthly = sum(instructor_costs)
        else:
            inst_monthly = 0.0

        # Overheads
        if lock_overheads and supervisor_salaries:
            highest = max(supervisor_salaries)
            overheads = (highest / 12.0) * CFG.OVERHEAD_PCT
        else:
            overheads = sum((s / 12.0) * CFG.OVERHEAD_PCT for s in supervisor_salaries)

        overheads_total += overheads

        # Unit cost
        weekly_cost_item = prisoner_cost_weekly + (inst_monthly * 12.0 / 52.0) + (overheads * 12.0 / 52.0)
        units_for_pricing = units_week
        unit_cost = (weekly_cost_item / units_for_pricing) if units_for_pricing > 0 else None
        monthly_total = units_for_pricing * (unit_cost or 0) * 52.0 / 12.0

        breakdowns.append({
            "Item": name,
            "Units/week": units_for_pricing,
            "Unit Cost (£)": unit_cost,
            "Monthly Total (£)": monthly_total,
        })

    return pd.DataFrame(breakdowns)

def production_summary_table(df: pd.DataFrame) -> pd.DataFrame:
    """Adds a grand total row to the production table"""
    total_monthly = df["Monthly Total (£)"].sum()
    rows = df.values.tolist()
    rows.append(["Grand Total", "", "", total_monthly])
    return pd.DataFrame(rows, columns=df.columns)