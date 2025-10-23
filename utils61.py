# utils61.py
import io
import pandas as pd

# -------------------------------
# GOV.UK styling + responsive sidebar
# -------------------------------
def inject_govuk_css():
    import streamlit as st
    # Add minimal spacing; extend with GOV.UK CSS if you wish
    st.markdown(
        """
        <style>
          .custom table { width: 100%; border-collapse: collapse; }
          .custom th, .custom td { padding: 6px 8px; border-bottom: 1px solid #e5e5e5; text-align: left; }
          .custom th { background: #f3f2f1; font-weight: 600; }
          .highlight td { background: #fff7bf; }
        </style>
        """,
        unsafe_allow_html=True
    )

# -------------------------------
# Sidebar controls (simplified)
# -------------------------------
def sidebar_controls(default_output: int):
    import streamlit as st
    with st.sidebar:
        st.header("Controls")
        prisoner_output = st.slider("Prisoner labour output (%)", 0, 100, default_output, step=5)
    return prisoner_output

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

def export_csv_single_row(common: dict, main_df: pd.DataFrame) -> bytes:
    """
    Flattens 'common' inputs + the visible main table into a single-row CSV.
    Segregated/secondary tables have been removed per requirement.
    """
    row = {**common}

    # Per-item fields from main_df
    if main_df is not None and not main_df.empty and "Item" in main_df.columns:
        for idx, (_, r) in enumerate(main_df.iterrows(), start=1):
            prefix = f"Item {idx} - "
            row[prefix + "Name"] = str(r.get("Item", ""))
            if "Output %" in main_df.columns:
                row[prefix + "Output %"] = r.get("Output %", "")
            if "Capacity (units/week)" in main_df.columns:
                row[prefix + "Capacity (units/week)"] = r.get("Capacity (units/week)", "")
            if "Units/week" in main_df.columns:
                row[prefix + "Units/week"] = r.get("Units/week", "")
            # Try to cover common numeric columns
            for col in [
                "Unit Cost (£)",
                "Unit Price inc VAT (£)",
                "Monthly Total ex VAT (£)",
                "Monthly Total inc VAT (£)",
                "Unit Cost (Prisoner Wage only £)",
                "Units to cover costs",
                "Unit Cost (ex VAT £)",
                "Unit Cost (inc VAT £)",
                "Line Total (ex VAT £)",
                "Line Total (inc VAT £)",
                "Units",
            ]:
                if col in main_df.columns:
                    row[prefix + col] = _to_float(r.get(col))

        # Totals across visible monetary columns (if present)
        if "Monthly Total ex VAT (£)" in main_df.columns:
            row["Production: Total Monthly ex VAT (£)"] = float(
                pd.to_numeric(main_df["Monthly Total ex VAT (£)"], errors="coerce").fillna(0).sum()
            )
        if "Monthly Total inc VAT (£)" in main_df.columns:
            row["Production: Total Monthly inc VAT (£)"] = float(
                pd.to_numeric(main_df["Monthly Total inc VAT (£)"], errors="coerce").fillna(0).sum()
            )

    return export_csv_bytes_rows([row])

# -------------------------------
# HTML export (PDF-ready)
# -------------------------------
def export_html(df_host, df_prod, *, title: str, header_block: str | None = None) -> str:
    styles = """
    <style>
      body { font-family: Arial, Helvetica, sans-serif; color: #0b0c0c; }
      h1 { font-size: 20px; margin: 0 0 10px 0; }
      .block { margin: 10px 0 20px 0; }
      table { width: 100%; border-collapse: collapse; }
      th, td { padding: 6px 8px; border-bottom: 1px solid #e5e5e5; text-align: left; }
      th { background: #f3f2f1; font-weight: 600; }
    </style>
    """
    html = f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{title}</title>{styles}</head><body>"
    html += f"<h1>{title}</h1>"
    if header_block:
        html += f"<div class='block'>{header_block}</div>"
    if df_host is not None:
        html += render_table_html(df_host)
    if df_prod is not None:
        html += render_table_html(df_prod)
    html += "</body></html>"
    return html

# -------------------------------
# Header block builder
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
        f"<p><strong>Date:</strong> {uk_date}</p>",
        f"<p><strong>Customer:</strong> {customer_name}</p>",
        f"<p><strong>Prison:</strong> {prison_name}</p>",
        f"<p><strong>Region:</strong> {region}</p>",
        f"<p>{p}</p>",
    ]
    return "".join(parts)

# -------------------------------
# Table rendering
# -------------------------------
def render_table_html(df: pd.DataFrame, highlight: bool = False) -> str:
    if df is None or df.empty:
        return ""
    df_fmt = df.copy()
    for col in df_fmt.columns:
        if any(key in col for key in ["£", "Cost", "Total", "Price", "Grand", "Amount"]):
            df_fmt[col] = df_fmt[col].apply(_fmt_cell)
    cls = "custom highlight" if highlight else "custom"
    return df_fmt.to_html(index=False, classes=cls, border=0, justify="left", escape=False)

# -------------------------------
# Adjust table (scale money-like columns)
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
