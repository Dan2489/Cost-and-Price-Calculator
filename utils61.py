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
# Sidebar controls (simplified)
# -------------------------------
def sidebar_controls(default_output: int):
    """
    Only returns prisoner_output slider now.
    Lock overheads and Instructor slider removed.
    """
    import streamlit as st
    with st.sidebar:
        st.header("Controls")
        prisoner_output = st.slider("Prisoner labour output (%)", 0, 100, default_output, step=5)
    return prisoner_output

# -------------------------------
# Formatters
# -------------------------------
def fmt_currency(val) -> str:
    try:
        return f"£{float(val):,.2f}"
    except Exception:
        return str(val)

# -------------------------------
# Export helpers
# -------------------------------
def export_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

def export_csv_bytes_rows(rows: list[dict]) -> bytes:
    df = pd.DataFrame(rows)
    return export_csv_bytes(df)

def export_csv_single_row(common: dict, df_main: pd.DataFrame, df_segregated: pd.DataFrame | None) -> bytes:
    """
    Flattens inputs + main table + (optional) segregated table into one single-row CSV.
    """
    out = dict(common)
    # Main table
    if df_main is not None and not df_main.empty:
        for i, (_, r) in enumerate(df_main.iterrows(), start=1):
            for col, val in r.items():
                key = f"Item {i} - {col}"
                out[key] = val
        # Totals (if present)
        for total_col in [
            "Monthly Total ex VAT (£)", "Monthly Total inc VAT (£)"
        ]:
            if total_col in df_main.columns:
                try:
                    out[f"Production: Total {total_col}"] = float(pd.to_numeric(df_main[total_col], errors="coerce").fillna(0).sum())
                except Exception:
                    pass
    # Segregated
    if df_segregated is not None and not df_segregated.empty:
        for i, (_, r) in enumerate(df_segregated.iterrows(), start=1):
            for col, val in r.items():
                key = f"Seg Item {i} - {col}"
                out[key] = val
        # Pull out instructor row / grand total if visible
        try:
            m_inst = df_segregated["Item"].astype(str).str.contains("Instructor Salary", na=False)
            if m_inst.any():
                out["Seg: Instructor Salary (monthly £)"] = df_segregated.loc[m_inst, "Monthly Total excl Instructor ex VAT (£)"].iloc[0]
        except Exception:
            pass
        try:
            m_gt = df_segregated["Item"].astype(str).str.contains("Grand Total", na=False)
            if m_gt.any():
                out["Seg: Grand Total ex VAT (£)"] = df_segregated.loc[m_gt, "Monthly Total excl Instructor ex VAT (£)"].iloc[0]
        except Exception:
            pass
    return export_csv_bytes_rows([out])

# -------------------------------
# HTML export with header & optional segregated table
# -------------------------------
def export_html(df_host: pd.DataFrame | None,
                df_prod: pd.DataFrame | None,
                title: str,
                header_block: str | None = None,
                extra_note: str | None = None,
                adjusted_df: pd.DataFrame | None = None,
                segregated_df: pd.DataFrame | None = None,
                reductions_info: list[str] | None = None) -> str:
    styles = """
    <style>
        body { font-family: Arial, sans-serif; }
        table.custom { width: 100%; border-collapse: collapse; margin: 12px 0; }
        table.custom th, table.custom td { border: 1px solid #b1b4b6; padding: 6px 10px; text-align: left; }
        table.custom th { background: #f3f2f1; font-weight: bold; }
        table.custom.highlight { background-color: #fff8dc; }
        .note { font-style: italic; color: #505a5f; }
    </style>
    """
    html = f"<html><head><meta charset='utf-8' />{styles}</head><body>"
    html += f"<h1>{title}</h1>"

    # Header text block (with quote wording & top fields)
    if header_block:
        html += header_block

    # Host or Production main table
    if df_host is not None:
        html += render_table_html(df_host)
    if df_prod is not None:
        html += render_table_html(df_prod)

    # Optional segregated section
    if segregated_df is not None and not segregated_df.empty:
        html += "<h3>Segregated Costs</h3>"
        html += render_table_html(segregated_df)

    # Optional reductions info (bullets)
    if reductions_info:
        html += "<h4>Benefits Reductions (summary)</h4><ul>"
        for line in reductions_info:
            html += f"<li>{line}</li>"
        html += "</ul>"

    # Adjusted
    if adjusted_df is not None:
        html += "<h3>Adjusted Costs (for review only)</h3>"
        html += render_table_html(adjusted_df, highlight=True)

    if extra_note:
        html += f"<div class='note' style='margin-top:1em'>{extra_note}</div>"

    html += "</body></html>"
    return html

# -------------------------------
# Header builder (with quotation text)
# -------------------------------
def build_header_block(uk_date: str, customer_name: str, prison_name: str, region: str) -> str:
    quote_text = (
        "We are pleased to set out below the terms of our Quotation for the Goods and/or Services you are "
        "currently seeking. We confirm that this Quotation and any subsequent contract entered into as a result "
        "is, and will be, subject exclusively to our Standard Conditions of Sale of Goods and/or Services a copy "
        "of which is available on request. Please note that all prices are exclusive of VAT and carriage costs at "
        "time of order of which the customer shall be additionally liable to pay."
    )
    top = f"""
    <div>
      <p><strong>Date:</strong> {uk_date}</p>
      <p><strong>Customer:</strong> {customer_name}</p>
      <p><strong>Prison:</strong> {prison_name}</p>
      <p><strong>Region:</strong> {region}</p>
    </div>
    <p class="note">{quote_text}</p>
    """
    return top

# -------------------------------
# Table rendering
# -------------------------------
def render_table_html(df: pd.DataFrame, highlight: bool = False) -> str:
    if df is None or df.empty:
        return "<p><em>No data</em></p>"

    df_fmt = df.copy()
    for col in df_fmt.columns:
        if any(key in col for key in ["£", "Cost", "Total", "Price", "Grand", "VAT", "Amount"]):
            df_fmt[col] = df_fmt[col].apply(lambda x: _fmt_cell(x))
    cls = "custom highlight" if highlight else "custom"
    return df_fmt.to_html(index=False, classes=cls, border=0, justify="left", escape=False)

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
# Adjust table for productivity (kept for completeness)
# -------------------------------
def adjust_table(df: pd.DataFrame, factor: float) -> pd.DataFrame:
    """Scale numeric/currency values by factor and return formatted copy."""
    if df is None or df.empty:
        return df

    df_adj = df.copy()
    for col in df_adj.columns:
        if any(key in col for key in ["£", "Cost", "Total", "Price", "Grand"]):
            def try_scale(val):
                try:
                    v = float(str(val).replace("£", "").replace(",", ""))
                    return fmt_currency(v * factor)
                except Exception:
                    return val
            df_adj[col] = df_adj[col].map(try_scale)
    return df_adj