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
    from production61 import BAND3_COSTS

    breakdown = {}

    # Prisoner wages (monthly)
    prisoner_monthly = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)
    breakdown["Prisoner Wages"] = prisoner_monthly

    # Instructor salary (monthly) — hours-based and divided by contracts
    if not customer_covers_supervisors:
        hours_frac = (float(workshop_hours) / 37.5) if workshop_hours > 0 else 0.0
        contracts_safe = max(1, int(contracts))
        instructor_cost = sum((s / 12.0) * hours_frac / contracts_safe for s in supervisor_salaries)
    else:
        instructor_cost = 0.0
    breakdown["Instructor Salary"] = instructor_cost

    # Overheads base — if customer provides instructors, use shadow Band3 on same hours/contract fraction; else instructor cost
    hours_frac = (float(workshop_hours) / 37.5) if workshop_hours > 0 else 0.0
    contracts_safe = max(1, int(contracts))
    if customer_covers_supervisors:
        shadow = BAND3_COSTS.get(region, 42247.81)
        base_overhead = (shadow / 12.0) * hours_frac / contracts_safe
    else:
        base_overhead = instructor_cost

    overhead = base_overhead * 0.61
    breakdown["Overheads (61%)"] = overhead

    # Development charge — show "before" at 20% so we can display a discount line
    dev_rate_before = 0.20
    dev_before = overhead * dev_rate_before

    # Actual dev rate from employment support
    s = (employment_support or "").lower()
    if "both" in s:
        dev_rate_actual = 0.0
    elif "employment on release/rotl" in s or "post release" in s:
        dev_rate_actual = 0.10
    else:
        dev_rate_actual = 0.20
    dev_actual = overhead * dev_rate_actual

    dev_discount = max(0.0, dev_before - dev_actual)

    # Subtotal logic
    # Subtotal BEFORE addl benefit (after applying development discount to get revised_dev)
    revised_dev = dev_actual
    subtotal_after_dev = prisoner_monthly + instructor_cost + overhead + revised_dev

    # Additional benefit discount (ONLY on instructor + overhead + revised development), 10% if Both + benefits
    addl_benefit_discount = 0.0
    if (employment_support == "Both") and additional_benefits:
        discount_base = instructor_cost + overhead + revised_dev
        addl_benefit_discount = discount_base * 0.10

    # Totals
    grand_total = subtotal_after_dev - addl_benefit_discount
    vat = grand_total * 0.20
    grand_total_inc_vat = grand_total + vat

    # Build rows in required order
    rows = []
    rows.append(("Prisoner Wages", prisoner_monthly))
    rows.append(("Instructor Salary", instructor_cost))
    rows.append(("Overheads (61%)", overhead))
    rows.append(("Development Charge (before discount)", dev_before))
    if dev_discount > 0:
        rows.append(("Development charge discount", -dev_discount))
        rows.append(("Revised development charge", revised_dev))
    else:
        rows.append(("Development charge", revised_dev))
    if addl_benefit_discount > 0:
        rows.append(("Additional benefit discount", -addl_benefit_discount))
    rows.append(("Grand Total (£/month)", grand_total))
    rows.append(("VAT (20%)", vat))
    rows.append(("Grand Total + VAT (£/month)", grand_total_inc_vat))

    host_df = pd.DataFrame(rows, columns=["Item", "Amount (£)"])
    host_df["Amount (£)"] = host_df["Amount (£)"].apply(fmt_currency)

    ctx = {
        "date": date.today().isoformat(),
        "region": region,
        "employment_support": employment_support,
        "additional_benefits": additional_benefits,
    }

    return host_df, ctx