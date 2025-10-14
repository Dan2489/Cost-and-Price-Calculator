# newapp61.py — self-contained, shows Dev charge reduction + Revised dev charge in summary

import streamlit as st
import pandas as pd
from datetime import date

# -------------------------------
# Minimal config & lookups (inline)
# -------------------------------
class CFG:
    GLOBAL_OUTPUT_DEFAULT = 100  # only used for prisoner-output sidebar slider

PRISON_TO_REGION = {
    "Altcourse": "National",
    "Hindley": "National",
    "Ranby": "National",
    "Durham": "National",
    "Elmley": "National",
    "Wealstun": "National",
    "Highpoint": "National",
    "Lowdham Grange": "National",
    "Winchester": "National",
}

SUPERVISOR_PAY = {
    "National": [
        {"title": "Production Instructor: Band 3", "avg_total": 42248},
        {"title": "Production Instructor: Band 4", "avg_total": 47350},
        {"title": "Prison Officer Specialist - Instructor: Band 4", "avg_total": 48969},
    ]
}

# -------------------------------
# Inline utility replacements (no external utils import)
# -------------------------------
def inject_govuk_css():
    st.markdown(
        """
        <style>
          :root { --govuk-green:#00703c; --govuk-yellow:#ffdd00; --govuk-red:#d4351c; }
          .stButton > button { background: var(--govuk-green)!important; color:#fff!important; border-radius:0!important; }
          .neg { color: var(--govuk-red); font-weight:600; }
          table.custom { width:100%; border-collapse:collapse; margin:12px 0; }
          table.custom th, table.custom td { border:1px solid #b1b4b6; padding:6px 10px; text-align:left; }
          table.custom th { background:#f3f2f1; font-weight:700; }
        </style>
        """,
        unsafe_allow_html=True,
    )

def sidebar_controls(default_output: int):
    with st.sidebar:
        st.header("Controls")
        prisoner_output = st.slider("Prisoner labour output (%)", 0, 100, default_output, step=1)
    # return placeholders to preserve original signature (lock_overheads, instructor_pct, prisoner_output)
    return False, 0, prisoner_output

def fmt_currency(val) -> str:
    try:
        return f"£{float(val):,.2f}"
    except Exception:
        return str(val)

def render_table_html(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "<p><em>No data</em></p>"
    return df.to_html(index=False, classes="custom", escape=False)

def export_csv_bytes_rows(rows: list[dict]) -> bytes:
    import io
    df = pd.DataFrame(rows)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

def build_header_block(*, uk_date: str, customer_name: str, prison_name: str, region: str) -> str:
    return (
        f"<h2>Quotation</h2>"
        f"<p><strong>Date:</strong> {uk_date}</p>"
        f"<p><strong>Prison:</strong> {prison_name} ({region})</p>"
        f"<p><strong>Customer:</strong> {customer_name}</p>"
        "<p>We are pleased to set out below the terms of our Quotation for the Goods and/or Services you are "
        "currently seeking. We confirm that this Quotation and any subsequent contract entered into as a result "
        "is, and will be, subject exclusively to our Standard Conditions of Sale of Goods and/or Services a copy "
        "of which is available on request. Please note that all prices are exclusive of VAT and carriage costs at "
        "time of order of which the customer shall be additionally liable to pay.</p>"
    )

def export_html(df_host: pd.DataFrame, df_prod: pd.DataFrame, *, title: str, header_block: str = "", segregated_df: pd.DataFrame | None = None) -> bytes:
    html = ["<html><head><meta charset='utf-8' /><title>", title, "</title></head><body>"]
    if header_block:
        html.append(header_block)
        html.append("<hr>")
    if df_host is not None:
        html.append("<h3>Summary</h3>")
        html.append(render_table_html(df_host))
    if df_prod is not None:
        html.append("<h3>Summary</h3>")
        html.append(render_table_html(df_prod))
    if segregated_df is not None and not segregated_df.empty:
        html.append("<h3>Segregated Costs</h3>")
        html.append(render_table_html(segregated_df))
    html.append("</body></html>")
    return "".join(html).encode("utf-8")

def _uk_date(d: date) -> str:
    return d.strftime("%d/%m/%Y")

# -------------------------------
# Development rate rules
# -------------------------------
def _dev_rate_from_support(s: str) -> float:
    # Applicable development rate (used for revised dev charge)
    if s == "None":
        return 0.20
    if s in ("Employment on release/RoTL", "Post release"):
        return 0.10
    return 0.00  # Both

STANDARD_DEV_RATE = 0.20  # "before" rate used to show reduction vs revised

# -------------------------------
# Host quote engine (inline)
# -------------------------------
def generate_host_summary(
    *, num_prisoners: int, prisoner_salary: float,
    num_supervisors: int, supervisor_salaries: list[float],
    employment_support: str, benefits_discount_on_instructor: float
) -> pd.DataFrame:
    """
    Host summary rows (in this order):
      Prisoner wages
      Instructor salary
      Overheads
      Development charge (before) — using STANDARD_DEV_RATE
      Development reduction (red) — difference between 'before' and 'revised'
      Revised development charge — using applicable rate from support
      Additional benefits reduction (red) — 10% of instructor if chosen
      Grand Total (ex VAT)
      VAT (20%)
      Grand Total (inc VAT)
    """
    prisoner_month = num_prisoners * prisoner_salary * 52.0 / 12.0
    instr_month = (sum(supervisor_salaries) / 12.0) if num_supervisors > 0 else 0.0
    overheads_month = instr_month * 0.61

    # Dev "before" at standard 20%
    dev_before = overheads_month * STANDARD_DEV_RATE
    # Dev "revised" at applicable rate
    dev_revised_rate = _dev_rate_from_support(employment_support)
    dev_revised = overheads_month * dev_revised_rate
    # Reduction is the delta (show only if positive)
    dev_reduction = max(0.0, dev_before - dev_revised)

    benefits_reduction = instr_month * benefits_discount_on_instructor if benefits_discount_on_instructor > 0 else 0.0

    grand_total_ex_vat = prisoner_month + instr_month + overheads_month + dev_revised - dev_reduction - benefits_reduction
    vat = grand_total_ex_vat * 0.20
    grand_inc_vat = grand_total_ex_vat + vat

    rows = [
        {"Item": "Prisoner Wages", "Amount (£)": fmt_currency(prisoner_month)},
        {"Item": "Instructor Salary", "Amount (£)": fmt_currency(instr_month)},
        {"Item": "Overheads", "Amount (£)": fmt_currency(overheads_month)},
        {"Item": "Development charge (before)", "Amount (£)": fmt_currency(dev_before)},
    ]
    if dev_reduction > 0:
        rows.append({"Item": "<span class='neg'>Development reduction</span>", "Amount (£)": f"<span class='neg'>- {fmt_currency(dev_reduction)}</span>"})
    rows.append({"Item": "Revised development charge", "Amount (£)": fmt_currency(dev_revised)})
    if benefits_reduction > 0:
        rows.append({"Item": "<span class='neg'>Additional benefits reduction</span>", "Amount (£)": f"<span class='neg'>- {fmt_currency(benefits_reduction)}</span>"})
    rows.extend([
        {"Item": "Grand Total (ex VAT)", "Amount (£)": fmt_currency(grand_total_ex_vat)},
        {"Item": "VAT (20%)", "Amount (£)": fmt_currency(vat)},
        {"Item": "Grand Total (inc VAT)", "Amount (£)": fmt_currency(grand_inc_vat)},
    ])
    return pd.DataFrame(rows)

# -------------------------------
# App UI
# -------------------------------
st.set_page_config(page_title="Cost and Price Calculator", page_icon="💷", layout="centered")
inject_govuk_css()
st.title("Cost and Price Calculator")

# Sidebar (only output slider retained)
_, _, prisoner_output = sidebar_controls(CFG.GLOBAL_OUTPUT_DEFAULT)

# Base inputs
prisons_sorted = ["Select"] + sorted(PRISON_TO_REGION.keys())
prison_choice = st.selectbox("Prison Name", prisons_sorted, index=0, key="prison_choice")
region = PRISON_TO_REGION.get(prison_choice, "Select") if prison_choice != "Select" else "Select"

customer_name = st.text_input("Customer Name", key="customer_name")
contract_type = st.selectbox("Contract Type", ["Select", "Host", "Production"], key="contract_type")

workshop_hours = st.number_input("How many hours is the workshop open per week?", min_value=0.0, format="%.2f")
num_prisoners = st.number_input("How many prisoners employed per week?", min_value=0, step=1)
prisoner_salary = st.number_input("Average prisoner salary per week (£)", min_value=0.0, format="%.2f")

# Instructors (no slider; “required at full contract capacity”)
num_supervisors = st.number_input("How many instructors are required at full contract capacity.", min_value=1, step=1)
supervisor_salaries = []
if num_supervisors > 0 and region != "Select":
    titles_for_region = SUPERVISOR_PAY.get(region, [])
    options = [t["title"] for t in titles_for_region]
    for i in range(int(num_supervisors)):
        sel = st.selectbox(f"Instructor {i+1} Title", options, key=f"inst_title_{i}")
        pay = next(t["avg_total"] for t in titles_for_region if t["title"] == sel)
        st.caption(f"{region} — £{pay:,.0f}")
        supervisor_salaries.append(float(pay))

contracts = st.number_input("How many contracts do they oversee in this workshop?", min_value=1, value=1)

employment_support = st.selectbox(
    "What employment support does the customer offer?",
    ["None", "Employment on release/RoTL", "Post release", "Both"],
)

# Additional benefits (optional 10% off instructor salary)
has_benefits = st.radio(
    "Any additional prison benefits that you feel warrant a further reduction?",
    ["No", "Yes"], index=0, horizontal=True
)
benefits_text = ""
if has_benefits == "Yes":
    benefits_text = st.text_area("Describe the benefits")
instructor_discount = 0.10 if has_benefits == "Yes" else 0.0

# -------------------------------
# HOST
# -------------------------------
if contract_type == "Host":
    if st.button("Generate Host Costs"):
        errors = []
        if prison_choice == "Select": errors.append("Select prison")
        if region == "Select": errors.append("Region could not be derived from prison selection")
        if not str(customer_name).strip(): errors.append("Enter customer name")
        if workshop_hours <= 0: errors.append("Workshop hours must be greater than zero")
        if len(supervisor_salaries) != int(num_supervisors): errors.append("Choose a title for each instructor")

        if errors:
            st.error("Fix errors:\n- " + "\n- ".join(errors))
        else:
            host_df = generate_host_summary(
                num_prisoners=int(num_prisoners),
                prisoner_salary=float(prisoner_salary),
                num_supervisors=int(num_supervisors),
                supervisor_salaries=supervisor_salaries,
                employment_support=employment_support,
                benefits_discount_on_instructor=instructor_discount,
            )
            st.session_state["host_df"] = host_df
            st.session_state["host_ctx"] = {
                "benefits_text": benefits_text,
                "benefits_flag": has_benefits,
                "employment_support": employment_support,
            }

    if "host_df" in st.session_state:
        df = st.session_state["host_df"].copy()
        st.markdown(render_table_html(df), unsafe_allow_html=True)

        # Downloads
        header_block = build_header_block(
            uk_date=_uk_date(date.today()),
            customer_name=customer_name,
            prison_name=prison_choice,
            region=region,
        )

        # Extract numeric values robustly (no regex pitfalls)
        def _grab(df_in: pd.DataFrame, needle: str) -> float:
            try:
                m = df_in["Item"].astype(str).str.contains(needle, case=False, na=False, regex=False)
                if m.any():
                    raw = str(df_in.loc[m, "Amount (£)"].iloc[-1])
                    # strip formatting and possible - in red spans
                    raw = raw.replace("£", "").replace(",", "").replace("-", "").strip()
                    # if wrapped in <span>, keep digits and dot only
                    raw = "".join(ch for ch in raw if (ch.isdigit() or ch in "."))
                    return float(raw)
            except Exception:
                pass
            return 0.0

        prisoner_month   = _grab(df, "Prisoner Wages")
        instructor_month = _grab(df, "Instructor Salary")
        overheads_month  = _grab(df, "Overheads")
        dev_before       = _grab(df, "Development charge (before)")
        dev_reduction    = _grab(df, "Development reduction")
        dev_revised      = _grab(df, "Revised development charge")
        benefits_reduct  = _grab(df, "Additional benefits reduction")
        grand_ex_vat     = _grab(df, "Grand Total (ex VAT)")
        vat_month        = _grab(df, "VAT (20%)")
        grand_inc_vat    = _grab(df, "Grand Total (inc VAT)")

        ctx = st.session_state.get("host_ctx", {})
        csv_row = {
            "Quote Type": "Host",
            "Date": _uk_date(date.today()),
            "Prison Name": prison_choice,
            "Region": region,
            "Customer Name": customer_name,
            "Contract Type": "Host",
            "Workshop Hours / week": workshop_hours,
            "Prisoners Employed": num_prisoners,
            "Prisoner Salary / week": prisoner_salary,
            "Instructors Count": num_supervisors,
            "Employment Support": ctx.get("employment_support", employment_support),
            "Additional Benefits": ctx.get("benefits_flag", "No"),
            "Benefits Description": ctx.get("benefits_text", ""),
            "Host: Prisoner wages (£/month)": prisoner_month,
            "Host: Instructor Salary (£/month)": instructor_month,
            "Host: Overheads (£/month)": overheads_month,
            "Host: Development charge (before £/month)": dev_before,
            "Host: Development Reduction (£/month)": dev_reduction,
            "Host: Development Revised (£/month)": dev_revised,
            "Host: Additional benefits reduction (£/month)": benefits_reduct,
            "Host: Grand Total (ex VAT £/month)": grand_ex_vat,
            "Host: VAT (£/month)": vat_month,
            "Host: Grand Total (inc VAT £/month)": grand_inc_vat,
        }

        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "Download CSV (Host)",
                data=export_csv_bytes_rows([csv_row]),
                file_name="host_quote.csv",
                mime="text/csv"
            )
        with c2:
            st.download_button(
                "Download PDF-ready HTML (Host)",
                data=export_html(df, None, title="Host Quote", header_block=header_block, segregated_df=None),
                file_name="host_quote.html",
                mime="text/html"
            )

# -------------------------------
# PRODUCTION (unchanged note)
# -------------------------------
if contract_type == "Production":
    st.info(
        "Production flow unchanged in this file. Instructor costs are based on the chosen instructor titles, "
        "overheads are 61% of instructor, and development rate follows Employment Support. "
        "Additional benefits reduction would apply to instructor salary if selected."
    )