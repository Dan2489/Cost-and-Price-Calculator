# newapp61.py
# Instructor-cost based app (no utilities). Overheads are 61% of instructor base.
# Keeps aesthetics and structure; adds monthly totals for production and a sidebar lock toggle.
from io import BytesIO
from datetime import date
import pandas as pd
import streamlit as st

from config61 import CFG
from utils61 import inject_govuk_css, draw_sidebar_simple, PRISON_TO_REGION, SUPERVISOR_PAY
from production61 import labour_minutes_budget, calculate_production_contractual, calculate_adhoc
from host61 import generate_host_quote

# -----------------------------------------------------------------------------
# Page config + CSS
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Cost and Price Calculator", page_icon="💷", layout="centered")
inject_govuk_css()

# -----------------------------------------------------------------------------
# Header
# -----------------------------------------------------------------------------
st.markdown("## Cost and Price Calculator")

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _currency(v) -> str:
    try:
        return f"£{float(v):,.2f}"
    except Exception:
        return ""

def render_generic_df_to_html(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    thead = "<tr>" + "".join([f"<th>{c}</th>" for c in cols]) + "</tr>"
    body_rows = []
    for _, row in df.iterrows():
        tds = []
        for col in cols:
            val = row[col]
            if isinstance(val, (int, float)) and pd.notna(val):
                tds.append(f"<td>{_currency(val)}</td>")
            else:
                tds.append(f"<td>{val}</td>")
        body_rows.append("<tr>" + "".join(tds) + "</tr>")
    return f"<table>{thead}{''.join(body_rows)}</table>"

def export_csv_bytes(df: pd.DataFrame) -> BytesIO:
    b = BytesIO()
    df.to_csv(b, index=False)
    b.seek(0)
    return b

def export_html(prod_df: pd.DataFrame | None, title: str = "Quote") -> BytesIO:
    css = """<style>
      body{font-family:Arial,Helvetica,sans-serif;color:#0b0c0c;}
      table{width:100%;border-collapse:collapse;margin:12px 0;}
      th,td{border-bottom:1px solid #b1b4b6;padding:8px;text-align:left;}
      th{background:#f3f2f1;} td.neg{color:#d4351c;} tr.grand td{font-weight:700;}
      h1,h2,h3{margin:0.2rem 0;}
    </style>"""
    header_html = f"<h2>{title}</h2>"
    meta = (f"<p>Date: {date.today().isoformat()}<br/>"
            f"Customer: {st.session_state.get('customer_name','')}<br/>"
            f"Prison: {st.session_state.get('prison_choice','')}<br/>"
            f"Region: {st.session_state.get('region','')}</p>")
    parts = [css, header_html, meta]
    if prod_df is not None:
        parts += [f"<h3>Production Items</h3>", render_generic_df_to_html(prod_df)]
    parts.append("<p>Prices are indicative and may change based on final scope and site conditions.</p>")
    html_doc = f"<!doctype html><html lang='en'><head><meta charset='utf-8'/><title>{title}</title></head><body>{''.join(parts)}</body></html>"
    b = BytesIO(html_doc.encode("utf-8"))
    b.seek(0); return b

# -----------------------------------------------------------------------------
# Base inputs
# -----------------------------------------------------------------------------
prisons_sorted = ["Select"] + sorted(PRISON_TO_REGION.keys())
prison_choice = st.selectbox("Prison Name", prisons_sorted, index=0, key="prison_choice")
region = PRISON_TO_REGION.get(prison_choice, "Select") if prison_choice != "Select" else "Select"
st.session_state["region"] = region

customer_type = st.selectbox("I want to quote for", ["Select", "Commercial", "Another Government Department"], key="customer_type")
customer_name = st.text_input("Customer Name", key="customer_name")
workshop_mode = st.selectbox("Contract type?", ["Select", "Host", "Production"], key="workshop_mode")

# Sidebar (simple): overhead lock toggle
draw_sidebar_simple()

# Hours / staffing & instructors
workshop_hours = st.number_input("How many hours per week is the workshop open?", min_value=0.0, format="%.2f", key="workshop_hours")
num_prisoners   = st.number_input("How many prisoners employed?", min_value=0, step=1, key="num_prisoners")
pr