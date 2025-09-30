from io import BytesIO
from datetime import date, datetime
import pandas as pd
import streamlit as st

from config61 import CFG
from utils61 import inject_govuk_css, draw_sidebar
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
from host61 import generate_host_quote
from production61 import labour_minutes_budget, calculate_production_contractual, calculate_adhoc

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

def render_df_to_html(df: pd.DataFrame) -> str:
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

def export_html(df: pd.DataFrame, title: str = "Quote") -> BytesIO:
    css = """
      <style>
        body{font-family:Arial,Helvetica,sans-serif;color:#0b0c0c;}
        table{width:100%;border-collapse:collapse;margin:12px 0;}
        th,td{border-bottom:1px solid #b1b4b6;padding:8px;text-align:left;}
        th{background:#f3f2f1;} td.neg{color:#d4351c;} tr.grand td{font-weight:700;}
        h1,h2,h3{margin:0.2rem 0;}
        .red {color:#d4351c;}
      </style>
    """
    header_html = f"<h2>{title}</h2>"
    meta = (f"<p>Date: {date.today().isoformat()}<br/>"
            f"Customer: {st.session_state.get('customer_name','')}<br/>"
            f"Prison: {st.session_state.get('prison_choice','')}<br/>"
            f"Region: {st.session_state.get('region','')}</p>")
    parts = [css, header_html, meta, render_df_to_html(df)]
    html_doc = f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8" /><title>{title}</title></head>
<body>{''.join(parts)}</body></html>"""
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

customer_type = st.selectbox("Customer type", ["Select", "Commercial", "Another Government Department"], key="customer_type")
customer_name = st.text_input("Customer Name", key="customer_name")
workshop_mode = st.selectbox("Contract type?", ["Select", "Host", "Production"], key="workshop_mode")

# Prisoners & instructors
workshop_hours = st.number_input("Hours per week workshop open", min_value=0.0, format="%.2f", key="workshop_hours")
num_prisoners = st.number_input("How many prisoners employed?", min_value=0, step=1, key="num_prisoners")
prisoner_salary = st.number_input("Prisoner salary per week (£)", min_value=0.0, format="%.2f", key="prisoner_salary")
num_supervisors = st.number_input("How many instructors?", min_value=0, step=1, key="num_supervisors")
customer_covers_supervisors = st.checkbox("Customer provides instructor(s)?", key="customer_covers_supervisors")

supervisor_salaries = []
if not customer_covers_supervisors and region != "Select":
    titles_for_region = SUPERVISOR_PAY.get(region, [])
    for i in range(int(num_supervisors)):
        options = [t["title"] for t in titles_for_region]
        sel = st.selectbox(f"Instructor {i+1} title", options, key=f"inst_title_{i}")
        pay = next(t["avg_total"] for t in titles_for_region if t["title"] == sel)
        st.caption(f"Avg Total for {region}: **£{pay:,.0f}** per year")
        supervisor_salaries.append(float(pay))

contracts = st.number_input("How many contracts do these instructors oversee?", min_value=1, value=1, key="contracts")

# Instructor allocation recommendation
recommended_pct = round((workshop_hours / 37.5) * (1 / contracts) * 100, 1) if contracts and workshop_hours > 0 else 0
st.info(f"Recommended Instructor Allocation: {recommended_pct}%")

# Development charge (Commercial only)
dev_rate = 0.0
if customer_type == "Commercial":
    support = st.selectbox(
        "Customer employment support?",
        ["None", "Employment on release/RoTL", "Post release", "Both"],
    )
    if support == "None":
        dev_rate = 0.20
    elif support in ("Employment on release/RoTL", "Post release"):
        dev_rate = 0.10
    else:
        dev_rate = 0.00

# Sidebar controls
draw_sidebar(CFG.GLOBAL_OUTPUT_DEFAULT)
effective_pct = int(st.session_state.get("chosen_pct", recommended_pct))
lock_overheads = st.session_state.get("lock_overheads", False)
planned_output_pct = st.session_state.get("planned_output_pct", CFG.GLOBAL_OUTPUT_DEFAULT)

# -----------------------------------------------------------------------------
# HOST
# -----------------------------------------------------------------------------
if workshop_mode == "Host":
    if st.button("Generate Host Costs"):
        host_df, _ctx = generate_host_quote(
            num_prisoners=int(num_prisoners),
            prisoner_salary=float(prisoner_salary),
            num_supervisors=int(num_supervisors),
            customer_covers_supervisors=bool(customer_covers_supervisors),
            supervisor_salaries=supervisor_salaries,
            effective_pct=float(effective_pct),
            region=region,
            customer_type=customer_type,
            vat_rate=20.0,
            dev_rate=float(dev_rate),
            lock_overheads=bool(lock_overheads),
        )
        # Insert development charge breakdown if commercial
        if customer_type == "Commercial":
            base_dev = 0.20
            if support == "None":
                st.markdown(f"**Development charge applied:** {base_dev*100:.0f}%")
            elif support in ("Employment on release/RoTL", "Post release"):
                st.markdown(f"**Development charge applied:** {base_dev*100:.0f}%")
                st.markdown("<span class='red'>-10% for support</span>", unsafe_allow_html=True)
                st.markdown(f"**Revised development charge:** {dev_rate*100:.0f}%")
            elif support == "Both":
                st.markdown(f"**Development charge applied:** {base_dev*100:.0f}%")
                st.markdown("<span class='red'>-20% for support</span>", unsafe_allow_html=True)
                st.markdown(f"**Revised development charge:** {dev_rate*100:.0f}%")

        st.markdown(render_df_to_html(host_df), unsafe_allow_html=True)
        st.download_button("Download CSV", data=export_csv_bytes(host_df), file_name="host_quote.csv", mime="text/csv")
        st.download_button("Download HTML", data=export_html(host_df, "Host Quote"), file_name="host_quote.html", mime="text/html")

# -----------------------------------------------------------------------------
# PRODUCTION
# -----------------------------------------------------------------------------
if workshop_mode == "Production":
    st.markdown("---")
    st.subheader("Production settings")

    prod_type = st.radio(
        "Do you want ad-hoc costs with a deadline, or contractual work?",
        ["Contractual work", "Ad-hoc costs (multiple lines) with deadlines"],
        index=0, key="prod_type"
    )

    if prod_type == "Contractual work":
        pricing_mode_label = st.radio(
            "Price based on:",
            ["Maximum units from capacity", "Target units per week"],
            index=0,
        )
        pricing_mode = "as-is" if pricing_mode_label.startswith("Maximum") else "target"

        # Planned minutes
        budget_minutes_raw = labour_minutes_budget(int(num_prisoners), float(workshop_hours))
        budget_minutes_planned = budget_minutes_raw * (planned_output_pct / 100.0)
        st.markdown(f"**Planned available Labour minutes @ {planned_output_pct}%:** {budget_minutes_planned:,.0f}")

        # Items
        num_items = st.number_input("Number of items produced?", min_value=1, value=1, step=1, key="num_items_prod")
        items, targets = [], []
        for i in range(int(num_items)):
            with st.expander(f"Item {i+1} details", expanded=(i == 0)):
                name = st.text_input(f"Item {i+1} Name", key=f"name_{i}")
                disp = (name.strip() or f"Item {i+1}") if isinstance(name, str) else f"Item {i+1}"
                required = st.number_input(f"Prisoners required to make 1 item ({disp})", min_value=1, value=1, step=1, key=f"req_{i}")
                minutes_per = st.number_input(f"Minutes to make 1 item ({disp})", min_value=1.0, value=10.0, format="%.2f", key=f"mins_{i}")
                assigned = st.number_input(f"How many prisoners work solely on this item ({disp})", min_value=0, max_value=int(num_prisoners), step=1, key=f"assigned_{i}")
                if pricing_mode == "target":
                    tgt = st.number_input(f"Target units per week ({disp})", min_value=0, value=0, step=1, key=f"target_{i}")
                    targets.append(int(tgt))
                items.append({"name": name, "required": int(required), "minutes": float(minutes_per), "assigned": int(assigned)})

        results = calculate_production_contractual(
            items,
            planned_output_pct,
            workshop_hours=float(workshop_hours),
            prisoner_salary=float(prisoner_salary),
            supervisor_salaries=supervisor_salaries,
            effective_pct=float(effective_pct),
            customer_covers_supervisors=bool(customer_covers_supervisors),
            region=region,
            customer_type=customer_type,
            apply_vat=True,
            vat_rate=20.0,
            num_prisoners=int(num_prisoners),
            num_supervisors=int(num_supervisors),
            dev_rate=float(dev_rate),
            pricing_mode=pricing_mode,
            targets=targets if pricing_mode == "target" else None,
            lock_overheads=bool(lock_overheads),
        )
        prod_df = pd.DataFrame(results)
        st.markdown(render_df_to_html(prod_df), unsafe_allow_html=True)

        # ---- Grand Total Monthly Cost (separate line, outside the table) ----
        grand_monthly = 0.0
        if "Monthly Total ex VAT (£)" in prod_df.columns:
            grand_monthly = float(prod_df["Monthly Total ex VAT (£)"].fillna(0).sum())
        else:
            # Fallback: Units/week × Unit Cost (£) × 52/12
            try:
                u = prod_df["Units/week"].astype(float).fillna(0.0)
                c = prod_df["Unit Cost (£)"].astype(float).fillna(0.0)
                grand_monthly = float((u * c).sum() * (52.0 / 12.0))
            except Exception:
                grand_monthly = 0.0
        st.markdown(f"**Grand Total Monthly Cost (ex VAT): {_currency(grand_monthly)}**")

        st.download_button("Download CSV", data=export_csv_bytes(prod_df), file_name="production_quote.csv", mime="text/csv")
        st.download_button("Download HTML", data=export_html(prod_df, "Production Quote"), file_name="production_quote.html", mime="text/html")

    else:  # Ad-hoc mode
        st.info("Enter multiple lines with units and deadlines for feasibility check.")

        num_lines = st.number_input("Number of lines", min_value=1, value=1, step=1, key="num_lines")
        lines = []
        for i in range(int(num_lines)):
            with st.expander(f"Line {i+1}", expanded=(i == 0)):
                name = st.text_input(f"Line {i+1} Name", key=f"line_name_{i}")
                units = st.number_input(f"Units required ({name or f'Line {i+1}'})", min_value=0, value=0, step=1, key=f"units_{i}")
                mins_per_item = st.number_input(f"Minutes per item ({name or f'Line {i+1}'})", min_value=1.0, value=10.0, step=1.0, key=f"mins_line_{i}")
                pris_per_item = st.number_input(f"Prisoners required per item ({name or f'Line {i+1}'})", min_value=1, value=1, step=1, key=f"pris_line_{i}")
                deadline = st.date_input(f"Deadline for line {i+1}", value=date.today(), key=f"deadline_{i}")
                lines.append({"name": name or f"Line {i+1}", "units": units, "mins_per_item": mins_per_item, "pris_per_item": pris_per_item, "deadline": deadline})

        results = calculate_adhoc(
            lines,
            planned_output_pct,
            workshop_hours=float(workshop_hours),
            num_prisoners=int(num_prisoners),
            prisoner_salary=float(prisoner_salary),
            supervisor_salaries=supervisor_salaries,
            effective_pct=float(effective_pct),
            customer_covers_supervisors=bool(customer_covers_supervisors),
            customer_type=customer_type,
            apply_vat=True,
            vat_rate=20.0,
            dev_rate=float(dev_rate),
            today=datetime.today().date(),
        )

        per_line = pd.DataFrame(results["per_line"])
        st.markdown(render_df_to_html(per_line), unsafe_allow_html=True)

        # Ad-hoc already shows job totals; keep that (no monthly derivation here)
        totals_ex = float(sum(p["line_total_ex_vat"] for p in results["per_line"]))
        totals_inc = float(sum(p["line_total_inc_vat"] for p in results["per_line"]))
        st.markdown(f"**Total Job Cost (ex VAT): {_currency(totals_ex)}**")
        st.markdown(f"**Total Job Cost (inc VAT): {_currency(totals_inc)}**")

        st.download_button("Download CSV", data=export_csv_bytes(per_line), file_name="adhoc_quote.csv", mime="text/csv")
        st.download_button("Download HTML", data=export_html(per_line, "Ad-hoc Quote"), file_name="adhoc_quote.html", mime="text/html")