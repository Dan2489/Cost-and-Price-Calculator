import streamlit as st

# ---------- Styling ----------
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

# ---------- Sidebar Controls ----------
def draw_sidebar(default_output: int = 100):
    with st.sidebar:
        st.header("Workshop Settings")

        # Lock overheads toggle
        st.checkbox("Lock overheads to highest instructor salary", key="lock_overheads")

        # Instructor allocation slider
        st.slider(
            "Instructor % allocation",
            min_value=0,
            max_value=100,
            value=100,
            step=1,
            key="chosen_pct"
        )

        # Prisoner labour output slider
        st.slider(
            "Planned Output (%)",
            min_value=0,
            max_value=100,
            value=default_output,
            step=1,
            key="planned_output_pct"
        )