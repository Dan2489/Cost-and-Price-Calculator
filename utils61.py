# utils61.py
import streamlit as st

# ---------- Styling ----------
def inject_govuk_css():
    """Inject GOV.UK-style CSS overrides."""
    st.markdown(
        """
        <style>
          /* Sidebar width */
          [data-testid="stSidebar"] {
            min-width: 320px !important;
            max-width: 320px !important;
          }

          /* GOV.UK colours */
          :root {
            --govuk-green: #00703c;
            --govuk-yellow: #ffdd00;
            --govuk-red: #d4351c;
          }

          /* Buttons */
          .stButton > button {
            background: var(--govuk-green) !important;
            color: #fff !important;
            border: none !important;
            border-radius: 0 !important;
            font-weight: 600;
          }
          .stButton > button:hover { filter: brightness(0.95); }

          /* Tables */
          table.govuk-table {
            width: 100%;
            border-collapse: collapse;
            margin: 1rem 0;
          }
          table.govuk-table th, table.govuk-table td {
            border-bottom: 1px solid #b1b4b6;
            padding: 6px 8px;
            text-align: left;
          }
          table.govuk-table th {
            background: #f3f2f1;
          }
          table.govuk-table td.neg {
            color: var(--govuk-red);
          }
          table.govuk-table tr.total td {
            font-weight: bold;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

# ---------- Helpers ----------
def fmt_currency(v) -> str:
    """Format a number as £ with commas and 2dp."""
    try:
        return f"£{float(v):,.2f}"
    except Exception:
        return ""

def recommended_instructor_allocation(workshop_hours: float, contracts: int) -> float:
    """Recommended instructor % based on 37.5h baseline and contracts."""
    if workshop_hours <= 0 or contracts <= 0:
        return 0.0
    return round((workshop_hours / 37.5) * (1 / contracts) * 100, 1)

def render_summary_table(rows: list[tuple[str, float]], dev_reduction: bool = False) -> str:
    """Render a GOV.UK-style summary table with optional dev charge reduction in red."""
    html = ["<table class='govuk-table'>"]
    html.append("<tr><th>Item</th><th>Amount (£)</th></tr>")
    for label, val in rows:
        css = ""
        if dev_reduction and "reduction" in label.lower():
            css = " class='neg'"
        elif "total" in label.lower():
            css = " class='total'"
        html.append(f"<tr><td>{label}</td><td{css}>{fmt_currency(val)}</td></tr>")
    html.append("</table>")
    return "".join(html)

# ---------- Sidebar controls ----------
def sidebar_controls(default_output: int):
    """Render sidebar sliders and switches."""
    with st.sidebar:
        st.header("Controls")
        lock_overheads = st.checkbox("Lock overheads to highest instructor salary", value=False)
        instructor_pct = st.slider("Instructor allocation (%)", 0, 100, 100)
        prisoner_output = st.slider("Prisoner labour output (%)", 0, 100, default_output)
    return lock_overheads, instructor_pct, prisoner_output