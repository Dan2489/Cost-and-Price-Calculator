from typing import List, Dict, Optional
import math
import datetime as dt
from config61 import CFG

def labour_minutes_budget(num_pris: int, hours: float) -> float:
    return max(0.0, float(num_pris) * float(hours) * 60.0)

def _dev_rate_applied(customer_type: str, dev_rate: float) -> float:
    return dev_rate if customer_type == "Commercial" else 0.0

def calculate_production_contractual(
    items: List[Dict],
    output_pct: int,
    *,
    workshop_hours: float,
    prisoner_salary: float,
    supervisor_salaries: List[float],
    effective_pct: float,
    customer_covers_supervisors: bool,
    region: str,
    customer_type: str,
    dev_rate: float,
    pricing_mode: str,                # "as-is" or "target"
    targets: Optional[List[int]],
    lock_overheads: bool,
    num_prisoners: int,
    contracts_overseen: int,
) -> List[Dict]:

    # Instructor weekly cost (split by contracts)
    if customer_covers_supervisors or len(supervisor_salaries) == 0:
        inst_weekly_total = 0.0
    else:
        share = (effective_pct / 100.0) / max(1, contracts_overseen)
        inst_weekly_total = sum((s / 52.0) * share for s in supervisor_salaries)

    # Overhead base
    if customer_covers_supervisors:
        shadow = CFG.SHADOW_COSTS.get(region, CFG.SHADOW_COSTS["National"])
        overhead_base = (shadow / 52.0) * (effective_pct / 100.0)
    else:
        overhead_base = inst_weekly_total

    if lock_overheads and supervisor_salaries:
        overhead_base = (max(supervisor_salaries) / 52.0) * (effective_pct / 100.0)

    overheads_weekly = overhead_base * 0.61
    dev_weekly_total = overheads_weekly * _dev_rate_applied(customer_type, dev_rate)

    denom = sum(int(it.get("assigned", 0)) * workshop_hours * 60.0 for it in items)
    output_scale = float(output_pct) / 100.0

    results: List[Dict] = []
    for idx, it in enumerate(items):
        name = (it.get("name") or "").strip() or f"Item {idx+1}"