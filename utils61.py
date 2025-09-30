# utils61.py
import streamlit as st

# -----------------------------
# CSS Styling
# -----------------------------
def inject_govuk_css() -> None:
    st.markdown(
        """
        <style>
          /* Sidebar: slimmer for mobile usability */
          [data-testid="stSidebar"] {
            min-width: 260px !important;
            max-width: 260px !important;
          }
          @media (max-width: 1200px) {
            [data-testid="stSidebar"] {
              min-width: 220px !important;
              max-width: 220px !important;
            }
          }

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

          /* Headers */
          .govuk-heading-l { font-weight: 700; font-size: 1.75rem; line-height: 1.2; }

          /* Tables */
          table { width:100%; border-collapse: collapse; margin: 12px 0; }
          th, td { border-bottom: 1px solid #b1b4b6; padding: 8px; text-align: left; }
          th { background: #f3f2f1; }
          td.neg { color: #d4351c; }
          tr.grand td { font-weight: 700; }

          /* Boxed sections */
          .boxed {
            border: 1px solid #b1b4b6;
            border-radius: 6px;
            padding: 16px;
            margin-top: 8px;
          }
        </style>
        """,
        unsafe_allow_html=True
    )

# -----------------------------
# Currency formatting
# -----------------------------
def fmt_currency(v) -> str:
    try:
        return f"£{float(v):,.2f}"
    except Exception:
        return ""

# -----------------------------
# Sidebar Controls
# -----------------------------
def sidebar_controls() -> dict:
    with st.sidebar:
        st.header("Controls")

        instructor_pct = st.slider("Instructor allocation (%)", 0, 100, 100)
        prisoner_output = st.slider("Prisoner labour output (%)", 0, 100, 100)
        lock_overheads = st.checkbox("Lock overheads to highest instructor salary")

    return {
        "instructor_pct": instructor_pct,
        "prisoner_output": prisoner_output,
        "lock_overheads": lock_overheads,
    }