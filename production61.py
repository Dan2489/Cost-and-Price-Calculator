from typing import List, Dict, Optional
import pandas as pd

# ---------- Core contractual calculation ----------
def calculate_production_contractual(
    items: List[Dict],
    output_pct: int,
    *,
    workshop_hours: float,
    prisoner_salary: float,
    supervisor_salaries: List[float],
    effective_pct: float,
    customer_covers_supervisors: bool,
    customer_type: str,
    apply_vat: bool,
    vat_rate: float,
    instructor_allocation_pct: float,
    lock_overheads: bool,
    dev_rate: float,
) -> List[Dict]:
    """
    Core calculation for production costs with 61% overhead model.
    """
    output_scale = float(output_pct) / 100.0

    # Instructor costs
    inst_weekly_total = sum((s / 52.0) * (float(effective_pct) / 100.0) for s in supervisor_salaries)
    prisoner_weekly_total = prisoner_salary

    # Overheads = 61% of instructor costs
    if lock_overheads and supervisor_salaries:
        highest = max(supervisor_salaries)
        base_for_overheads = (highest / 52.0) * (float(effective_pct) / 100.0)
    else:
        base_for_overheads = inst_weekly_total

    overheads_weekly_total = base_for_overheads * 0.61

    # Dev charge only applies if Commercial
    if customer_type == "Commercial":
        dev_weekly_total = overheads_weekly_total * float(dev_rate)
    else:
        dev_weekly_total = 0.0

    results: List[Dict] = []
    grand_total = 0.0

    for idx, it in enumerate(items):
        name = (it.get("name") or "").strip() or f"Item {idx+1}"
        mins_per_unit = float(it.get("minutes", 0))
        pris_required = int(it.get("required", 1))
        pris_assigned = int(it.get("assigned", 0))

        # Capacity calc
        if pris_assigned > 0 and mins_per_unit > 0 and pris_required > 0 and workshop_hours > 0:
            cap_100 = (pris_assigned * workshop_hours * 60.0) / (mins_per_unit * pris_required)
        else:
            cap_100 = 0.0
        capacity_units = cap_100 * output_scale

        # Weekly cost per item share (by assignment share)
        denom = sum(int(it.get("assigned", 0)) * workshop_hours * 60.0 for it in items)
        share = ((pris_assigned * workshop_hours * 60.0) / denom) if denom > 0 else 0.0

        prisoner_weekly_item = pris_assigned * prisoner_weekly_total
        inst_weekly_item = inst_weekly_total * share if not customer_covers_supervisors else 0.0
        overheads_weekly_item = overheads_weekly_total * share
        dev_weekly_item = dev_weekly_total * share
        weekly_cost_item = prisoner_weekly_item + inst_weekly_item + overheads_weekly_item + dev_weekly_item

        units_for_pricing = capacity_units
        unit_cost_ex_vat = (weekly_cost_item / units_for_pricing) if units_for_pricing > 0 else None
        unit_price_ex_vat = unit_cost_ex_vat
        if unit_price_ex_vat is not None and (customer_type == "Commercial" and apply_vat):
            unit_price_inc_vat = unit_price_ex_vat * (1 + (float(vat_rate) / 100.0))
        else:
            unit_price_inc_vat = unit_price_ex_vat

        monthly_total = (units_for_pricing * unit_cost_ex_vat * 52 / 12) if unit_cost_ex_vat else 0.0
        grand_total += monthly_total

        results.append({
            "Item": name,
            "Capacity (units/week)": int(round(capacity_units)) if capacity_units > 0 else 0,
            "Units/week": int(round(units_for_pricing)) if units_for_pricing > 0 else 0,
            "Unit Cost (£)": unit_cost_ex_vat,
            "Unit Price ex VAT (£)": unit_price_ex_vat,
            "Unit Price inc VAT (£)": unit_price_inc_vat,
            "Monthly Total (£)": monthly_total,
        })

    results.append({
        "Item": "Grand Total",
        "Capacity (units/week)": "",
        "Units/week": "",
        "Unit Cost (£)": "",
        "Unit Price ex VAT (£)": "",
        "Unit Price inc VAT (£)": "",
        "Monthly Total (£)": grand_total,
    })

    return results


# ---------- Wrappers so newapp61.py imports still work ----------
def calculate_production_costs(*args, **kwargs):
    return calculate_production_contractual(*args, **kwargs)


def production_summary_table(results: List[Dict]):
    df = pd.DataFrame(results)
    return df