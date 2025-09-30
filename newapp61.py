from io import BytesIO
from datetime import date
import pandas as pd
import streamlit as st

from config61 import CFG61
from style import inject_govuk_css
from tariff import PRISON_TO_REGION, SUPERVISOR_PAY
from sidebar61 import draw_sidebar
from production61 import (
    labour_minutes_budget,
    calculate_production_costs,
    production_summary_table,
)
from host61 import generate_host_quote

# -----------------------------------------------------------------------------
# Page config + CSS
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Cost and Price Calculator", page_icon="💷", layout="centered")
inject_govuk_css()

# -----------------------------------------------------------------------------
# Helpers: formatting + HTML export
# -----------------------------------------------------------------------------
def _currency(v) -> str:
    try:
        return f"£{float(v):,.2f}"
    except Exception:
        return ""

def render_host_df_to_html(host_df: pd.DataFrame) -> str:
    rows_html = []
    for _, row in host_df.iterrows():
        item = str(row["Item"])
        val = row["Amount (£)"]
        neg_cls = ""
        try:
            if isinstance(val, str) and val.startswith("-£"):
                neg_cls = " class='neg'"
            elif float(val) < 0:
                neg_cls = " class='neg'"
        except Exception:
            pass
        grand_cls = " class='grand'" if "Grand Total" in item else ""
        rows_html.append(f"<tr{grand_cls}><td>{item}</td><td{neg_cls}>{_currency(val) if not isinstance(val,str) else val}</td></tr>")
    header = "<tr><th>Item</th><th>Amount (£)</th></tr>"
    return f"<table>{header}{''.join(rows_html)}</table>"

def render_generic_df_to_html(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    thead = "<tr>" + "".join([f"<th>{c}</th>" for c in cols]) + "</tr>"
    body_rows = []
    for _, row in df.iterrows():
        tds = []
        for col in cols:
            val = row[col]
            if isinstance(val, (int, float)) and pd.notna(val):
                tds.append(f"<td>{_currency(val) if '£' in col else f'{float(val):,.2f}'}</td>")
            else:
                tds.append(f"<td>{val}</td>")
        body_rows.append("<tr>" + "".join(tds) + "</tr>")
    return f"<table>{thead}{''.join(body_rows)}</table>"

def export_csv_bytes(df: pd.DataFrame) -> BytesIO:
    b = BytesIO()
    df.to_csv(b, index=False)
    b.seek(0)
    return b

def export_html(host_df: pd.DataFrame | None,
                prod_df: pd.DataFrame | None,
                title: str = "Quote") -> BytesIO:
    css = """
      <style>
        body{font-family:Arial,Helvetica,sans-serif;color:#0b0c0c;}
        table{width:100%;border-collapse:collapse;margin:12px 0;}
        th,td{border-bottom:1px solid #b1b4b6;padding:8px;text-align:left;}
        th{background:#f3f2f1;} td.neg{color:#d4351c;} tr.grand td{font-weight:700;}
        h1,h2,h3{margin:0.2rem 0;}
      </style>
    """
    header_html = f"<h2>{title}</h2>"
    meta = (f"<p>Date: {date.today().isoformat()}<br/>"
            f"Customer: {st.session_state.get('customer_name','')}<br/>"
            f"Prison: {st.session_state.get('prison_choice','')}<br/>"
            f"Region: {st.session_state.get('region','')}</p>")
    parts = [css, header_html, meta]
    if host_df is not None:
        parts += ["<h3>Host Costs</h3>", render_host_df_to_html(host_df)]
    if prod_df is not None:
        section_title = "Production Items"
        parts += [f"<h3>{section_title}</h3>", render_generic_df_to_html(prod_df)]
    parts.append("<p>Prices are indicative and may change based on final scope and site conditions.</p>")

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>{title}</title>
</head>
<body>
{''.join(parts)}
</body>
</html>"""
    b = BytesIO(html_doc.encode("utf-8"))
    b.seek(0)
    return b

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

workshop_hours = st.number_input("How many hours per week is the workshop open?", min_value=0.0, format="%.2f", key="workshop_hours")
num_prisoners   = st.number_input("How many prisoners employed?", min_value=0, step=1, key="num_prisoners")
prisoner_salary = st.number_input("Prisoner salary per week (£)", min_value=0.0, format="%.2f", key="prisoner_salary")
num_supervisors = st.number_input("How many instructors?", min_value=0, step=1, key="num_supervisors")
customer_covers_supervisors = st.checkbox("Customer provides instructor(s)?", key="customer_covers_supervisors")

supervisor_salaries = []
if not customer_covers_supervisors:
    titles_for_region = SUPERVISOR_PAY.get(region, [])
    if region == "Select" or not titles_for_region:
        st.warning("Select a prison to derive the Region before assigning instructor titles.")
    else:
        for i in range(int(num_supervisors)):
            options = [t["title"] for t in titles_for_region]
            sel = st.selectbox(f"Instructor {i+1} title", options, key=f"inst_title_{i}")
            pay = next(t["avg_total"] for t in titles_for_region if t["title"] == sel)
            st.caption(f"Avg Total for {region}: **£{pay:,.0f}** per year")
            supervisor_salaries.append(float(pay))

contracts = st.number_input("How many contracts do these instructors oversee?", min_value=1, value=1, key="contracts")
recommended_pct = round((workshop_hours / 37.5) * (1 / contracts) * 100, 1) if contracts and workshop_hours >= 0 else 0
st.session_state["recommended_pct"] = recommended_pct

# Development charge
dev_rate = 0.0
if customer_type == "Commercial":
    support = st.selectbox(
        "Customer employment support?",
        ["None", "Employment on release/RoTL", "Post release", "Both"],
        help="Affects development charge (on instructor overheads)."
    )
    st.session_state["support"] = support
    if support == "None":
        dev_rate = 0.20
    elif support in ("Employment on release/RoTL", "Post release"):
        dev_rate = 0.10
    elif support == "Both":
        dev_rate = 0.00

# -----------------------------------------------------------------------------
# Sidebar controls (lock overheads + sliders)
# -----------------------------------------------------------------------------
draw_sidebar(recommended_pct)

# -----------------------------------------------------------------------------
# HOST
# -----------------------------------------------------------------------------
def run_host():
    if st.button("Generate Costs"):
        host_df, _ctx = generate_host_quote(
            num_prisoners=int(num_prisoners),
            prisoner_salary=float(prisoner_salary),
            num_supervisors=int(num_supervisors),
            customer_covers_supervisors=bool(customer_covers_supervisors),
            supervisor_salaries=supervisor_salaries,
            effective_pct=float(st.session_state.get("chosen_pct", recommended_pct)),
            customer_type=customer_type,
            apply_vat=True,
            vat_rate=20.0,
            dev_rate=float(dev_rate),
        )
        st.markdown(render_host_df_to_html(host_df), unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.download_button("Download CSV (Host)", data=export_csv_bytes(host_df), file_name="host_quote.csv", mime="text/csv")
        with c2:
            st.download_button(
                "Download PDF-ready HTML (Host)",
                data=export_html(host_df, None, title="Host Quote"),
                file_name="host_quote.html", mime="text/html"
            )

# -----------------------------------------------------------------------------
# PRODUCTION
# -----------------------------------------------------------------------------
def run_production():
    planned_output_pct = st.session_state.get("labour_output_pct", CFG61.GLOBAL_OUTPUT_DEFAULT)
    results = calculate_production_costs(
        num_prisoners=num_prisoners,
        prisoner_salary=prisoner_salary,
        supervisor_salaries=supervisor_salaries,
        effective_pct=st.session_state.get("chosen_pct", recommended_pct),
        customer_covers_supervisors=customer_covers_supervisors,
        customer_type=customer_type,
        vat_rate=20.0,
        dev_rate=dev_rate,
        planned_output_pct=planned_output_pct,
    )
    df = production_summary_table(results)
    st.markdown(render_generic_df_to_html(df), unsafe_allow_html=True)
    d1, d2 = st.columns(2)
    with d1:
        st.download_button("Download CSV (Production)", data=export_csv_bytes(df), file_name="production_quote.csv", mime="text/csv")
    with d2:
        st.download_button(
            "Download PDF-ready HTML (Production)",
            data=export_html(None, df, title="Production Quote"),
            file_name="production_quote.html", mime="text/html"
        )

# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
if workshop_mode == "Host":
    run_host()
elif workshop_mode == "Production":
    run_production()

# -----------------------------------------------------------------------------
# Reset
# -----------------------------------------------------------------------------
if st.button("Reset Selections", key="reset_app_footer"):
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()