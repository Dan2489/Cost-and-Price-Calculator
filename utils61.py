# utils61.py
import streamlit as st

def inject_govuk_css():
    st.markdown("""
    <style>
      /* Sidebar adjustments */
      [data-testid="stSidebar"] {
        min-width: 300px !important;
        max-width: 300px !important;
      }
      @media (max-width: 768px) {
        [data-testid="stSidebar"] {
          transform: translateX(-100%) !important;
        }
        [data-testid="stSidebar"][aria-expanded="true"] {
          transform: translateX(0) !important;
        }
      }

      /* Tables */
      table {
        width: auto !important;
        border-collapse: collapse;
        margin: 12px 0;
      }
      th, td {
        border-bottom: 1px solid #b1b4b6;
        padding: 6px 10px;
        text-align: left;
      }
      th {
        background: #f3f2f1;
      }
      td.neg {
        color: #d4351c;
      }
      tr.grand td {
        font-weight: bold;
      }
    </style>
    """, unsafe_allow_html=True)

def fmt_currency(v):
    try:
        return f"£{float(v):,.2f}"
    except Exception:
        return v

def sidebar_controls(default_output: int):
    with st.sidebar:
        st.header("Controls")
        lock_overheads = st.checkbox("Lock overheads to highest instructor salary", value=False)
        instructor_pct = st.slider("Instructor allocation (%)", 0, 100, 100)
        prisoner_output = st.slider("Prisoner labour output (%)", 0, 100, default_output)
    return lock_overheads, instructor_pct, prisoner_output