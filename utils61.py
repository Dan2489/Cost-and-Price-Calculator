import io
import pandas as pd

# -------------------------------
# Inject GOV.UK styling
# -------------------------------
def inject_govuk_css():
    import streamlit as st
    st.markdown(
        """
        <style>
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
          .stButton > button:hover { filter: brightness(0.95); }
          .stButton > button:focus {
            outline: 3px solid var(--govuk-yellow) !important;
            box-shadow: 0 0 0 1px #000 inset !important;
          }

          /* Tables */
          table.custom { width: 100%; border-collapse: collapse; margin: 12px 0; }
          table.custom th, table.custom td {
            border: 1px solid #b1b4b6;
            padding: 6px 10px;
            text-align: left;
          }
          table.custom th { background: #f3f2f1; font-weight: bold; }
          table.custom td.neg { color: #d4351c; }
          table.custom tr.grand td { font-weight: bold; }
          table.custom.highlight { background-color: #fff8dc; }

          /* Red lines (reductions) */
          .reduction { color: #d4351c; }
        </style>
        """,
        unsafe_allow_html=True
    )

# -------------------------------
# Sidebar controls
# -------------------------------
def sidebar_controls(default_output: int):
    """
    Returns: (lock_overheads: bool, instructor_pct: int, prisoner_output: int)
    """
    import streamlit as st
    with st.sidebar:
        st.header("Controls")
        lock_overheads = st.checkbox("Lock overheads to highest instructor", value=False)
        instructor_pct = st.slider("Instructor allocation (%)", 0, 100, 100, step=5)
        prisoner_output = st.slider("Prisoner labour output (%)", 0, 100, default_output, step=5)
    return lock_overheads, instructor_pct, prisoner_output

# -------------------------------
# Formatters
# -------------------------------
def fmt_currency(val) -> str:
    try:
        return f"£{float(val):,.2f}"
    except Exception:
        return str(val)

def _fmt_cell(x):
    import pandas as pd
    if pd.isna(x):
        return ""
    s = str(x)
    if s.strip() == "":
        return ""
    try:
        if "£" in s:
            s_num = s.replace("£", "").replace(",", "").strip()
            return fmt_currency(float(s_num))
        return fmt_currency(float(s))
    except Exception:
        return s

# -------------------------------
# Table rendering
# -------------------------------
def render_table_html(df: pd.DataFrame, highlight: bool = False) -> str:
    if df is None or df.empty:
        return "<p><em>No data</em></p>"

    df_fmt = df.copy()
    for col in df_fmt.columns:
        if any(key in col for key in ["£", "Cost", "Total", "Price", "Grand"]):
            df_fmt[col] = df_fmt[col].apply(lambda x: _fmt_cell(x))
        if col == "Item":
            df_fmt[col] = df_fmt[col].apply(
                lambda x: f"<span class='reduction'>{x}</span>" if "Reduction" in str(x) else x
            )

    cls = "custom highlight" if highlight else "custom"
    return df_fmt.to_html(index=False, classes=cls, border=0, justify="left", escape=False)

# -------------------------------
# HTML export
# -------------------------------
def export_html(
    df_host: pd.DataFrame,
    df_prod_combined: pd.DataFrame,
    title: str,
    *,
    prison_name: str = "",
    region: str = "",
    customer_name: str = "",
    uk_date: str = "",
    df_prod_segregated: pd.DataFrame = None,
    monthly_instructor_salary: float = None,
    extra_note: str = None
) -> str:
    styles = """
    <style>
        body { font-family: Arial, sans-serif; }
        table.custom { width: 100%; border-collapse: collapse; margin: 12px 0; }
        table.custom th, table.custom td { border: 1px solid #b1b4b6; padding: 6px 10px; text-align: left; }
        table.custom th { background: #f3f2f1; font-weight: bold; }
        .reduction { color: #d4351c; }
    </style>
    """
    html = f"<html><head><meta charset='utf-8' />{styles}</head><body>"
    html += f"<h1>{title}</h1>"

    meta = []
    if uk_date: meta.append(f"Date: {uk_date}")
    if customer_name: meta.append(f"Customer: {customer_name}")
    if prison_name: meta.append(f"Prison: {prison_name}")
    if region: meta.append(f"Region: {region}")
    if meta:
        html += "<p>" + "<br/>".join(meta) + "</p>"

    html += (
        "<p>We are pleased to set out below the terms of our Quotation for the Goods and/or Services you are "
        "currently seeking. We confirm that this Quotation and any subsequent contract entered into as a result "
        "is, and will be, subject exclusively to our Standard Conditions of Sale of Goods and/or Services a copy "
        "of which is available on request. Please note that all prices are exclusive of VAT and carriage costs at "
        "time of order of which the customer shall be additionally liable to pay.</p>"
    )

    if df_host is not None:
        html += "<h3>Host Costs</h3>"
        html += render_table_html(df_host)

    if df_prod_combined is not None:
        html += "<h3>Production – Combined Costs</h3>"
        html += render_table_html(df_prod_combined)

    if df_prod_segregated is not None:
        html += "<h3>Production – Instructor Segregated</h3>"
        if monthly_instructor_salary is not None:
            html += f"<p><strong>Monthly Instructor Salary (segregated):</strong> {fmt_currency(monthly_instructor_salary)}</p>"
        html += render_table_html(df_prod_segregated, highlight=True)

    if extra_note:
        html += f"<div style='margin-top:1em'>{extra_note}</div>"

    html += "</body></html>"
    return html

# -------------------------------
# CSV export (flat)
# -------------------------------
def export_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")