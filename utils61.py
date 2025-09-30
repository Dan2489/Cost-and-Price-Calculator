import streamlit as st

# ---------- CSS (keep aesthetics) ----------
def inject_govuk_css() -> None:
    st.markdown(
        """
        <style>
          [data-testid="stSidebar"]{min-width:420px;max-width:420px}
          @media (max-width:1200px){
            [data-testid="stSidebar"]{min-width:360px;max-width:360px}
          }
          :root{--govuk-green:#00703c;--govuk-yellow:#ffdd00;}
          .stButton>button{background:var(--govuk-green)!important;color:#fff!important;
            border:2px solid transparent!important;border-radius:0!important;font-weight:600;}
          .stButton>button:hover{filter:brightness(.95)}
          .stButton>button:focus{outline:3px solid var(--govuk-yellow)!important;
            outline-offset:0!important;box-shadow:0 0 0 1px #000 inset!important;}
          [data-testid="stSlider"] [role="slider"]{background:var(--govuk-green)!important;
            border:2px solid var(--govuk-green)!important;box-shadow:none!important;}
          [data-testid="stSlider"] [role="slider"]:focus{outline:3px solid var(--govuk-yellow)!important;
            outline-offset:0!important;box-shadow:0 0 0 1px #000 inset!important;}
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

# ---------- formatters ----------
def fmt_currency(v):
    try:
        return f"£{float(v):,.2f}"
    except Exception:
        return ""

# ---------- Sidebar controls (only these three) ----------
def render_sidebar():
    with st.sidebar:
        st.header("Adjustments")
        st.session_state["lock_overheads"] = st.checkbox(
            "Lock overheads to highest instructor salary", value=st.session_state.get("lock_overheads", False)
        )
        st.session_state["effective_pct"] = st.slider(
            "Instructor allocation (%)", 0, 100, st.session_state.get("effective_pct", 100), 1
        )
        st.session_state["output_pct"] = st.slider(
            "Prisoner output (%) (Production only)", 10, 100, st.session_state.get("output_pct", 100), 5
        )