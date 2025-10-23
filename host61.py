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
    Host quote calculation.

    Rules implemented:
    - Instructor cost is time-proportioned by (workshop_hours/37.5) and divided by number of contracts.
    - If customer provides instructors -> Instructor cost = 0 (but overhead base uses Band 3 shadow cost).
    - Overheads = 61% of the overhead base (base = instructor cost unless customer provides, then base = Band 3 shadow).
    - Development charge is on (Instructor cost + Overheads), with rate by Employment Support:
        None -> 20%; Employment on release/RoTL or Post release -> 10%; Both -> 0%.
      If rate < 20%, show before/discount/revised lines; otherwise show single "Development charge".
    - Additional benefit discount (if Employment Support == "Both" and additional_benefits is True) = 10% of Instructor cost.
      Applied after development and shown after development lines.
    """

    from production61 import BAND3_COSTS

    # -------------------------------
    # Core monthly components
    # -------------------------------
    # Prisoner wages (monthly)
    prisoner_monthly = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)

    # Instructor cost (monthly) — time-proportioned by hours and contracts
    if not customer_covers_supervisors:
        hours_frac = (float(workshop_hours) / 37.5) if workshop_hours > 0 else 0.0
        contracts_safe = max(1, int(contracts))
        instructor_cost = sum((s / 12.0) * hours_frac / contracts_safe for s in supervisor_salaries)
    else:
        instructor_cost = 0.0

    # Overheads base: if customer provides instructors, use Band 3 SHADOW for region; else use actual instructor cost
    hours_frac = (float(workshop_hours) / 37.5) if workshop_hours > 0 else 0.0
    contracts_safe = max(1, int(contracts))
    if customer_covers_supervisors:
        shadow = float(BAND3_COSTS.get(region, 42247.81))
        base_overhead = (shadow / 12.0) * hours_frac / contracts_safe
    else:
        base_overhead = instructor_cost

    # Overheads (61%)
    overhead = base_overhead * 0.61

    # -------------------------------
    # Development charge on (Instructor cost + Overheads)
    # -------------------------------
    s = (employment_support or "").lower()
    if "both" in s:
        dev_rate_actual = 0.0
    elif "employment on release/rotl" in s or "post release" in s:
        dev_rate_actual = 0.10
    else:
        dev_rate_actual = 0.20

    dev_base = instructor_cost + overhead
    dev_before = dev_base * 0.20
    dev_actual = dev_base * dev_rate_actual
    dev_discount = max(0.0, dev_before - dev_actual)

    # -------------------------------
    # Subtotal before any Additional benefit discount
    # -------------------------------
    subtotal_before_benefits = prisoner_monthly + instructor_cost + overhead + dev_actual

    # -------------------------------
    # Additional benefit discount (ONLY when Employment Support == "Both")
    # 10% of Instructor cost (monthly). Listed and applied AFTER development.
    # -------------------------------
    addl_benefit_discount = 0.0
    if (employment_support == "Both") and additional_benefits and instructor_cost > 0:
        addl_benefit_discount = instructor_cost * 0.10

    # Final totals
    grand_total = subtotal_before_benefits - addl_benefit_discount
    vat = grand_total * 0.20
    grand_total_inc_vat = grand_total + vat

    # -------------------------------
    # Build breakdown (required order)
    # -------------------------------
    rows: list[tuple[str, float]] = []
    rows.append(("Prisoner Wages", prisoner_monthly))
    if instructor_cost > 0:
        rows.append(("Instructor cost", instructor_cost))  # label fixed
    rows.append(("Overheads", overhead))  # no "(61%)" in label

    # Development lines:
    if dev_rate_actual == 0.20:
        rows.append(("Development charge", dev_actual))
    else:
        rows.append(("Development Charge (before discount)", dev_before))
        rows.append(("Development charge discount", -dev_discount))
        rows.append(("Revised development charge", dev_actual))

    # Additional benefit discount (after development)
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