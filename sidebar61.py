# sidebar61.py
import streamlit as st

def draw_sidebar() -> None:
    with st.sidebar:
        st.header("Overhead Options")
        st.markdown("← Configure how overheads are applied")

        # Toggle to lock overheads at the highest instructor cost
        lock_highest = st.checkbox(
            "Lock overheads against highest instructor cost",
            key="lock_overheads_highest",
            help="If selected, overheads will always be based on the highest selected instructor cost (61%)."
        )

        st.session_state["lock_overheads_highest"] = lock_highest
