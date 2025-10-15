# host61.py
from __future__ import annotations
import pandas as pd
from utils61 import fmt_currency


def generate_host_quote(
    workshop_hours: float,
    num_prisoners: int,
    prisoner_salary: float,
    num_supervisors: int,
    customer_covers_supervisors: bool,
    supervisor_salaries: list[float],
    region: str,
    contracts: int,
    employment_support: str,
    instructor_allocation: float,
    lock_overheads: bool,
    benefits_yes: bool = False,
    benefits_discount_pc: float = 0.10,
):
    """
    Build the Host contract quote table with all cost components.
    """

    # --- Base rates ---
    prisoner_monthly = num_prisoners * prisoner_salary * 52.0 / 12.0

    if customer_covers_supervisors:
        instructor_monthly = 0.0
    else:
        total = sum(supervisor_salaries)
        alloc = (workshop_hours / 37.5) * (1.0 / contracts)
        instructor_monthly = (total / 12.0) * alloc

    # Overheads (61%)
    overheads_monthly = instructor_monthly * 0.61

    # Development charge based on Employment Support
    if employment_support == "None":
        dev_rate = 0.20
    elif employment_support in ("Employment on release/RoTL", "Post release"):
        dev_rate = 0.10
    else:
        dev_rate = 0.0
    dev_charge_monthly = overheads_monthly * dev_rate

    # Revised total before any benefit reduction
    subtotal = prisoner_monthly + instructor_monthly + overheads_monthly + dev_charge_monthly

    # Development charge reduction (illustrative)
    dev_reduction = dev_charge_monthly * 0.0  # placeholder for later adjustment

    # Additional benefit discount (10%) if applicable and support == Both
    benefits_reduction = 0.0
    if benefits_yes and employment_support == "Both":
        benefits_reduction = instructor_monthly * benefits_discount_pc

    revised_dev_charge = dev_charge_monthly - dev_reduction
    grand_total = subtotal - dev_reduction - benefits_reduction
    vat_amount = grand_total * 0.20
    grand_total_inc_vat = grand_total + vat_amount

    # --- Build table ---
    rows = [
        {"Item": "Prisoner Wages", "Amount (£)": fmt_currency(prisoner_monthly)},
    ]

    if instructor_monthly > 0:
        rows.append({"Item": "Instructor Salary", "Amount (£)": fmt_currency(instructor_monthly)})

    if overheads_monthly > 0:
        rows.append({"Item": "Overheads", "Amount (£)": fmt_currency(overheads_monthly)})

    if dev_charge_monthly > 0:
        rows.append({"Item": "Development charge", "Amount (£)": fmt_currency(dev_charge_monthly)})

    if dev_reduction > 0:
        rows.append({"Item": "Development charge reduction", "Amount (£)": f"<span style='color:red'>{fmt_currency(dev_reduction)}</span>"})

    if revised_dev_charge > 0:
        rows.append({"Item": "Revised development charge", "Amount (£)": fmt_currency(revised_dev_charge)})

    if benefits_reduction > 0:
        rows.append({"Item": "Additional Benefits Reduction", "Amount (£)": f"<span style='color:red'>{fmt_currency(benefits_reduction)}</span>"})

    rows += [
        {"Item": "Subtotal", "Amount (£)": fmt_currency(subtotal)},
        {"Item": "Grand Total", "Amount (£)": fmt_currency(grand_total)},
        {"Item": "VAT (20%)", "Amount (£)": fmt_currency(vat_amount)},
        {"Item": "Grand Total inc VAT", "Amount (£)": fmt_currency(grand_total_inc_vat)},
    ]

    df = pd.DataFrame(rows)

    context = {
        "prisoner_monthly": prisoner_monthly,
        "instructor_monthly": instructor_monthly,
        "overheads_monthly": overheads_monthly,
        "dev_charge_monthly": dev_charge_monthly,
        "dev_reduction": dev_reduction,
        "benefits_reduction": benefits_reduction,
        "revised_dev_charge": revised_dev_charge,
        "subtotal": subtotal,
        "grand_total": grand_total,
        "vat_amount": vat_amount,
        "grand_total_inc_vat": grand_total_inc_vat,
    }

    return df, context