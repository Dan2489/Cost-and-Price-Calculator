import streamlit as st
import pandas as pd
from datetime import date

# -------------------------------
# Mock minimal config replacements
# -------------------------------
class CFG:
    GLOBAL_OUTPUT_DEFAULT = 100

PRISON_TO_REGION = {
    "Altcourse": "National",
    "Hindley": "National",
    "Ranby": "National",
}

SUPERVISOR_PAY = {
    "National": [
        {"title": "Production Instructor: Band 3", "avg_total": 42248},
        {"title": "Production Instructor: Band 4", "avg_total": 47350},
    ]
}

# -------------------------------
# Inline utils61 replacements
# -------------------------------
def inject_govuk_css():
    st.markdown(
        """
        <style>
        body { font-family: 'Arial', sans-serif; }
        table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
        th, td { border: 1px solid #ddd; padding: 8px; }
        th { background: #f2f2f2; }
        </style>
        """,
        unsafe_allow_html=True,
    )

def sidebar_controls(default):
    st.sidebar.header("Controls")
    prisoner_output = st.sidebar.slider("Prisoner labour output (%)", 0, 100, default)
    return False, 0, prisoner_output

def fmt_currency(v):
    try:
        return f"£{float(v):,.2f}"
    except Exception:
        return v

def export_csv_bytes_rows(rows):
    import io
    df = pd.DataFrame(rows)
    csv_buf = io.StringIO()
    df.to_csv(csv_buf, index=False)
    return csv_buf.getvalue().encode("utf-8")

def render_table_html(df):
    html = df.to_html(index=False, escape=False)
    return html

def build_header_block(**kwargs):
    hdr = "<h3>Quote Summary</h3>"
    for k, v in kwargs.items():
        hdr += f"<p><strong>{k.replace('_', ' ').title()}:</strong> {v}</p>"
    return hdr

def export_html(df, df2=None, title="", header_block="", segregated_df=None):
    html = f"<html><head><title>{title}</title></head><body>{header_block}"
    if df is not None:
        html += render_table_html(df)
    if df2 is not None:
        html += "<hr>" + render_table_html(df2)
    if segregated_df is not None:
        html += "<hr>" + render_table_html(segregated_df)
    html += "</body></html>"
    return html.encode("utf-8")

# -------------------------------
# Mock host + production logic
# -------------------------------
def generate_host_quote_mock(workshop_hours, num_prisoners, prisoner_salary, num_supervisors, supervisor_salaries):
    base_prison = num_prisoners * prisoner_salary * 4.33
    base_instructor = sum(supervisor_salaries) / 12
    overheads = base_instructor * 0.61
    dev_charge = overheads * 0.2
    vat = (base_prison + base_instructor + overheads + dev_charge) * 0.2
    total = base_prison + base_instructor + overheads + dev_charge

    rows = [
        {"Item": "Prisoner Wages", "Amount (£)": fmt_currency(base_prison)},
        {"Item": "Instructor Salary", "Amount (£)": fmt_currency(base_instructor)},
        {"Item": "Overheads", "Amount (£)": fmt_currency(overheads)},
        {"Item": "Development charge", "Amount (£)": fmt_currency(dev_charge)},
        {"Item": "Grand Total", "Amount (£)": fmt_currency(total)},
        {"Item": "VAT", "Amount (£)": fmt_currency(vat)},
    ]
    return pd.DataFrame(rows)

def labour_minutes_budget(num_prisoners, hours):
    return num_prisoners * hours * 60

# -------------------------------
# Streamlit main app
# -------------------------------
st.set_page_config(page_title="Cost and Price Calculator", page_icon="💷", layout="centered")
inject_govuk_css()
st.title("Cost and Price Calculator")

_, _, prisoner_output = sidebar_controls(CFG.GLOBAL_OUTPUT_DEFAULT)

# Base inputs
prisons_sorted = ["Select"] + sorted(PRISON_TO_REGION.keys())
prison_choice = st.selectbox("Prison Name", prisons_sorted, index=0)
region = PRISON_TO_REGION.get(prison_choice, "Select") if prison_choice != "Select" else "Select"

customer_name = st.text_input("Customer Name")
contract_type = st.selectbox("Contract Type", ["Select", "Host", "Production"])

workshop_hours = st.number_input("How many hours is the workshop open per week?", min_value=0.0, format="%.2f")
num_prisoners = st.number_input("How many prisoners employed per week?", min_value=0, step=1)
prisoner_salary = st.number_input("Average prisoner salary per week (£)", min_value=0.0, format="%.2f")

num_supervisors = st.number_input("How many instructors are required at full contract capacity.", min_value=1, step=1)
region = PRISON_TO_REGION.get(prison_choice, "National")
titles = [t["title"] for t in SUPERVISOR_PAY.get(region, [])]
supervisor_salaries = []
for i in range(int(num_supervisors)):
    sel = st.selectbox(f"Instructor {i+1} Title", titles, key=f"inst_title_{i}")
    pay = next(t["avg_total"] for t in SUPERVISOR_PAY[region] if t["title"] == sel)
    st.caption(f"{region} — £{pay:,.0f}")
    supervisor_salaries.append(float(pay))

contracts = st.number_input("How many contracts do they oversee in this workshop?", min_value=1, value=1)
employment_support = st.selectbox(
    "What employment support does the customer offer?",
    ["None", "Employment on release/RoTL", "Post release", "Both"],
)

# Additional benefits
has_benefits = st.radio(
    "Any additional prison benefits that you feel warrant a further reduction?",
    ["No", "Yes"], index=0
)
benefits_text = ""
if has_benefits == "Yes":
    benefits_text = st.text_area("Describe the benefits")
instructor_discount = 0.1 if has_benefits == "Yes" else 0.0

# -------------------------------
# HOST section
# -------------------------------
if contract_type == "Host":
    if st.button("Generate Host Costs"):
        df = generate_host_quote_mock(workshop_hours, num_prisoners, prisoner_salary, num_supervisors, supervisor_salaries)

        # Extract numeric values
        def grab(df, needle):
            try:
                m = df["Item"].astype(str).str.contains(needle, case=False, na=False, regex=False)
                if m.any():
                    raw = str(df.loc[m, "Amount (£)"].iloc[-1]).replace("£", "").replace(",", "")
                    return float(raw)
            except Exception:
                pass
            return 0.0

        prison_wages = grab(df, "Prisoner")
        instructor_salary = grab(df, "Instructor")
        overheads = grab(df, "Overheads")
        dev = grab(df, "Development")
        total = grab(df, "Grand")
        vat = grab(df, "VAT")

        # Apply 10% discount on instructor if benefits selected
        benefits_reduction = 0
        if instructor_discount > 0 and instructor_salary > 0:
            benefits_reduction = instructor_salary * instructor_discount
            df = pd.concat([df, pd.DataFrame([{
                "Item": "Additional benefits reduction",
                "Amount (£)": f"-£{benefits_reduction:,.2f}"
            }])], ignore_index=True)
            total -= benefits_reduction
            df.loc[df["Item"] == "Grand Total", "Amount (£)"] = fmt_currency(total)

        df_display = df.copy()
        df_display["Item"] = df_display["Item"].apply(
            lambda x: f"<span style='color:red'>{x}</span>" if "reduction" in str(x).lower() else x
        )
        st.markdown(render_table_html(df_display), unsafe_allow_html=True)

        # CSV + HTML export
        header_block = build_header_block(
            uk_date=date.today().strftime("%d/%m/%Y"),
            customer_name=customer_name,
            prison_name=prison_choice,
            region=region,
        )

        common = {
            "Prison Name": prison_choice,
            "Region": region,
            "Customer Name": customer_name,
            "Workshop Hours": workshop_hours,
            "Prisoners": num_prisoners,
            "Prisoner Salary": prisoner_salary,
            "Employment Support": employment_support,
            "Additional Benefits": has_benefits,
            "Benefits Description": benefits_text,
        }
        amounts = {
            "Prisoner wages (£/month)": prison_wages,
            "Instructor Salary (£/month)": instructor_salary,
            "Overheads (£/month)": overheads,
            "Development charge (£/month)": dev,
            "Additional Benefits Reduction (£/month)": benefits_reduction,
            "Grand Total (£/month)": total,
            "Grand Total + VAT (£/month)": total + vat,
        }

        csv_bytes = export_csv_bytes_rows([{**common, **amounts}])
        c1, c2 = st.columns(2)
        with c1:
            st.download_button("Download CSV (Host)", data=csv_bytes, file_name="host_quote.csv", mime="text/csv")
        with c2:
            st.download_button(
                "Download PDF-ready HTML (Host)",
                data=export_html(df, None, title="Host Quote", header_block=header_block, segregated_df=None),
                file_name="host_quote.html",
                mime="text/html"
            )

# -------------------------------
# PRODUCTION (mock display only)
# -------------------------------
if contract_type == "Production":
    st.subheader("Production section is unchanged and uses the same benefit logic.")
    st.info("Instructor costs derived from workshop hours and contracts internally.")