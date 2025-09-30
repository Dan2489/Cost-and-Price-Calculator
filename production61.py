from typing import List, Dict, Optional
from config61 import CFG

# Band 3 shadow annual salaries for overheads when customer provides instructors
BAND3_SHADOW = {
    "Outer London": 45855.97,
    "Inner London": 49202.70,
    "National": 42247.81,
}

def labour_minutes_budget(num_pris: int, hours: float) -> float:
    return max(0.0, float(num_pris) * float(hours) * 60.0)

def _applied_dev_rate(customer_type: str, support: str) -> float:
    # Commercial: base 20% minus reductions; AGD: 0%
    if customer_type != "Commercial":
        return 0.0
    if support in ("Employment on release/RoTL", "Post release"):
        return 0.10
    if support == "Both":
        return 0.00
    return 0.20

def calculate_production_contractual(
    items: List[Dict],
    output_pct: int,
    *,
    workshop_hours: float,
    prisoner_salary: float,
    supervisor_salaries: List[float],
    effective_pct: float,
    customer_covers_supervisors: bool,
    customer_type: str,     # "Commercial" or "Another Government Department"
    support: str,           # dev reductions input; used to pick applied % (not shown)
    apply_vat: bool,
    vat_rate: float,
    num_prisoners: int,
    region: str,
    lock_overheads: bool,
    pricing_mode: str = "as-is",
    targets: Optional[List[int]] = None,
) -> List[Dict]:
    """
    Returns per-item rows. Dev charge is included in costs, but not shown.
    """
    output_scale = float(output_pct) / 100.0

    # Instructor weekly cost (if MoJ pays)
    inst_weekly_total = 0.0
    if not customer_covers_supervisors and supervisor_salaries:
        inst_weekly_total = sum((s / 52.0) * (float(effective_pct) / 100.0) for s in supervisor_salaries)

    # Overheads weekly (61% of instructor)
    if customer_covers_supervisors:
        band3 = BAND3_SHADOW.get(region, BAND3_SHADOW["National"])
        overheads_weekly = (band3 * CFG.OVERHEAD_PCT) / 52.0
    else:
        if lock_overheads and supervisor_salaries:
            overheads_weekly = (max(supervisor_salaries) * CFG.OVERHEAD_PCT) / 52.0
        else:
            overheads_weekly = inst_weekly_total * CFG.OVERHEAD_PCT

    # Applied development weekly (Commercial only)
    dev_rate_applied = _applied_dev_rate(customer_type, support)
    dev_weekly_total = overheads_weekly * dev_rate_applied

    denom = sum(int(it.get("assigned", 0)) * workshop_hours * 60.0 for it in items)

    results: List[Dict] = []
    for idx, it in enumerate(items):
        name = (it.get("name") or "").strip() or f"Item {idx+1}"
        mins_per_unit = float(it.get("minutes", 0))
        pris_required = int(it.get("required", 1))
        pris_assigned = int(it.get("assigned", 0))

        # Capacity
        if pris_assigned > 0 and mins_per_unit > 0 and pris_required > 0 and workshop_hours > 0:
            cap_100 = (pris_assigned * workshop_hours * 60.0) / (mins_per_unit * pris_required)
        else:
            cap_100 = 0.0
        capacity_units = cap_100 * output_scale

        # Share for overheads/dev/instructor by available minutes
        share = ((pris_assigned * workshop_hours * 60.0) / denom) if denom > 0 else 0.0

        # Weekly cost components for this item
        prisoner_weekly_item   = pris_assigned * prisoner_salary
        inst_weekly_item       = inst_weekly_total * share
        overheads_weekly_item  = overheads_weekly * share
        dev_weekly_item        = dev_weekly_total * share
        weekly_cost_item       = prisoner_weekly_item + inst_weekly_item + overheads_weekly_item + dev_weekly_item

        # Units for pricing
        if pricing_mode == "target":
            tgt = 0
            if targets and idx < len(targets):
                try: tgt = int(targets[idx])
                except Exception: tgt = 0
            units_for_pricing = float(tgt)
        else:
            units_for_pricing = capacity_units

        # Unit costs/prices
        if units_for_pricing > 0:
            unit_cost_ex_vat = weekly_cost_item / units_for_pricing
        else:
            unit_cost_ex_vat = None

        unit_price_ex_vat = unit_cost_ex_vat
        if unit_price_ex_vat is not None and apply_vat and customer_type == "Commercial":
            unit_price_inc_vat = unit_price_ex_vat * (1 + (float(vat_rate) / 100.0))
        else:
            unit_price_inc_vat = unit_price_ex_vat

        # Monthly totals (ex & inc VAT)
        monthly_ex = (units_for_pricing * unit_price_ex_vat * 52.0 / 12.0) if unit_price_ex_vat is not None else None
        monthly_inc = (units_for_pricing * unit_price_inc_vat * 52.0 / 12.0) if unit_price_inc_vat is not None else None

        results.append({
            "Item": name,
            "Output %": int(output_pct),
            "Capacity (units/week)": int(round(capacity_units)) if capacity_units > 0 else 0,
            "Units/week": int(round(units_for_pricing)) if units_for_pricing > 0 else 0,
            "Unit Cost (£)": unit_cost_ex_vat,
            "Unit Price ex VAT (£)": unit_price_ex_vat,
            "Unit Price inc VAT (£)": unit_price_inc_vat,
            "Monthly Total (ex VAT £)": monthly_ex,
            "Monthly Total (inc VAT £)": monthly_inc,
        })
    return results