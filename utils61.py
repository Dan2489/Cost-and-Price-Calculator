import streamlit as st

# -------------------------------------------------------------------
# Prison → Region mapping
# -------------------------------------------------------------------
PRISON_TO_REGION = {
    "Altcourse": "National", "Ashfield": "National", "Askham Grange": "National",
    "Aylesbury": "National", "Bedford": "National", "Belmarsh": "Inner London",
    "Brixton": "Inner London", "Bronzefield": "Outer London",
    "Coldingley": "Outer London", "Downview": "Outer London",
    "Feltham A": "Outer London", "Feltham B": "Outer London",
    "High Down": "Outer London", "Isis": "Inner London",
    "Pentonville": "Inner London", "Thameside": "Inner London",
    "Wandsworth": "Inner London", "Woodhill": "Inner London",
    "Wormwood Scrubs": "Inner London",
    # default: all others are "National"
}

# -------------------------------------------------------------------
# Instructor pay bands
# -------------------------------------------------------------------
SUPERVISOR_PAY = {
    "Inner London": [
        {"title": "Production Instructor: Band 3", "avg_total": 49203},
        {"title": "Specialist Instructor: Band 4", "avg_total": 55632},
    ],
    "Outer London": [
        {"title": "Production Instructor: Band 3", "avg_total": 45856},
        {"title": "Specialist Instructor: Band 4", "avg_total": 69584},
    ],
    "National": [
        {"title": "Production Instructor: Band 3", "avg_total": 42248},
        {"title": "Specialist Instructor: Band 4", "avg_total": 48969},
    ],
}

# Band 3 shadow costs for when customer provides instructors
BAND3_SHADOW = {
    "Inner London": 49202.70,
    "Outer London": 45855.97,
    "National": 42247.81,
}

# -------------------------------------------------------------------
# GOV.UK CSS styling
# -------------------------------------------------------------------
def inject_govuk_css() -> None:
    st.markdown(
        """
        <style>
          [data-testid="stSidebar"] {
            min-width: 420px !important;
            max-width: 420px !important;
          }
          @media (max-width: 1200px) {
            [data-testid="stSidebar"] {
              min-width: 360px !important;
              max-width: 360px !important;
            }
          }
          :root { --govuk-green: #00703c; --govuk-yellow: #ffdd00; }
          .stButton > button {
            background: var(--govuk-green) !important; color: #fff !important;
            border: 2px solid transparent !important; border-radius: 0 !important;
            font-weight: 600;
          }
          .stButton > button:hover { filter: brightness(0.95); }
          .stButton > button:focus, .stButton > button:focus-visible {
            outline: 3px solid var(--govuk-yellow) !important;
            outline-offset: 0 !important;
            box-shadow: 0 0 0 1px #000 inset !important;
          }
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
          .govuk-heading-l { font-weight: 700; font-size: 1.75rem; line-height: 1.2; }
          .app-header { display:flex; align-items:center; gap:12px; margin: 0.25rem 0 0.75rem 0; }
          .app-header .app-logo { height: 56px; width: auto; display:block; }
          table { width:100%; border-collapse: collapse; margin: 12px 0; }
          th, td { border-bottom: 1px solid #b1b4b6; padding: 8px; text-align: left; }
          th { background: #f3f2f1; } td.neg { color: #d4351c; } tr.grand td { font-weight: 700; }
        </style>
        """,
        unsafe_allow_html=True,
    )

# -------------------------------------------------------------------
# Sidebar (only 3 controls)
# -------------------------------------------------------------------
def draw_sidebar() -> None:
    with st.sidebar:
        st.header("Controls")
        # Lock overheads toggle
        st.checkbox("Lock overheads to highest instructor", key="lock_overheads")
        # Instructor allocation %
        st.slider("Instructor allocation (%)", 0, 100, 100, key="chosen_pct")
        # Prisoner labour output %
        st.slider("Planned Output (%)", 0, 100, 100, key="planned_output_pct")