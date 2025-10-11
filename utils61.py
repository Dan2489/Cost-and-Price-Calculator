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

          /* Simple, bordered tables */
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

          /* Header block */
          .quote-header { border:1px solid #b1b4b6; padding:12px; margin:12px 0; }
          .quote-header h2 { margin:0 0 8px 0; }
          .quote-grid { display:grid; grid-template-columns: 220px 1fr; gap:6px 16px; }
          .quote-grid div { padding:2px 0; }
          .quote-text { margin: 12px 0; }
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

# -------------------------------
# Basic CSV for a single table
# -------------------------------
def export_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

# -------------------------------
# Full CSV with metadata + all tables
# -------------------------------
def export_csv_bytes_full(
    *,
    meta: dict,
    df_host: pd.DataFrame | None,
    df_prod_main: pd.DataFrame | None,
    df_prod_segregated: pd.DataFrame | None
) -> bytes:
    """
    Produce a flat CSV for Power BI:
      - top: metadata (key/value)
      - then each table with a Section column
    Column names remain consistent across sections where possible.
    """
    frames = []

    # 1) Metadata (key-value)
    if meta:
        meta_df = pd.DataFrame(
            [{"Section": "Metadata", "Field": k, "Value": (fmt_currency(v) if _is_money_field(k) else v)} for k, v in meta.items()]
        )
        frames.append(meta_df)

    # 2) Host table
    if df_host is not None and not df_host.empty:
        host_df = df_host.copy()
        host_df.insert(0, "Section", "Host")
        frames.append(host_df)

    # 3) Production - Standard
    if df_prod_main is not None and not df_prod_main.empty:
        prod_df = df_prod_main.copy()
        prod_df.insert(0, "Section", "Production (Standard)")
        frames.append(prod_df)

    # 4) Production - Segregated
    if df_prod_segregated is not None and not df_prod_segregated.empty:
        seg_df = df_prod_segregated.copy()
        seg_df.insert(0, "Section", "Production (Segregated)")
        frames.append(seg_df)

    if not frames:
        return export_csv_bytes(pd.DataFrame([{"Note": "No data"}]))

    final = pd.concat(frames, axis=0, ignore_index=True)
    buf = io.StringIO()
    final.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

def _is_money_field(k: str) -> bool:
    k_lower = str(k).lower()
    money_keys = ["salary", "rate", "price", "charge", "total", "amount", "cost", "value", "unit price"]
    return any(mk in k_lower for mk in money_keys)

# -------------------------------
# HTML exporter with header + tables
# -------------------------------
def export_html(
    df_host: pd.DataFrame | None,
    df_prod: pd.DataFrame | None,
    *,
    title: str,
    meta: dict | None = None,
    extra_note: str | None = None,
    adjusted_df: pd.DataFrame | None = None,
    df_prod_segregated: pd.DataFrame | None = None
) -> str:
    styles = """
    <style>
        body { font-family: Arial, sans-serif; }
        table.custom { width: 100%; border-collapse: collapse; margin: 12px 0; }
        table.custom th, table.custom td { border: 1px solid #b1b4b6; padding: 6px 10px; text-align: left; }
        table.custom th { background: #f3f2f1; font-weight: bold; }
        table.custom.highlight { background-color: #fff8dc; }
        .quote-header { border:1px solid #b1b4b6; padding:12px; margin:12px 0; }
        .quote-header h2 { margin:0 0 8px 0; }
        .quote-grid { display:grid; grid-template-columns: 220px 1fr; gap:6px 16px; }
        .quote-grid div { padding:2px 0; }
        .quote-text { margin: 12px 0; }
    </style>
    """
    html = f"<html><head><meta charset='utf-8' />{styles}</head><body>"
    html += f"<h1>{title}</h1>"

    # Header meta block
    if meta:
        def _fmt_bool(v):
            return "Yes" if bool(v) else "No"

        grid_rows_html = ""
        order = [
            ("Prison", "prison_name"),
            ("Region", "region"),
            ("Customer", "customer_name"),
            ("Date", "date"),
            ("Contract Type", "contract_type"),
            ("Employment Support", "employment_support"),
            ("Hours Open / Week", "workshop_hours"),
            ("Prisoners Employed / Week", "num_prisoners"),
            ("Prisoner Salary / Week", "prisoner_salary"),
            ("Instructors (count)", "num_supervisors"),
            ("Customer Provides Instructors?", "customer_covers_supervisors"),
            ("Instructor Allocation (%)", "instructor_allocation"),
            ("Recommended Allocation (%)", "recommended_allocation"),
            ("Contracts Overseen", "contracts"),
            ("Lock Overheads to Highest?", "lock_overheads"),
        ]
        for label, key in order:
            val = meta.get(key, "")
            if key in ("prisoner_salary",):
                val = fmt_currency(val)
            if key in ("customer_covers_supervisors", "lock_overheads"):
                val = _fmt_bool(val)
            grid_rows_html += f"<div><strong>{label}</strong></div><div>{val}</div>"

        html += (
            "<div class='quote-header'>"
            "<h2>Quotation Details</h2>"
            f"<div class='quote-grid'>{grid_rows_html}</div>"
            "</div>"
        )

    # Standard quotation text
    html += (
        "<div class='quote-text'>"
        "<p>We are pleased to set out below the terms of our Quotation for the Goods and/or Services you are currently seeking. "
        "We confirm that this Quotation and any subsequent contract entered into as a result is, and will be, subject exclusively "
        "to our Standard Conditions of Sale of Goods and/or Services a copy of which is available on request. "
        "Please note that all prices are exclusive of VAT and carriage costs at time of order of which the customer shall be "
        "additionally liable to pay.</p>"
        "</div>"
    )

    # Tables
    if df_host is not None:
        html += "<h2>Host — Summary</h2>"
        html += render_table_html(df_host)
    if df_prod is not None:
        html += "<h2>Production — Summary</h2>"
        html += render_table_html(df_prod)
    if df_prod_segregated is not None:
        html += "<h2>Production — Segregated View (Instructor shown separately)</h2>"
        html += render_table_html(df_prod_segregated)

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

    df_fmt = df.copy()
    for col in df_fmt.columns:
        if any(key in col for key in ["£", "Cost", "Total", "Price", "Grand", "Amount"]):
            df_fmt[col] = df_fmt[col].apply(_fmt_cell)

    cls = "custom highlight" if highlight else "custom"
    return df_fmt.to_html(index=False, classes=cls, border=0, justify="left", escape=False)

def _fmt_cell(x):
    if pd.isna(x):
        return ""
    s = str(x).strip()
    if s == "":
        return ""
    try:
        # already currency?
        if "£" in s:
            s_num = s.replace("£", "").replace(",", "")
            return fmt_currency(float(s_num))
        return fmt_currency(float(s))
    except Exception:
        return s

# -------------------------------
# Adjust table for productivity (still available if needed)
# -------------------------------
def adjust_table(df: pd.DataFrame, factor: float) -> pd.DataFrame:
    """Scale numeric/currency values by factor and return formatted copy."""
    if df is None or df.empty:
        return df

    df_adj = df.copy()
    for col in df_adj.columns:
        if any(key in col for key in ["£", "Cost", "Total", "Price", "Grand", "Amount"]):
            def try_scale(val):
                try:
                    v = float(str(val).replace("£", "").replace(",", ""))
                    return fmt_currency(v * factor)
                except Exception:
                    return val
            df_adj[col] = df_adj[col].map(try_scale)
    return df_adj