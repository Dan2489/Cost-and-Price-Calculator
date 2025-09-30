# style61.py
import streamlit as st

def inject_govuk_css() -> None:
    st.markdown(
        """
        <style>
        /* Wider sidebar so controls fit comfortably */
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
        .stButton > button:hover {
            filter: brightness(0.95);
        }
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
        [data-testid="stSlider"] [role="slider"]:focus, [data-testid="stSlider"] [role="slider"]:focus-visible {
            outline: 3px solid var(--govuk-yellow) !important;
            outline-offset: 0 !important;
            box-shadow: 0 0 0 1px #000 inset !important;
        }
        [data-testid="stSlider"] div[aria-hidden="true"] > div > div {
            background-color: var(--govuk-green) !important;
        }

        /* In-body header */
        .govuk-heading-l {
            font-weight: 700;
            font-size: 1.75rem;
            line-height: 1.2;
        }
        .app-header {
            display:flex;
            align-items:center;
            gap:12px;
            margin: 0.25rem 0 0.75rem 0;
        }
        .app-header .app-logo {
            height: 56px;
            width: auto;
            display:block;
        }

        /* Tables */
        table {
            width:100%;
            border-collapse: collapse;
            margin: 12px 0;
        }
        th, td {
            border-bottom: 1px solid #b1b4b6;
            padding: 8px;
            text-align: left;
        }
        th {
            background: #f3f2f1;
        }
        td.neg {
            color: #d4351c;
        }
        tr.grand td {
            font-weight: 700;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
