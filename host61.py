import pandas as pd
from datetime import date
from config61 import CFG
from utils61 import fmt_currency

# -------------------------------
# Host cost calculation
# -------------------------------
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
    instructor_allocation: float,
    lock_overheads: bool,
):
    breakdown = {}
    breakdown["Prisoner Wages"] = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)

    # --- Instructor cost ---
    if not customer_covers_supervisors:
        instructor_cost = sum((s / 12.0) * (float(instructor_allocation) / 100.0) for s in supervisor_salaries)
    else:
        instructor_cost = 0.0
    breakdown["Instructor Salary"] = instructor_cost

    # --- Overheads 61% ---
    if not customer_covers_supervisors:
        base_overhead = instructor_cost
    else:
        from production61 import BAND3_COSTS
        shadow = BAND3_COSTS.get(region, 42247.81)
        base_overhead = (shadow / 12.0) * (float(instructor_allocation) / 100.0)
    if lock_overheads and supervisor_salaries:
        base_overhead = (max(supervisor_salaries) / 12.0) * (float(instructor_allocation) / 100.0)

    overhead = base_overhead * 0.61
    breakdown["Overheads (61%)"] = overhead

    # --- Development charge logic ---
    dev_rate = 0.20
    if employment_support in ("Employment on release/RoTL", "Post release"):
        dev_rate = 0.10
    elif employment_support == "Both":
        dev_rate = 0.00

    dev_charge = overhead * dev_rate
    breakdown["Development Charge"] = dev_charge

    # --- Grand total ---
    subtotal = sum(breakdown.values())
    breakdown["Grand Total (£/month)"] = subtotal

    # --- Create DataFrame ---
    rows = [(k, v) for k, v in breakdown.items()]
    host_df = pd.DataFrame(rows, columns=["Item", "Amount (£)"])
    for c in ["Amount (£)"]:
        host_df[c] = host_df[c].apply(fmt_currency)

    # --- Comparison table ---
    comp_df = build_host_comparison(
        num_prisoners=num_prisoners,
        prisoner_salary=prisoner_salary,
        num_supervisors=num_supervisors,
        supervisor_salaries=supervisor_salaries,
        region=region,
        contracts=contracts,
        customer_covers_supervisors=customer_covers_supervisors,
        lock_overheads=lock_overheads,
        employment_support=employment_support,
        instructor_allocation=instructor_allocation,
    )

    ctx = {
        "date": date.today().isoformat(),
        "region": region,
        "employment_support": employment_support,
        "comparison": comp_df,
    }

    return host_df, ctx


# -------------------------------
# Comparison logic for Host
# -------------------------------
def build_host_comparison(
    *,
    num_prisoners: int,
    prisoner_salary: float,
    num_supervisors: int,
    supervisor_salaries: list[float],
    region: str,
    contracts: int,
    customer_covers_supervisors: bool,
    lock_overheads: bool,
    employment_support: str,
    instructor_allocation: float,
):
    from production61 import BAND3_COSTS

    recommended_pct = min(100.0, (float(37.5) / float(37.5)) * (1 / contracts) * 100.0)
    # We'll adjust properly below
    recommended_pct = min(100.0, (float(37.5) / 37.5) * (1 / contracts) * 100.0)
    scenarios = {
        "100%": 100.0,
        "Recommended": recommended_pct,
        "50%": 50.0,
        "25%": 25.0,
    }

    rows = []
    for label, pct in scenarios.items():
        if not customer_covers_supervisors:
            inst_cost = sum((s / 12.0) * (pct / 100.0) for s in supervisor_salaries)
        else:
            inst_cost = 0.0

        if customer_covers_supervisors:
            shadow = BAND3_COSTS.get(region, 42247.81)
            base_overhead = (shadow / 12.0) * (pct / 100.0)
        else:
            base_overhead = inst_cost

        if lock_overheads and supervisor_salaries:
            base_overhead = (max(supervisor_salaries) / 12.0) * (pct / 100.0)

        overhead = base_overhead * 0.61

        # --- Dev charge logic ---
        dev_rate = 0.20
        if employment_support in ("Employment on release/RoTL", "Post release"):
            dev_rate = 0.10
        elif employment_support == "Both":
            dev_rate = 0.00

        dev_charge = overhead * dev_rate

        prisoner_monthly = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)
        total = prisoner_monthly + inst_cost + overhead + dev_charge

        rows.append({
            "Scenario": label,
            "Instructor %": f"{pct:.1f}%",
            "Monthly Total (ex VAT £)": fmt_currency(total),
            "Instructor Cost (£)": fmt_currency(inst_cost),
            "Development Charge (£)": fmt_currency(dev_charge),
            "Overhead (£)": fmt_currency(overhead),
        })

    return pd.DataFrame(rows)