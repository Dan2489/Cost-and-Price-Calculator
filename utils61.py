# utils61.py
# Shared helpers (formatting, CSS, sidebar controls, overheads calc, development logic)

from __future__ import annotations
from typing import List, Tuple, Dict
import streamlit as st
from config61 import CFG

# ------------------ Aesthetics ------------------
def inject_govuk_css() -> None:
    st.markdown("""
    <style>
      [data-testid="stSidebar"] { min-width: 420px !important; max-width: 420px !important; }
      @media (max-width: 1200px) { [data-testid="stSidebar"] { min-width: 360px !important; max-width: 360px !important; } }
      :root { --govuk-green:#00703c; --govuk-yellow:#ffdd00; }
      .stButton > button {
        background: var(--govuk-green) !important; color:#fff !important; border:2px solid transparent !important;
        border-radius:0 !important; font-weight:600;
      }
      .stButton > button:hover { filter: brightness(0.95); }
      .stButton > button:focus { outline:3px solid var(--govuk-yellow) !important; outline-offset:0 !important; box-shadow:0 0 0 1px #000 inset !important; }
      [data-testid="stSlider"] [role="slider"] { background:var(--govuk-green) !important; border:2px solid var(--govuk-green) !important; box-shadow:none !important; }
      [data-testid="stSlider"] [role="slider"]:focus { outline:3px solid var(--govuk-yellow) !important; outline-offset:0 !important; box-shadow:0 0 0 1px #000 inset !important; }
      [data-testid="stSlider"] div[aria-hidden="true"] > div > div { background-color:var(--govuk-green) !important; }
      .govuk-heading-l { font-weight:700; font-size:1.75rem; line-height:1.2; }
      table { width:100%; border-collapse:collapse; margin:12px 0; }
      th,td{ border-bottom:1px solid #b1b4b6; padding:8px; text-align:left; }
      th{ background:#f3f2f1; } td.neg{ color:#d4351c; } tr.grand td{ font-weight:700; }
      .smallnote{ color:#505a5f; font-size:0.9rem; }
      .red { color:#d4351c; font-weight:600; }
    </style>
    """, unsafe_allow_html=True)

def format_currency(v) -> str:
    try:
        return f"£{float(v):,.2f}"
    except Exception:
        return ""

# ------------------ Sidebar ------------------
def sidebar_controls(default_output_pct: int) -> Tuple[bool, int, int]:
    with st.sidebar:
        st.header("Controls")
        lock = st.checkbox("Lock overheads to highest instructor cost", key="lock_overheads", value=False)
        eff = st.slider("Adjust instructor % allocation", 0, 100, int(st.session_state.get("effective_pct", 0)),
                        help="Percentage of each instructor’s time allocated to this workshop.")
        st.session_state["effective_pct"] = eff
        out = st.slider("Planned prisoner output (%)", 0, 100,
                        int(st.session_state.get("planned_output_pct", default_output_pct)),
                        help="Scales planned capacity used for production.")
        st.session_state["planned_output_pct"] = out
    return lock, eff, out

# ------------------ Labour minutes ------------------
def labour_minutes_budget(num_pris: int, hours: float) -> float:
    try:
        return max(0.0, float(num_pris) * float(hours) * 60.0)
    except Exception:
        return 0.0

# ------------------ Overheads (61% method) ------------------
def overheads_weekly_61(
    *,
    supervisor_salaries: List[float],
    customer_covers_supervisors: bool,
    region: str,
    effective_pct: float,
    lock_overheads: bool,
) -> Tuple[float, Dict]:
    """
    Returns (overheads_weekly, detail dict).
    Overheads = 61% of chosen weekly instructor base.
    - If customer provides instructors -> use Band3 shadow cost for region (salary not shown/charged).
    - Else -> base on selected instructor salaries.
      If lock_overheads==True, base on the highest single instructor salary (still charge all wages separately).
    """
    pct = float(effective_pct) / 100.0
    if customer_covers_supervisors:
        # shadow, salary not shown in summary
        annual = CFG.SHADOW_COSTS.get(region, CFG.SHADOW_COSTS["National"])
        base_weekly = (annual / 52.0) * pct
        basis = f"61% of Band 3 shadow ({region})"
    else:
        if lock_overheads and supervisor_salaries:
            annual = max(supervisor_salaries)
            base_weekly = (annual / 52.0) * pct
            basis = "61% of highest instructor"
        else:
            # Base the overheads on the total instructor salary pool (consistent with your previous model)
            annual = sum(supervisor_salaries)
            base_weekly = (annual / 52.0) * pct
            basis = "61% of total instructor cost"
    overheads = base_weekly * 0.61
    return overheads, {"basis": basis, "base_weekly": base_weekly}

# ------------------ Development charge logic ------------------
def development_rate(customer_type: str, support: str) -> Tuple[float, Dict]:
    """
    Returns (dev_rate, breakdown dict). Only applies to Commercial.
    support options:
      "None" -> 20%
      "Employment on release/RoTL" -> 10% (deduct 10)
      "Post release" -> 10% (deduct 10)
      "Both" -> 0%  (deduct 20)
    Another Government Department -> 0%
    """
    if customer_type == "Another Government Department":
        return 0.0, {"base": 0.0, "reduction": 0.0, "revised": 0.0}

    base = CFG.DEV_RATE_BASE
    if support == "None":
        revised = base
        reduction = 0.0
    elif support in ("Employment on release/RoTL", "Post release"):
        revised = max(0.0, base - 0.10)
        reduction = base - revised
    else:  # "Both"
        revised = 0.0
        reduction = base
    return revised, {"base": base, "reduction": reduction, "revised": revised}