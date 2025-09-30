import pandas as pd
import streamlit as st
from config61 import CFG

def generate_host_quote(
    *,
    workshop_hours: float,
    num_prisoners: int,
    prisoner_salary: float,
    num_supervisors: int,
    customer_covers_supervisors: bool,
    supervisor_salaries: list,
    effective_pct: float,
    customer_type: str,
    lock_overheads: bool,
    output_pct: float,
):
    breakdown = {}

    # Prisoner wages
    breakdown["Prisoner wages"] = num_prisoners * prisoner_salary * (52.0 / 12.0)

    # Instructor costs
    instructor_costs = []
    for s in supervisor_salaries:
        instructor_costs.append((s / 12.0) * (effective_pct / 100.0))
    if not customer_covers_supervisors:
        breakdown["Instructor salaries"] = sum(instructor_costs)
    else:
        breakdown["Instructor salaries"] = 0.0

    # Overheads
    if lock_overheads and supervisor_salaries:
        highest = max(supervisor_salaries)
        overheads = (highest / 12.0) * CFG.OVERHEAD_PCT
    else:
        overheads = sum((s / 12.0) * CFG.OVERHEAD_PCT for s in supervisor_salaries)

    breakdown["Overheads (61%)"] = overheads

    # Development charge (Commercial only)
    development_charge = 0.0
    if customer_type == "Commercial":
        development_charge = overheads
        breakdown["Development charge (applied)"] = development_charge
        breakdown["Reduction (50%)"] = -0.5 * development_charge
        breakdown["Revised development charge"] = 0.5 * development_charge

    subtotal = sum(breakdown.values())
    vat = subtotal * 0.20
    total = subtotal + vat

    ctx = {"subtotal": subtotal, "vat": vat, "grand_total": total}
    df = pd.DataFrame(list(breakdown.items()), columns=["Item", "Amount (£)"])
    return df, ctx

def host_summary_table(df: pd.DataFrame, ctx: dict) -> pd.DataFrame:
    """Formats the host summary with subtotal, VAT, and grand total"""
    rows = df.values.tolist()
    rows.append(["Subtotal", ctx["subtotal"]])
    rows.append([f"VAT (20%)", ctx["vat"]])
    rows.append(["Grand Total (£/month)", ctx["grand_total"]])
    return pd.DataFrame(rows, columns=["Item", "Amount (£)"])