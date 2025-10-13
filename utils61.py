import io
import pandas as pd

# -------------------------------
# GOV.UK styling + responsive sidebar
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

          /* Sidebar width + ensure it can close on mobile */
          [data-testid="stSidebar"] {
            min-width: 320px !important;
            max-width: 320px !important;
          }
          @media (max-width: 768px) {
            [data-testid="stSidebar"] {
              min-width: 280px !important;
              max-width: 280px !important;
            }
          }
        </style>
        """,
        unsafe_allow_html=True
    )

# -------------------------------
# Sidebar controls (unchanged)
# -------------------------------
def sidebar_controls(default_output: int):
    import streamlit as st
    with st.sidebar:
        st.header("Controls")
        lock_overheads = st.checkbox("Lock overheads to highest instructor", value=False)
        instructor_pct = st.slider("Instructor allocation (%)", 0, 100, 100, step=1)
        prisoner_output = st.slider("Prisoner labour output (%)", 0, 100, default_output, step=5)
    return lock_overheads, instructor_pct, prisoner_output

# -------------------------------
# Formatting helpers
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
        if "£" in s:
            s_num = s.replace("£", "").replace(",", "")
            return fmt_currency(float(s_num))
        return fmt_currency(float(s))
    except Exception:
        return s

def _to_float(val):
    try:
        return float(str(val).replace("£", "").replace(",", ""))
    except Exception:
        return None

# -------------------------------
# CSV export helpers
# -------------------------------
def export_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

def export_csv_bytes_rows(rows: list[dict], columns_order: list[str] | None = None) -> bytes:
    if not rows:
        rows = [{}]
    df = pd.DataFrame(rows)
    if columns_order:
        for col in columns_order:
            if col not in df.columns:
                df[col] = ""
        df = df[columns_order]
    return export_csv_bytes(df)

def export_csv_single_row(common: dict, main_df: pd.DataFrame, seg_df: pd.DataFrame | None) -> bytes:
    """
    Single flat row with all common fields first, then per-item fields from main_df,
    then segregated fields (including the instructor salary and grand totals).
    All values numeric where appropriate (no £ signs) so Power BI can ingest easily.
    """
    row = {**common}

    # Per-item fields from main_df
    if main_df is not None and not main_df.empty and "Item" in main_df.columns:
        for idx, (_, r) in enumerate(main_df.iterrows(), start=1):
            prefix = f"Item {idx} - "
            row[prefix + "Name"] = str(r.get("Item", ""))
            row[prefix + "Output %"] = r.get("Output %", "")
            row[prefix + "Capacity (units/week)"] = r.get("Capacity (units/week)", "")
            row[prefix + "Units/week"] = r.get("Units/week", "")
            row[prefix + "Unit Cost (£)"] = _to_float(r.get("Unit Cost (£)"))
            row[prefix + "Unit Price ex VAT (£)"] = _to_float(r.get("Unit Price ex VAT (£)"))
            row[prefix + "Unit Price inc VAT (£)"] = _to_float(r.get("Unit Price inc VAT (£)"))
            row[prefix + "Monthly Total ex VAT (£)"] = _to_float(r.get("Monthly Total ex VAT (£)"))
            row[prefix + "Monthly Total inc VAT (£)"] = _to_float(r.get("Monthly Total inc VAT (£)"))

        # Totals across items (ex/ inc VAT) from main table
        if "Monthly Total ex VAT (£)" in main_df.columns:
            row["Production: Total Monthly ex VAT (£)"] = float(
                pd.to_numeric(main_df["Monthly Total ex VAT (£)"], errors="coerce").fillna(0).sum()
            )
        if "Monthly Total inc VAT (£)" in main_df.columns:
            row["Production: Total Monthly inc VAT (£)"] = float(
                pd.to_numeric(main_df["Monthly Total inc VAT (£)"], errors="coerce").fillna(0).sum()
            )

    # Segregated data
    if seg_df is not None and not seg_df.empty:
        # Per-item (excl instructor)
        if "Item" in seg_df.columns:
            j = 1
            for _, rr in seg_df.iterrows():
                nm = str(rr.get("Item", ""))
                if nm in ("Instructor Salary (monthly)", "Grand Total (ex VAT)"):
                    continue
                prefix = f"Seg Item {j} - "
                row[prefix + "Name"] = nm
                row[prefix + "Output %"] = rr.get("Output %", "")
                row[prefix + "Capacity (units/week)"] = rr.get("Capacity (units/week)", "")
                row[prefix + "Units/week"] = rr.get("Units/week", "")
                row[prefix + "Unit Cost excl Instructor (£)"] = _to_float(rr.get("Unit Cost excl Instructor (£)"))
                row[prefix + "Monthly Total excl Instructor ex VAT (£)"] = _to_float(rr.get("Monthly Total excl Instructor ex VAT (£)"))
                j += 1

            # Instructor salary + grand total
            inst_row = seg_df[seg_df["Item"].astype(str) == "Instructor Salary (monthly)"]
            if not inst_row.empty:
                row["Seg: Instructor Salary (monthly £)"] = _to_float(inst_row.iloc[0]["Monthly Total excl Instructor ex VAT (£)"])

            gt_row = seg_df[seg_df["Item"].astype(str) == "Grand Total (ex VAT)"]
            if not gt_row.empty:
                row["Seg: Grand Total ex VAT (£)"] = _to_float(gt_row.iloc[0]["Monthly Total excl Instructor ex VAT (£)"])

    return export_csv_bytes_rows([row])

# -------------------------------
# HTML export (PDF-ready) – now supports segregated_df
# -------------------------------
def export_html(
    df_host: pd.DataFrame,
    df_prod: pd.DataFrame,
    *,
    title: str,
    header_block: str = None,
    segregated_df: pd.DataFrame | None = None
) -> str:
    styles = """
    <style>
        body { font-family: Arial, sans-serif; }
        h1, h2, h3 { margin-bottom: 0.35rem; }
        .meta { margin-bottom: 0.8rem; }
        table.custom { width: 100%; border-collapse: collapse; margin: 12px 0; }
        table.custom th, table.custom td { border: 1px solid #b1b4b6; padding: 6px 10px; text-align: left; }
        table.custom th { background: #f3f2f1; font-weight: bold; }
        table.custom.highlight { background-color: #fff8dc; }
        .neg { color:#d4351c; }
    </style>
    """
    html = f"<html><head><meta charset='utf-8' />{styles}</head><body>"
    html += f"<h1>{title}</h1>"

    if header_block:
        html += f"<div class='meta'>{header_block}</div>"

    if df_host is not None:
        html += render_table_html(df_host)

    if df_prod is not None:
        html += render_table_html(df_prod)

    if segregated_df is not None and not segregated_df.empty:
        html += "<h3>Segregated Costs</h3>"
        html += render_table_html(segregated_df)

    html += "</body></html>"
    return html

# -------------------------------
# Header block builder (for HTML)
# -------------------------------
def build_header_block(*, uk_date: str, customer_name: str, prison_name: str, region: str) -> str:
    p = (
        "We are pleased to set out below the terms of our Quotation for the Goods and/or Services you are "
        "currently seeking. We confirm that this Quotation and any subsequent contract entered into as a result "
        "is, and will be, subject exclusively to our Standard Conditions of Sale of Goods and/or Services a copy "
        "of which is available on request. Please note that all prices are exclusive of VAT and carriage costs at "
        "time of order of which the customer shall be additionally liable to pay."
    )
    parts = [
        f"<p><strong>Date:</strong> {uk_date}<br/>"
        f"<strong>Customer:</strong> {customer_name}<br/>"
        f"<strong>Prison:</strong> {prison_name}<br/>"
        f"<strong>Region:</strong> {region}</p>",
        f"<p>{p}</p>"
    ]
    return "".join(parts)

# -------------------------------
# Table rendering for app/html
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

# -------------------------------
# Adjust table (kept for backwards compat if needed)
# -------------------------------
def adjust_table(df: pd.DataFrame, factor: float) -> pd.DataFrame:
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