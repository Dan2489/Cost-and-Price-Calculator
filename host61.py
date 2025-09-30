# host61.py
# Host monthly breakdown based on Instructor costs (overheads fixed at 61%)

from typing import List, Dict, Tuple
import pandas as pd

from config61 import CFG
from tariff61 import BAND3_SHADOW

def generate_host_quote(
    *,
    workshop_hours: float,
    num_prisoners: int,
    prisoner_salary: float,
    num_instructors: int,
    customer_covers_instructors: bool,
    instructor_salaries: List[float],
    effective_pct: float,
    customer_type: str,
    apply_vat: bool,
    vat_rate: float,
) -> Tuple[pd.DataFrame, Dict]:
    breakdown: Dict[str, float] = {}

    # Prisoner wages (monthly)
    breakdown["Prisoner wages"] = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)

    # Instructor costs
    instructor_cost = 0.0
    if not customer_covers_instructors:
        instructor_cost = sum((s / 12.0) * (float(effective_pct) / 100.0) for s in instructor_salaries)
        breakdown["Instructors"] = instructor_cost
        overheads_subtotal = instructor_cost * 0.61
    else:
        # Shadow cost: Band 3 values (salary excluded, only overheads at 61%)
        shadow_monthly = BAND3_SHADOW["monthly"]
        breakdown["Shadow Instructor Band 3 (overheads only)"] = shadow_monthly * 0.61
        overheads_subtotal = shadow_monthly * 0.61

    breakdown["Overheads (61%)"] = overheads_subtotal

    # Development charge (Commercial only)
    dev_rate = 0.20 if customer_type == "Commercial" else 0.0
    breakdown["Development charge (applied)"] = overheads_subtotal * dev_rate

    subtotal = sum(breakdown.values())

    # VAT always applied
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

# config61.py
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class AppConfig:
    DAYS_PER_MONTH: float = 365.0 / 12.0 # ≈30.42
    FULL_UTILISATION_WEEK: float = 37.5 # reference week for scaling
    GLOBAL_OUTPUT_DEFAULT: int = 100 # slider default

CFG = AppConfig()

def hours_scale(hours_open_per_week: float, full_week: Optional[float] = None) -> float:
    """Scale factor for hours open vs full utilisation week."""
    try:
        h = float(hours_open_per_week)
        f = float(full_week if full_week is not None else CFG.FULL_UTILISATION_WEEK)
        if f <= 0:
            return 1.0
        return max(0.0, h / f)
    except Exception:
        return 1.0
