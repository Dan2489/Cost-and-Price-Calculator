import streamlit as st

# ------------------------
# GOV.UK styling
# ------------------------
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
          :root {
            --govuk-green: #00703c;
            --govuk-yellow: #ffdd00;
          }
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
          table { width:100%; border-collapse: collapse; margin: 12px 0; }
          th, td { border-bottom: 1px solid #b1b4b6; padding: 8px; text-align: left; }
          th { background: #f3f2f1; }
          td.neg { color: #d4351c; }
          tr.grand td { font-weight: 700; }
        </style>
        """,
        unsafe_allow_html=True
    )

# ------------------------
# Prison → Region mapping
# ------------------------
PRISON_TO_REGION = {
    "Altcourse": "National", "Ashfield": "National", "Askham Grange": "National",
    "Aylesbury": "National", "Bedford": "National", "Belmarsh": "Inner London",
    "Brixton": "Inner London", "Liverpool": "National", "Manchester": "National",
    "Pentonville": "Inner London", "Wandsworth": "Inner London",
    # … keep full list from your tariff61.py
}

# ------------------------
# Instructor pay bands
# ------------------------
SUPERVISOR_PAY = {
    "Inner London": [
        {"title": "Production Instructor: Band 3", "avg_total": 49203},
        {"title": "Specialist Instructor: Band 4", "avg_total": 55632},
    ],
    "Outer London": [
        {"title": "Production Instructor: Band 3", "avg_total": 45856},
        {"title": "Prison Officer Specialist - Instructor: Band 4", "avg_total": 69584},
    ],
    "National": [
        {"title": "Production Instructor: Band 3", "avg_total": 42248},
        {"title": "Prison Officer Specialist - Instructor: Band 4", "avg_total": 48969},
    ],
}

# ------------------------
# Sidebar controls
# ------------------------
def draw_sidebar_controls(recommended_pct: float, chosen_pct: float, prisoner_salary: float):
    with st.sidebar:
        st.header("Adjust Settings")

        lock_overheads = st.checkbox(
            "Lock overheads to highest instructor cost",
            value=st.session_state.get("lock_overheads", False),
        )
        st.session_state["lock_overheads"] = lock_overheads

        chosen_pct = st.slider(
            "Adjust instructor % allocation",
            min_value=0,
            max_value=100,
            value=int(chosen_pct),
            step=1,
        )

        prisoner_salary = st.slider(
            "Prisoner labour rate (£/week)",
            min_value=0.0,
            max_value=50.0,
            value=float(prisoner_salary),
            step=0.5,
        )

        return lock_overheads, chosen_pct, prisoner_salary

# ------------------------
# Backwards-compatible alias
# ------------------------
def draw_sidebar(*args, **kwargs):
    """Alias so existing code calling draw_sidebar(...) still works"""
    return draw_sidebar_controls(*args, **kwargs)