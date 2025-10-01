# utils61.py
import streamlit as st

def inject_govuk_css() -> None:
    st.markdown(
        """
        <style>
          /* Responsive Sidebar */
          @media (min-width: 1200px) {
            [data-testid="stSidebar"] {
              width: 350px !important;
            }
          }
          @media (max-width: 768px) {
            [data-testid="stSidebar"] {
              width: auto !important;
              min-width: unset !important;
              max-width: unset !important;
            }
          }

          /* GOV.UK colours */
          :root {
            --govuk-green: #00703c;
            --govuk-yellow: #ffdd00;
          }

          /* Buttons */
          .stButton > button {
            background: var(--govuk-green) !important;
            color: #fff !important;
            border: 2px solid transparent !important;
            border-radius: 0 !important;
            font-weight: 600;
          }
          .stButton > button:hover { filter: brightness(0.95); }
          .stButton > button:focus, .stButton > button:focus-visible {
            outline: 3px solid var(--govuk-yellow) !important;
            outline-offset: 0 !important;
            box-shadow: 0 0 0 1px #000 inset !important;
          }

          /* Sliders */
          [data-testid="stSlider"] [role="slider"] {
            background: var(--govuk-green) !important;
            border: 2px solid var(--govuk-green) !important;
            box-shadow: none !important;
          }
          [data-testid="stSlider"] [role="slider"]:focus,
          [data-testid="stSlider"] [role="slider"]:focus-visible {
            outline: 3px solid var(--govuk-yellow) !important;
            outline-offset: 0 !important;
            box-shadow: 0 0 0 1px #000 inset !important;
          }
          [data-testid="stSlider"] div[aria-hidden="true"] > div > div {
            background-color: var(--govuk-green) !important;
          }

          /* Centered results tables */
          .results-table {
            max-width: 900px;
            margin: 1rem auto;
          }
          .results-table table {
            width: 100%;
            border-collapse: collapse;
            margin: 12px 0;
          }
          .results-table th, .results-table td {
            border-bottom: 1px solid #b1b4b6;
            padding: 8px;
            text-align: left;
          }
          .results-table th { background: #f3f2f1; }
          .results-table td.neg { color: #d4351c; }
          .results-table tr.total td { font-weight: 700; }
        </style>
        """,
        unsafe_allow_html=True
    )


def fmt_currency(v) -> str:
    try:
        return f"£{float(v):,.2f}"
    except Exception:
        return ""


def sidebar_controls(global_output_default: int, workshop_hours: float, contracts: int):
    """Sidebar with instructor allocation + prisoner output + lock overheads"""
    with st.sidebar:
        st.header("Controls")
        lock_overheads = st.checkbox("Lock overheads to highest instructor salary", value=False)

        # Instructor allocation slider
        rec = 0.0
        if workshop_hours > 0 and contracts > 0:
            rec = min(100.0, (workshop_hours / 37.5) * (1 / contracts) * 100.0)
        instructor_pct = st.slider("Instructor allocation (%)", 0, 100, int(round(rec)) if rec > 0 else 100)
        if rec > 0:
            st.caption(f"Recommended: {rec:.0f}%")

        # Prisoner output slider
        prisoner_output = st.slider("Prisoner labour output (%)", 0, 100, global_output_default)

        return lock_overheads, instructor_pct, prisoner_output


def render_summary_table(rows, dev_reduction: bool = False) -> str:
    """Render a breakdown table as HTML (wrapped in results-table container)."""
    body = []
    for item, val in rows:
        val_str = fmt_currency(val) if val is not None else ""
        cls = ""
        if dev_reduction and "reduction" in str(item).lower():
            cls = " class='neg'"
        if "Total" in str(item):
            body.append(f"<tr class='total'><td>{item}</td><td>{val_str}</td></tr>")
        else:
            body.append(f"<tr><td>{item}</td><td{cls}>{val_str}</td></tr>")
    return f"<div class='results-table'><table><tr><th>Item</th><th>Amount (£)</th></tr>{''.join(body)}</table></div>"