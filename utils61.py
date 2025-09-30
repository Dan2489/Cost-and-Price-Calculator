# utils61.py
import streamlit as st

def inject_govuk_css() -> None:
    st.markdown(
        """
        <style>
          [data-testid="stSidebar"]{min-width:420px;max-width:420px}
          @media (max-width:1200px){[data-testid="stSidebar"]{min-width:360px;max-width:360px}}
          :root{--govuk-green:#00703c;--govuk-yellow:#ffdd00;}
          .stButton>button{background:var(--govuk-green)!important;color:#fff!important;border:2px solid transparent!important;border-radius:0!important;font-weight:600;}
          .stButton>button:hover{filter:brightness(.95)}
          .stButton>button:focus{outline:3px solid var(--govuk-yellow)!important;outline-offset:0!important;box-shadow:0 0 0 1px #000 inset!important;}
          [data-testid="stSlider"] [role="slider"]{background:var(--govuk-green)!important;border:2px solid var(--govuk-green)!important;box-shadow:none!important;}
          [data-testid="stSlider"] [role="slider"]:focus{outline:3px solid var(--govuk-yellow)!important;outline-offset:0!important;box-shadow:0 0 0 1px #000 inset!important;}
          [data-testid="stSlider"] div[aria-hidden="true"]>div>div{background-color:var(--govuk-green)!important;}
          .govuk-heading-l{font-weight:700;font-size:1.75rem;line-height:1.2}
          table{width:100%;border-collapse:collapse;margin:12px 0}
          th,td{border-bottom:1px solid #b1b4b6;padding:8px;text-align:left}
          th{background:#f3f2f1} td.neg{color:#d4351c} tr.grand td{font-weight:700}
          .boxed{border:1px solid #b1b4b6;border-radius:6px;padding:16px;margin-top:8px}
        </style>
        """,
        unsafe_allow_html=True
    )

def fmt_currency(v) -> str:
    try:
        return f"£{float(v):,.2f}"
    except Exception:
        return ""

def sidebar_controls(default_output: int):
    st.sidebar.header("Controls")
    lock_overheads = st.sidebar.checkbox("Lock overheads to highest instructor salary", value=False, key="lock_overheads")
    instructor_pct = st.sidebar.slider("Instructor allocation (%)", 0, 100, 100, key="instructor_pct")
    prisoner_output = st.sidebar.slider("Prisoner labour output (%)", 0, 100, default_output, key="prisoner_output")
    return lock_overheads, float(instructor_pct), int(prisoner_output)