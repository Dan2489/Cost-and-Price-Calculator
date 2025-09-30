# host61.py
# Host monthly breakdown using 61% overheads method and development charge reductions display.

from typing import List, Dict, Tuple
import pandas as pd
from config61 import CFG
from utils61 import overheads_weekly_61, format_currency, development_rate

def generate_host_quote(
    *,
    workshop_hours: float,
    num_prisoners: int,
    prisoner_salary: float,
    num_supervisors: int,
    customer_covers_supervisors: bool,
    supervisor_salaries: List[float],
    effective_pct: float,
    customer_type: str,
    region: str,
    support_option: str,
    lock_overheads: bool,
    apply_vat: bool,
    vat_rate: float,
) -> Tuple[pd.DataFrame, Dict]:
    breakdown: Dict[str, float] = {}

    # Prisoner wages (monthly)
    breakdown["Prisoner wages"] = float(num_prisoners) * float(prisoner_salary) * (52.0 / 12.0)

    # Instructor wages (monthly) — charged only if customer does NOT provide
    inst_monthly = 0.0
    if not customer_covers_supervisors and num_supervisors > 0 and supervisor_salaries:
        inst_monthly = sum((s / 12.0) * (float(effective_pct) / 100.0) for s in supervisor_salaries)
    breakdown["Instructors"] = inst_monthly

    # Overheads (61% of instructor base) — weekly -> monthly
    overheads_weekly, basis = overheads_weekly_61(
        supervisor_salaries=supervisor_salaries,
        customer_covers_supervisors=customer_covers_supervisors,
        region=region,
        effective_pct=effective_pct,
        lock_overheads=lock_overheads,
    )
    overheads_monthly = overheads_weekly * (52.0 / 12.0)
    breakdown["Overheads (61%)"] = overheads_monthly

    # Development charge (Commercial only) with reductions shown
    dev_rate_eff, dev_br = development_rate(customer_type, support_option)
    dev_monthly = overheads_monthly * dev_rate_eff
    dev_base_monthly = overheads_monthly * CFG.DEV_RATE_BASE
    dev_reduction_monthly = dev_base_monthly - dev_monthly  # may be 0

    if customer_type == "Commercial":
        # Display the base, then reductions (red), then revised
        breakdown["Development charge (base 20%)"] = dev_base_monthly
        if dev_reduction_monthly > 1e-9:
            breakdown["Reduction on development charge"] = -dev_reduction_monthly
        breakdown["Revised development charge"] = dev_monthly

    subtotal = sum(breakdown.values())

    vat_amount = subtotal * (float(vat_rate) / 100.0) if apply_vat and customer_type == "Commercial" else 0.0
    grand_total = subtotal + vat_amount

    # Build display rows
    rows = []
    for k, v in breakdown.items():
        rows.append((k, v))
    rows += [("Subtotal", subtotal)]
    if vat_amount:
        rows += [(f"VAT ({float(vat_rate):.1f}%)", vat_amount)]
    rows += [("Grand Total (£/month)", grand_total)]

    host_df = pd.DataFrame(rows, columns=["Item", "Amount (£)"])

    ctx = {
        "overheads_basis": basis,
        "subtotal": subtotal,
        "vat_amount": vat_amount,
        "grand_total": grand_total,
        "dev": {"rate": dev_rate_eff, **dev_br},
    }
    return host_df, ctx

def host_summary_table(df: pd.DataFrame) -> str:
    # Render as HTML with negatives in red and totals bold
    rows_html = []
    for _, row in df.iterrows():
        item = str(row["Item"])
        val = row["Amount (£)"]
        neg_cls = ""
        try:
            neg_cls = " class='neg'" if float(val) < 0 else ""
        except Exception:
            pass
        grand_cls = " class='grand'" if "Grand Total" in item else ""
        rows_html.append(f"<tr{grand_cls}><td>{item}</td><td{neg_cls}>{format_currency(val)}</td></tr>")
    header = "<tr><th>Item</th><th>Amount (£)</th></tr>"
    return f"<table>{header}{''.join(rows_html)}</table>"