# host61.py
import pandas as pd
from utils61 import fmt_currency
from config61 import CFG
from production61 import BAND3_COSTS


def generate_host_quote(
    *,
    workshop_hours: float,
    num_prisoners: int,
    prisoner_salary: float,
    num_supervisors: int,
    supervisor_salaries: list,
    instructor_allocation: float,
    customer_type: str,
    dev_rate: float,
    lock_overheads: bool,
    region: str,
):
    breakdown = {}

    # Prisoner wages (monthly)
    breakdown["Prisoner wages"] = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)

    # Instructor wages (monthly)
    instructor_cost = 0.0
    if num_supervisors > 0:
        instructor_cost = sum((s / 12.0) * (float(instructor_allocation) / 100.0) for s in supervisor_salaries)
    breakdown["Instructors"] = instructor_cost

    # Overheads (61%)
    if num_supervisors > 0:
        overhead_base = instructor_cost
    else:
        shadow = BAND3_COSTS.get(region, 42247.81)
        overhead_base = (shadow / 12.0) * (float(instructor_allocation) / 100.0)

    if lock_overheads and supervisor_salaries:
        overhead_base = (max(supervisor_salaries) / 12.0) * (float(instructor_allocation) / 100.0)

    overheads_monthly = overhead_base * CFG.overheads_rate
    breakdown["Overheads (61%)"] = overheads_monthly

    # Development charge (Commercial only)
    if customer_type == "Commercial":
        breakdown["Development charge (before reductions)"] = overheads_monthly * 0.20
        breakdown["Development charge reductions"] = -(overheads_monthly * (0.20 - dev_rate))
        breakdown["Development charge (applied)"] = overheads_monthly * dev_rate

    subtotal = sum(v for v in breakdown.values())
    vat_amount = subtotal * (CFG.vat_rate / 100.0)
    grand_total = subtotal + vat_amount

    rows = [(k, v) for k, v in breakdown.items()]
    rows += [
        ("Subtotal", subtotal),
        (f"VAT ({CFG.vat_rate:.0f}%)", vat_amount),
        ("Grand Total (£/month)", grand_total),
    ]
    df = pd.DataFrame(rows, columns=["Item", "Amount (£)"])
    df["Amount (£)"] = df["Amount (£)"].apply(fmt_currency)

    ctx = {
        "subtotal": subtotal,
        "vat_amount": vat_amount,
        "grand_total": grand_total,
    }
    return df, ctx