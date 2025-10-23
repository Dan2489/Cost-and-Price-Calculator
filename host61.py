import pandas as pd
from datetime import date
from utils61 import fmt_currency

def generate_host_quote(
    *,
    workshop_hours: float,
    num_prisoners: int,
    prisoner_salary: float,
    num_supervisors: int,
    customer_covers_supervisors: bool,
    supervisor_salaries: list[float],
    region: str,
    contracts: int,
    employment_support: str,
    additional_benefits: bool,
):
    """
    Host breakdown:
      - Prisoner Wages (monthly)
      - Instructor cost (monthly)  [hours-based / divided by contracts; 0 if customer provides]
      - Overheads (monthly)        [base = instructor cost; if customer provides -> Band 3 shadow; then * 0.61]
      - Development charge         [on (Instructor + Overheads); rate from employment_support]
      - Development discount       [shown if rate < 20%]
      - Revised development charge
      - Additional benefit discount [10% of (Instructor + Overheads) only when employment_support == "Both" and additional_benefits = True]
      - Subtotal (ex VAT £/month)
      - Total with VAT (£/month)
    """

    # Pull Band 3 shadow costs (annual) from production module
    from production61 import BAND3_COSTS

    # -------------------------------
    # Core monthly components
    # -------------------------------
    # Prisoner wages
    prisoner_monthly = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)

    # Safe helpers
    hours_frac = (float(workshop_hours) / 37.5) if workshop_hours > 0 else 0.0
    contracts_safe = max(1, int(contracts))

    # Instructor cost (monthly): hours-based / divided by contracts
    if not customer_covers_supervisors:
        instructor_cost = sum((float(s) / 12.0) * hours_frac / contracts_safe for s in supervisor_salaries)
    else:
        instructor_cost = 0.0

    # Overheads base (monthly):
    # - if customer provides instructors -> use Band 3 shadow (monthly) * hours_frac / contracts
    # - else -> base = instructor_cost
    if customer_covers_supervisors:
        shadow_annual = float(BAND3_COSTS.get(region, 42247.81))
        overhead_base_monthly = (shadow_annual / 12.0) * hours_frac / contracts_safe
    else:
        overhead_base_monthly = instructor_cost

    # Overheads = base * 0.61
    overhead_monthly = overhead_base_monthly * 0.61

    # -------------------------------
    # Development charge logic (on Instructor + Overheads)
    # -------------------------------
    s = (employment_support or "").lower()
    if "both" in s:
        dev_rate_actual = 0.0
    elif "employment on release/rotl" in s or "pre-release support" in s:
        dev_rate_actual = 0.10
    else:
        dev_rate_actual = 0.20

    # Dev before @ 20% (reference), and actual @ dev_rate_actual
    base_for_dev = instructor_cost + overhead_monthly
    dev_before_monthly = base_for_dev * 0.20
    dev_actual_monthly = base_for_dev * dev_rate_actual
    dev_discount_monthly = max(0.0, dev_before_monthly - dev_actual_monthly)

    # -------------------------------
    # Additional benefit discount
    #   10% of (Instructor cost + Overheads) only if ES == "Both" AND additional_benefits is True
    # -------------------------------
    addl_benefit_monthly = 0.0
    if (employment_support == "Both") and additional_benefits:
        addl_benefit_monthly = (instructor_cost + overhead_monthly) * 0.10

    # -------------------------------
    # Totals
    # -------------------------------
    subtotal_monthly_ex_vat = (
        prisoner_monthly
        + instructor_cost
        + overhead_monthly
        + dev_actual_monthly
        - addl_benefit_monthly
    )
    vat_monthly = subtotal_monthly_ex_vat * 0.20
    total_inc_vat_monthly = subtotal_monthly_ex_vat + vat_monthly

    # -------------------------------
    # Build breakdown (required order)
    # -------------------------------
    rows = []
    rows.append(("Prisoner Wages", prisoner_monthly))
    if instructor_cost > 0:
        rows.append(("Instructor cost", instructor_cost))
    # Always show Overheads row (even if 0, though it's normally > 0)
    rows.append(("Overheads", overhead_monthly))

    # Development: show either a single line (20%) or the before/discount/revised trio
    if dev_rate_actual == 0.20:
        rows.append(("Development charge", dev_actual_monthly))
    else:
        rows.append(("Development charge", dev_before_monthly))
        rows.append(("Development discount", -dev_discount_monthly))
        rows.append(("Revised development charge", dev_actual_monthly))

    # Additional benefit discount (if any)
    if addl_benefit_monthly > 0:
        rows.append(("Additional benefit discount", -addl_benefit_monthly))

    rows.append(("Subtotal (ex VAT £/month)", subtotal_monthly_ex_vat))
    rows.append(("Total with VAT (£/month)", total_inc_vat_monthly))

    host_df = pd.DataFrame(rows, columns=["Item", "Amount (£)"])
    host_df["Amount (£)"] = host_df["Amount (£)"].apply(fmt_currency)

    ctx = {
        "date": date.today().isoformat(),
        "region": region,
        "employment_support": employment_support,
        "additional_benefits": additional_benefits,
    }

    return host_df, ctx