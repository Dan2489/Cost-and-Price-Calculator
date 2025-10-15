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
            --govuk-red: #d4351c;
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
          table.custom td.neg { color: var(--govuk-red); }
          table.custom tr.grand td { font-weight: bold; }
          table.custom.highlight { background-color: #fff8dc; }
          .muted { color: #505a5f; font-size: 0.95em; }
        </style>
        """,
        unsafe_allow_html=True
    )

# -------------------------------
# Sidebar controls (only labour output visible)
# -------------------------------
def sidebar_controls(default_output: int):
    """
    Keep return shape (lock_overheads, instructor_pct, prisoner_output)
    but only show the Output slider. We hard-return lock_overheads=False,
    instructor_pct=100 (ignored by app), and the chosen output.
    """
    import streamlit as st
    with st.sidebar:
        st.header("Controls")
        prisoner_output = st.slider("Prisoner labour output (%)", 0, 100, default_output, step=5)
    return False, 100, prisoner_output  # lock_overheads, instructor_pct_dummy, prisoner_output

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

def export_csv_bytes_rows(rows: list[dict]) -> bytes:
    df = pd.DataFrame(rows)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

def export_csv_single_row(common_inputs: dict, df_main: pd.DataFrame, df_seg: pd.DataFrame | None) -> bytes:
    """
    Flattens main result table and (optional) segregated table into a single-row CSV.
    """
    out = dict(common_inputs)

    # Main table: pick up to first 4 items (extend if you need more)
    if isinstance(df_main, pd.DataFrame) and not df_main.empty:
        max_items = 4
        for i, (_, r) in enumerate(df_main.iterrows()):
            if i >= max_items:
                break
            prefix = f"Item {i+1}"
            out[f"{prefix} - Name"] = r.get("Item")
            out[f"{prefix} - Output %"] = r.get("Output %")
            out[f"{prefix} - Capacity (units/week)"] = r.get("Capacity (units/week)")
            out[f"{prefix} - Units/week"] = r.get("Units/week")
            out[f"{prefix} - Unit Cost (£)"] = r.get("Unit Cost (£)")
            out[f"{prefix} - Unit Price ex VAT (£)"] = r.get("Unit Price ex VAT (£)")
            out[f"{prefix} - Unit Price inc VAT (£)"] = r.get("Unit Price inc VAT (£)")
            out[f"{prefix} - Monthly Total ex VAT (£)"] = r.get("Monthly Total ex VAT (£)")
            out[f"{prefix} - Monthly Total inc VAT (£)"] = r.get("Monthly Total inc VAT (£)")

        # Totals (if present)
        ex_cols = [c for c in df_main.columns if "Monthly Total ex VAT" in c]
        inc_cols = [c for c in df_main.columns if "Monthly Total inc VAT" in c]
        if ex_cols:
            out["Production: Total Monthly ex VAT (£)"] = float(pd.to_numeric(df_main[ex_cols], errors="coerce").fillna(0).sum())
        if inc_cols:
            out["Production: Total Monthly inc VAT (£)"] = float(pd.to_numeric(df_main[inc_cols], errors="coerce").fillna(0).sum())

    # Segregated table
    if isinstance(df_seg, pd.DataFrame) and not df_seg.empty:
        max_items = 4
        seg_rows = df_seg.to_dict("records")
        # add first N item lines
        seg_item_idx = 0
        for row in seg_rows:
            name = str(row.get("Item", "")).strip()
            if name.lower() in ("instructor salary (monthly)", "grand total (ex vat)"):
                continue
            if seg_item_idx >= max_items:
                break
            prefix = f"Seg Item {seg_item_idx+1}"
            out[f"{prefix} - Name"] = row.get("Item")
            out[f"{prefix} - Output %"] = row.get("Output %")
            out[f"{prefix} - Capacity (units/week)"] = row.get("Capacity (units/week)")
            out[f"{prefix} - Units/week"] = row.get("Units/week")
            out[f"{prefix} - Unit Cost excl Instructor (£)"] = row.get("Unit Cost excl Instructor (£)")
            out[f"{prefix} - Monthly Total excl Instructor ex VAT (£)"] = row.get("Monthly Total excl Instructor ex VAT (£)")
            seg_item_idx += 1

        # instructor + grand total
        instr = next((r for r in seg_rows if str(r.get("Item","")).lower()=="instructor salary (monthly)"), None)
        grand = next((r for r in seg_rows if str(r.get("Item","")).lower()=="grand total (ex vat)"), None)
        if instr:
            out["Seg: Instructor Salary (monthly £)"] = instr.get("Monthly Total excl Instructor ex VAT (£)")
        if grand:
            out["Seg: Grand Total ex VAT (£)"] = grand.get("Monthly Total excl Instructor ex VAT (£)")

    # -> CSV
    buf = io.StringIO()
    pd.DataFrame([out]).to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

def build_header_block(uk_date: str, customer_name: str, prison_name: str, region: str, benefits_text: str = "") -> str:
    base = f"""
    <p class="muted"><strong>Date:</strong> {uk_date}<br/>
    <strong>Customer:</strong> {customer_name}<br/>
    <strong>Prison:</strong> {prison_name}<br/>
    <strong>Region:</strong> {region}</p>
    <p>We are pleased to set out below the terms of our Quotation for the Goods and/or Services you are currently seeking.
    We confirm that this Quotation and any subsequent contract entered into as a result is, and will be, subject exclusively
    to our Standard Conditions of Sale of Goods and/or Services a copy of which is available on request. Please note that
    all prices are exclusive of VAT and carriage costs at time of order of which the customer shall be additionally liable to pay.</p>
    """
    if benefits_text:
        base += f'<p><em>Benefits provided (for pricing consideration):</em> {benefits_text}</p>'
    return base

# -------------------------------
# Table rendering
# -------------------------------
def render_table_html(df: pd.DataFrame, highlight: bool = False) -> str:
    if df is None or df.empty:
        return "<p><em>No data</em></p>"

    df_fmt = df.copy()

    # Currency formatting
    for col in df_fmt.columns:
        if any(key in str(col) for key in ["£", "Cost", "Total", "Price", "Grand", "VAT", "Overheads", "Salary", "charge"]):
            df_fmt[col] = df_fmt[col].apply(lambda x: _fmt_cell(x))

    # Make reductions red (if not already wrapped)
    if "Item" in df_fmt.columns:
        def _maybe_red(x):
            s = str(x)
            low = s.lower()
            if ("reduction" in low or "discount" in low) and "<span" not in s:
                return f'<span style="color:#d4351c">{s}</span>'
            return s
        df_fmt["Item"] = df_fmt["Item"].map(_maybe_red)

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
# Export HTML with header + (optional) segregated
# -------------------------------
def export_html(df_host: pd.DataFrame, df_prod: pd.DataFrame,
                title: str, header_block: str = "", segregated_df: pd.DataFrame | None = None,
                adjusted_df: pd.DataFrame = None) -> str:
    styles = """
    <style>
        body { font-family: Arial, sans-serif; font-size: 14px; }
        h1, h2, h3 { margin: 0.2em 0; }
        .section { margin-top: 1.0em; }
        .muted { color: #505a5f; }
        .red { color: #d4351c; }
        table.custom { width: 100%; border-collapse: collapse; margin: 12px 0; }
        table.custom th, table.custom td { border: 1px solid #b1b4b6; padding: 6px 10px; text-align: left; }
        table.custom th { background: #f3f2f1; font-weight: bold; }
    </style>
    """
    html = f"<html><head><meta charset='utf-8' />{styles}</head><body>"  # ensure £ renders correctly
    html += f"<h1>{title}</h1>"
    if header_block:
        html += header_block

    # Host or Production main table
    if df_host is not None:
        html += "<div class='section'><h3>Summary</h3>"
        html += render_table_html(df_host)
        html += "</div>"
    if df_prod is not None:
        html += "<div class='section'><h3>Summary</h3>"
        html += render_table_html(df_prod)
        html += "</div>"

    # Segregated (Production)
    if segregated_df is not None and not segregated_df.empty:
        html += "<div class='section'><h3>Segregated Costs</h3>"
        html += render_table_html(segregated_df)
        html += "</div>"

    # Optional adjusted table
    if adjusted_df is not None:
        html += "<div class='section'><h3>Adjusted Costs (for review only)</h3>"
        html += render_table_html(adjusted_df)
        html += "</div>"

    html += "</body></html>"
    return html

# -------------------------------
# Adjust table for productivity (kept for compatibility)
# -------------------------------
def adjust_table(df: pd.DataFrame, factor: float) -> pd.DataFrame:
    """Scale numeric/currency values by factor and return formatted copy."""
    if df is None or df.empty:
        return df

    df_adj = df.copy()
    for col in df_adj.columns:
        if any(key in str(col) for key in ["£", "Cost", "Total", "Price", "Grand"]):
            def try_scale(val):
                try:
                    v = float(str(val).replace("£", "").replace(",", ""))
                    return fmt_currency(v * factor)
                except Exception:
                    return val
            df_adj[col] = df_adj[col].map(try_scale)
    return df_adj