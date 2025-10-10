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
          .note { font-size: 0.95rem; }
          .muted { color: #505a5f; }
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
    if pd.isna(x):
        return ""
    s = str(x).strip()
    if s == "":
        return ""
    try:
        # Already a currency string?
        if "£" in s:
            s_num = s.replace("£", "").replace(",", "")
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
        if any(key in col for key in ["£", "Cost", "Total", "Price", "Grand", "VAT"]):
            df_fmt[col] = df_fmt[col].apply(lambda x: _fmt_cell(x))

    cls = "custom highlight" if highlight else "custom"
    return df_fmt.to_html(index=False, classes=cls, border=0, justify="left", escape=False)

# -------------------------------
# Export functions
# -------------------------------
def export_csv_bytes(df: pd.DataFrame) -> bytes:
    """Flat CSV for Power BI (no mixed columns)."""
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

def export_html(
    df_host: pd.DataFrame,
    df_prod: pd.DataFrame,
    *,
    title: str,
    meta_lines: list[str] | None = None,
    legal_block: str | None = None,
    comp1_html: str | None = None,
    comp2_html: str | None = None
) -> str:
    styles = """
    <style>
        body { font-family: Arial, sans-serif; }
        table.custom { width: 100%; border-collapse: collapse; margin: 12px 0; }
        table.custom th, table.custom td { border: 1px solid #b1b4b6; padding: 6px 10px; text-align: left; }
        table.custom th { background: #f3f2f1; font-weight: bold; }
        table.custom.highlight { background-color: #fff8dc; }
        .note { font-size: 0.95rem; }
        .muted { color: #505a5f; }
    </style>
    """
    html = f"<html><head><meta charset='utf-8' />{styles}</head><body>"
    html += f"<h1>{title}</h1>"

    if legal_block:
        html += f"<p class='note'>{legal_block}</p>"

    if meta_lines:
        html += "<p class='muted'>" + "<br/>".join(meta_lines) + "</p>"

    if df_host is not None:
        html += render_table_html(df_host)
    if df_prod is not None:
        html += render_table_html(df_prod)

    if comp1_html:
        html += "<h3>Instructor % Comparison (Unit Pricing)</h3>"
        html += comp1_html
    if comp2_html:
        html += "<h3>Instructor % Comparison (Monthly Breakdown)</h3>"
        html += comp2_html

    html += "</body></html>"
    return html

# -------------------------------
# Build comparison HTML tables
# -------------------------------
def build_comparison_html(df1: pd.DataFrame, df2: pd.DataFrame) -> str:
    """If you prebuild a dataframe for a comparison, render with our style."""
    return render_table_html(df1 if df2 is None else df2)

# -------------------------------
# Build flat CSV rows for Power BI
# -------------------------------
def build_flat_rows_for_csv(
    meta: dict,
    base_df: pd.DataFrame | None,
    comp_unit_df: pd.DataFrame | None,
    comp_month_df: pd.DataFrame | None
) -> pd.DataFrame:
    """Flatten everything into a clean, one-row-per-scenario CSV."""
    rows: list[dict] = []

    # Base summary rows (if any)
    if base_df is not None and not base_df.empty:
        for _, r in base_df.iterrows():
            rows.append({
                "section": "summary",
                **meta,
                **{k: r.get(k, "") for k in base_df.columns}
            })

    # Comparison – unit
    if comp_unit_df is not None and not comp_unit_df.empty:
        for _, r in comp_unit_df.iterrows():
            rows.append({
                "section": "comparison_unit",
                **meta,
                **{k: r.get(k, "") for k in comp_unit_df.columns}
            })

    # Comparison – month
    if comp_month_df is not None and not comp_month_df.empty:
        for _, r in comp_month_df.iterrows():
            rows.append({
                "section": "comparison_month",
                **meta,
                **{k: r.get(k, "") for k in comp_month_df.columns}
            })

    return pd.DataFrame(rows)