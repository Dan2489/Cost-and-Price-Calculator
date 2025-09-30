import pandas as pd
import streamlit as st
from config61 import CFG

def generate_host_quote(
    *,
    workshop_hours: float,
    area_m2: float,
    usage_key: str,
    num_prisoners: int,
    prisoner_salary: float,
    num_supervisors: int,
    customer_covers_supervisors: bool,
    supervisor_salaries: list,
    effective_pct: float,
    customer_type: str,
    apply_vat: bool,
    vat_rate: float,
    dev_rate: float,
    lock_overheads: bool,
) -> tuple[pd.DataFrame, dict]:
    breakdown: dict[str, float] = {}
    breakdown["Prisoner wages"] = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)

    instructor_cost = 0.0
    if not customer_covers_supervisors:
        instructor_cost = sum((s / 12.0) * (float(effective_pct) / 100.0) for s in supervisor_salaries)
    breakdown["Instructors"] = instructor_cost

    # Overheads = 61% of instructor salaries
    if lock_overheads and supervisor_salaries:
        highest = max(supervisor_salaries)
        overheads_subtotal = (highest / 12.0) * 0.61
    else:
        overheads_subtotal = instructor_cost * 0.61
    breakdown["Overheads (61%)"] = overheads_subtotal

    # Development charge (applies only to Commercial contracts)
    dev_charge = 0.0
    if customer_type == "Commercial":
        dev_charge = overheads_subtotal * float(dev_rate)
        breakdown["Development charge (applied)"] = dev_charge

        # Show reductions (red in summary) if dev_rate < 0.20
        if dev_rate < 0.20:
            reduction = overheads_subtotal * (0.20 - dev_rate)
            breakdown["Reduction"] = -reduction
            revised_dev_charge = dev_charge
            breakdown["Revised development charge"] = revised_dev_charge

    subtotal = sum(v for v in breakdown.values())
    vat_amount = subtotal * (float(vat_rate) / 100.0)
    grand_total = subtotal + vat_amount

    rows = list(breakdown.items()) + [
        ("Subtotal", subtotal),
        (f"VAT ({float(vat_rate):.1f}%)", vat_amount),
        ("Grand Total (£/month)", grand_total),
    ]
    host_df = pd.DataFrame(rows, columns=["Item", "Amount (£)"])

    ctx = {
        "overheads_subtotal": overheads_subtotal,
        "subtotal": subtotal,
        "vat_amount": vat_amount,
        "grand_total": grand_total,
    }
    return host_df, ctx


def host_summary_table(df: pd.DataFrame) -> pd.DataFrame:
    """Format summary: bold totals, red reductions."""
    styled = df.style.format({"Amount (£)": "£{:,.2f}"})

    # Bold important rows
    bold_rows = ["Subtotal", "Grand Total (£/month)"]
    styled = styled.apply(
        lambda s: ["font-weight: bold" if v in bold_rows else "" for v in s],
        axis=1,
        subset=["Item"],
    )

    # Red font for reductions
    def highlight_reduction(val):
        if isinstance(val, str) and "Reduction" in val:
            return "color: red"
        return ""
    styled = styled.applymap(highlight_reduction, subset=["Item"])

    return styled