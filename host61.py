from typing import List, Tuple
import pandas as pd
import streamlit as st
from config61 import CFG

# Band 3 shadow annual salaries for overheads when customer provides instructors
BAND3_SHADOW = {
    "Outer London": 45855.97,
    "Inner London": 49202.70,
    "National": 42247.81,
}

def generate_host_quote(
    *,
    region: str,
    num_prisoners: int,
    prisoner_salary: float,
    num_supervisors: int,
    customer_covers_supervisors: bool,
    supervisor_salaries: List[float],
    effective_pct: float,
    customer_type: str,        # "Commercial" or "Another Government Department"
    support: str,              # "None" | "Employment on release/RoTL" | "Post release" | "Both"
    lock_overheads: bool,
    apply_vat: bool,
    vat_rate: float,
) -> Tuple[pd.DataFrame, dict]:
    rows = []

    # Prisoner wages (monthly)
    prisoner_wages_m = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)
    rows.append(("Prisoner wages", prisoner_wages_m))

    # Instructors (monthly) — only if MoJ pays
    instructor_cost_m = 0.0
    if not customer_covers_supervisors:
        instructor_cost_m = sum((s / 12.0) * (float(effective_pct) / 100.0) for s in supervisor_salaries)
    rows.append(("Instructors", instructor_cost_m))

    # Overheads = 61% of instructor cost
    if customer_covers_supervisors:
        # use Band 3 shadow salary for selected region
        band3 = BAND3_SHADOW.get(region, BAND3_SHADOW["National"])
        overheads_m = (band3 * CFG.OVERHEAD_PCT) / 12.0
    else:
        if lock_overheads and supervisor_salaries:
            overheads_m = (max(supervisor_salaries) / 12.0) * CFG.OVERHEAD_PCT
        else:
            overheads_m = instructor_cost_m * CFG.OVERHEAD_PCT
    rows.append(("Overheads (61%)", overheads_m))

    # Development charge (Commercial only), with breakdown in the table
    dev_base = 0.0
    dev_reduction = 0.0
    dev_applied = 0.0
    if customer_type == "Commercial":
        # base 20% of overheads
        dev_base = overheads_m * 0.20
        # reductions from support
        if support in ("Employment on release/RoTL", "Post release"):
            dev_reduction = -overheads_m * 0.10
        elif support == "Both":
            dev_reduction = -overheads_m * 0.20
        dev_applied = dev_base + dev_reduction
        # Show in the table: base → reductions → applied
        rows.append(("Development charge (base 20%)", dev_base))
        rows.append(("Development charge reductions", dev_reduction))  # negative; will render red
        rows.append(("Development charge (applied)", dev_applied))

    # Subtotal, VAT, Grand Total
    subtotal = sum(v for _, v in rows)
    vat_amount = subtotal * (float(vat_rate) / 100.0) if apply_vat else 0.0
    grand_total = subtotal + vat_amount

    rows += [
        ("Subtotal", subtotal),
        (f"VAT ({float(vat_rate):.1f}%)", vat_amount),
        ("Grand Total (£/month)", grand_total),
    ]

    df = pd.DataFrame(rows, columns=["Item", "Amount (£)"])
    ctx = {
        "overheads_m": overheads_m,
        "dev_base": dev_base,
        "dev_reduction": dev_reduction,
        "dev_applied": dev_applied,
        "subtotal": subtotal,
        "vat_amount": vat_amount,
        "grand_total": grand_total,
    }
    return df, ctx