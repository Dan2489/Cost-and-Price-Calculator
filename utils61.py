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
          table.custom td.neg { color: #d4351c; font-weight: bold; }
          table.custom tr.grand td { font-weight: bold; }
          table.custom.highlight { background-color: #fff8dc; }
        </style>
        """,
        unsafe_allow_html=True
    )

# -------------------------------
# Sidebar controls
# -------------------------------
def sidebar_controls(default_output: int):
    import streamlit as st
    with st.sidebar:
        st.header("Controls")
        lock_overheads = st.checkbox("Lock overheads to highest instructor", value=False)
        instructor_pct = st.slider("Instructor Allocation (%)", 0, 100, 100, step=5)
        prisoner_output = st.slider("Prisoner Labour Output (%)", 0, 100, default_output, step=5)
    return lock_overheads, instructor_pct, prisoner_output

# -------------------------------
# Formatters
# -------------------------------
def fmt_currency(val) -> str:
    try:
        return f"£{float(val):,.2f}"
    except Exception:
        return str(val)

# -------------------------------
# Export functions
# -------------------------------
def export_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

def export_html(df_host: pd.DataFrame, df_prod: pd.DataFrame,
                title: str, extra_note: str = None, adjusted_df: pd.DataFrame = None) -> str:
    styles = """
    <style>
        body { font-family: Arial, sans-serif; }
        table.custom { width: 100%; border-collapse: collapse; margin: 12px 0; }
        table.custom th, table.custom td { border: 1px solid #b1b4b6; padding: 6px 10px; text-align: left; }
        table.custom th { background: #f3f2f1; font-weight: bold; }
        table.custom td.neg { color: #d4351c; font-weight: bold; }
        table.custom.highlight { background-color: #fff8dc; }
    </style>
    """
    html = f"<html><head>{styles}</head><body>"
    html += f"<h1>{title}</h1>"

    if df_host is not None:
        html += render_table_html(df_host)
    if df_prod is not None:
        html += render_table_html(df_prod)
    if adjusted_df is not None:
        html += "<h3>Adjusted Costs (for review only)</h3>"
        html += render_table_html(adjusted_df, highlight=True)

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

    rows_html = []
    for _, row in df.iterrows():
        item = str(row["Item"])
        val = row["Amount (£)"]

        # format value (prevent double "£")
        try:
            v = float(str(val).replace("£", "").replace(",", ""))
            val_fmt = fmt_currency(v)
        except Exception:
            val_fmt = val

        # CSS classes
        css_class = ""
        if "Reduction" in item:
            css_class = " class='neg'"
        elif "Grand Total" in item:
            css_class = " class='grand'"

        rows_html.append(f"<tr><td>{item}</td><td{css_class}>{val_fmt}</td></tr>")

    header = "<tr><th>Item</th><th>Amount (£)</th></tr>"
    table_html = f"<table class='custom{' highlight' if highlight else ''}'>{header}{''.join(rows_html)}</table>"
    return table_html

# -------------------------------
# Adjust table for productivity
# -------------------------------
def adjust_table(df: pd.DataFrame, factor: float) -> pd.DataFrame:
    """Scale numeric/currency values by factor and return formatted copy.
       Handles Development Charge vs Revised Development Charge properly."""
    if df is None or df.empty:
        return df

    df_adj = df.copy()
    has_revised = any("Revised Development Charge" in str(i) for i in df_adj["Item"])

    for idx, row in df_adj.iterrows():
        item = str(row["Item"])
        val = row["Amount (£)"]

        try:
            v = float(str(val).replace("£", "").replace(",", ""))
        except Exception:
            continue

        # If Revised exists: scale only Revised + Reduction + totals + wages/overheads
        if has_revised:
            if "Revised Development Charge" in item or "Reduction" in item:
                df_adj.at[idx, "Amount (£)"] = fmt_currency(v * factor)
            elif any(k in item for k in ["Grand Total", "Subtotal", "VAT", "Wages", "Salary", "Overheads"]):
                df_adj.at[idx, "Amount (£)"] = fmt_currency(v * factor)
        else:
            # No Revised: scale Development Charge + totals + wages/overheads
            if "Development Charge" in item or any(k in item for k in ["Grand Total", "Subtotal", "VAT", "Wages", "Salary", "Overheads"]):
                df_adj.at[idx, "Amount (£)"] = fmt_currency(v * factor)

    return df_adj