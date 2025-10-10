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
        </style>
        """,
        unsafe_allow_html=True
    )

# -------------------------------
# Sidebar controls (no productivity slider)
# -------------------------------
def sidebar_controls(default_output: int):
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
# Export functions (with header/preamble + comparison)
# -------------------------------
def export_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

def _render_preamble(meta: dict | None) -> str:
    from datetime import datetime
    if not meta:
        return ""
    today = meta.get("today")
    if hasattr(today, "strftime"):
        dt = today.strftime("%-d %B %Y")
    else:
        dt = str(today)
    customer = meta.get("customer", "")
    prison = meta.get("prison", "")
    region = meta.get("region", "")
    legal = (
        "We are pleased to set out below the terms of our Quotation for the Goods and/or Services you are "
        "currently seeking. We confirm that this Quotation and any subsequent contract entered into as a result "
        "is, and will be, subject exclusively to our Standard Conditions of Sale of Goods and/or Services a copy "
        "of which is available on request. Please note that all prices are exclusive of VAT and carriage costs at "
        "time of order of which the customer shall be additionally liable to pay."
    )
    return (
        f"<p><strong>Date:</strong> {dt}<br/>"
        f"<strong>Customer:</strong> {customer}<br/>"
        f"<strong>Prison:</strong> {prison}<br/>"
        f"<strong>Region:</strong> {region}</p>"
        f"<p>{legal}</p>"
    )

def export_html(df_host: pd.DataFrame, df_prod: pd.DataFrame,
                title: str, extra_note: str = None, adjusted_df: pd.DataFrame = None,
                meta: dict | None = None, comparison: dict | None = None) -> str:
    styles = """
    <style>
        body { font-family: Arial, sans-serif; }
        table.custom { width: 100%; border-collapse: collapse; margin: 12px 0; }
        table.custom th, table.custom td { border: 1px solid #b1b4b6; padding: 6px 10px; text-align: left; }
        table.custom th { background: #f3f2f1; font-weight: bold; }
        table.custom.highlight { background-color: #fff8dc; }
    </style>
    """
    # Ensure £ renders correctly and avoid stray characters
    html = f"<html><head><meta charset='utf-8' />{styles}</head><body>"
    html += f"<h1>{title}</h1>"
    html += _render_preamble(meta)

    if df_host is not None:
        html += "<h3>Host Costs</h3>"
        html += render_table_html(df_host)
    if df_prod is not None:
        html += "<h3>Production Items</h3>"
        html += render_table_html(df_prod)
    if adjusted_df is not None:
        html += "<h3>Adjusted Costs (for review only)</h3>"
        html += render_table_html(adjusted_df, highlight=True)
    if comparison:
        if comparison.get("Host") is not None:
            html += "<h3>Instructor allocation comparison (Host)</h3>"
            html += render_table_html(comparison["Host"])
        if comparison.get("Production") is not None:
            html += "<h3>Instructor allocation comparison (Production)</h3>"
            html += render_table_html(comparison["Production"])

    if extra_note:
        html += f"<div style='margin-top:1em'>{extra_note}</div>"

    html += "</body></html>"
    return html

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
    cls = "custom highlight" if highlight else "custom"
    return df_fmt.to_html(index=False, classes=cls, border=0, justify="left", escape=False)

# -------------------------------
# Allocation comparison helpers
# -------------------------------
def recompute_host_for_allocation(base_inputs: dict, allocation_pct: int):
    """Re-run the host quote at a different instructor allocation % and return (df, total)."""
    import host61
    df, _ctx = host61.generate_host_quote(
        workshop_hours=base_inputs["workshop_hours"],
        num_prisoners=base_inputs["num_prisoners"],
        prisoner_salary=base_inputs["prisoner_salary"],
        num_supervisors=base_inputs["num_supervisors"],
        customer_covers_supervisors=base_inputs["customer_covers_supervisors"],
        supervisor_salaries=base_inputs["supervisor_salaries"],
        region=base_inputs["region"],
        contracts=base_inputs["contracts"],
        employment_support=base_inputs["employment_support"],
        instructor_allocation=allocation_pct,
        lock_overheads=base_inputs["lock_overheads"],
    )
    total = 0.0
    try:
        if {"Item", "Amount (£)"}.issubset(df.columns):
            mask = df["Item"].astype(str).str.contains("Grand Total", case=False, na=False)
            if mask.any():
                val = pd.to_numeric(df.loc[mask, "Amount (£)"], errors="coerce").dropna()
                if not val.empty:
                    total = float(val.iloc[-1])
    except Exception:
        pass
    return df, total

def recompute_prod_for_allocation(current_df: pd.DataFrame, new_allocation_pct: int, current_allocation_pct: int) -> float:
    """
    Scale the shown Production table's totals by the ratio of new/current allocation.
    This keeps Dev charge as-is (visual comparison only).
    """
    try:
        ratio = (float(new_allocation_pct) / max(1e-9, float(current_allocation_pct)))
        total_col_candidates = [
            "Monthly Total inc VAT (£)", "Monthly Total (inc VAT £)",
            "Monthly Total (£)", "Grand Total (£)"
        ]
        for col in total_col_candidates:
            if col in current_df.columns:
                vals = pd.to_numeric(current_df[col].astype(str).str.replace("£", "").str.replace(",", ""), errors="coerce").fillna(0)
                return float(vals.sum() * ratio)
    except Exception:
        pass
    return 0.0