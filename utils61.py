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
# Sidebar controls (trimmed)
# -------------------------------
def sidebar_controls(default_output: int):
    """
    We’ve removed lock-overheads & instructor slider per spec.
    Return placeholders so callers can keep unpacking.
    """
    import streamlit as st
    with st.sidebar:
        st.header("Controls")
        prisoner_output = st.slider("Prisoner labour output (%)", 0, 100, default_output, step=5, key="labour_out")
    # (lock_overheads=False, instructor_pct=100 placeholder, prisoner_output)
    return False, 100, prisoner_output

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

def export_csv_single_row(common: dict, df_main: pd.DataFrame, segregated_df: pd.DataFrame | None) -> bytes:
    """
    Flatten df_main (quote table) into single-row columns after the shared 'common' fields.
    """
    row = dict(common)
    # take up to 20 items safely
    max_items = 20
    if df_main is not None and not df_main.empty and {"Item","Amount (£)"}.issubset(df_main.columns):
        items = df_main.reset_index(drop=True)
        for i in range(min(max_items, len(items))):
            item = str(items.loc[i, "Item"])
            amt = items.loc[i, "Amount (£)"]
            try:
                amt = float(str(amt).replace("£","").replace(",",""))
            except Exception:
                amt = None
            row[f"Line {i+1} - Item"] = item
            row[f"Line {i+1} - Amount (£)"] = amt

    if segregated_df is not None and not segregated_df.empty:
        seg = segregated_df.reset_index(drop=True)
        for i in range(min(20, len(seg))):
            item = str(seg.loc[i, "Item"])
            amt = seg.loc[i, seg.columns[-1]]
            try:
                amt = float(str(amt).replace("£","").replace(",",""))
            except Exception:
                amt = None
            row[f"Seg {i+1} - Item"] = item
            row[f"Seg {i+1} - Amount (£)"] = amt

    buf = io.StringIO()
    pd.DataFrame([row]).to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

def export_html(df_host: pd.DataFrame, df_prod: pd.DataFrame,
                title: str, header_block: dict = None, segregated_df: pd.DataFrame = None) -> str:
    styles = """
    <style>
        body { font-family: Arial, sans-serif; }
        h1 { margin-bottom: 0.2rem; }
        .muted { color: #505a5f; font-size: 0.9rem; }
        table.custom { width: 100%; border-collapse: collapse; margin: 12px 0; }
        table.custom th, table.custom td { border: 1px solid #b1b4b6; padding: 6px 10px; text-align: left; }
        table.custom th { background: #f3f2f1; font-weight: bold; }
        table.custom.highlight { background-color: #fff8dc; }
        .red { color: #d4351c; }
    </style>
    """
    html = f"<html><head><meta charset='utf-8' />{styles}</head><body>"
    html += f"<h1>{title}</h1>"
    if header_block:
        html += f"<div class='muted'>Customer: <strong>{header_block.get('customer')}</strong> · Prison: <strong>{header_block.get('prison')}</strong> · Region: <strong>{header_block.get('region')}</strong> · Date: {header_block.get('date')}</div>"
        if header_block.get("benefits"):
            html += f"<div class='muted'>Benefits: {header_block.get('benefits')}</div>"
        html += (
            "<p>We are pleased to set out below the terms of our Quotation for the Goods and/or Services you are "
            "currently seeking. We confirm that this Quotation and any subsequent contract entered into as a result "
            "is, and will be, subject exclusively to our Standard Conditions of Sale of Goods and/or Services a copy "
            "of which is available on request. Please note that all prices are exclusive of VAT and carriage costs at "
            "time of order of which the customer shall be additionally liable to pay.</p>"
        )

    if df_host is not None:
        html += render_table_html(df_host)
    if df_prod is not None:
        html += render_table_html(df_prod)
    if segregated_df is not None and not segregated_df.empty:
        html += "<h3>Segregated Costs</h3>"
        html += render_table_html(segregated_df, highlight=True)

    html += "</body></html>"
    return html

def build_header_block(uk_date: str, customer_name: str, prison_name: str, region: str, benefits_desc: str | None = None) -> dict:
    return {
        "date": uk_date,
        "customer": customer_name,
        "prison": prison_name,
        "region": region,
        "benefits": benefits_desc
    }

# -------------------------------
# Table rendering
# -------------------------------
def render_table_html(df: pd.DataFrame, highlight: bool = False) -> str:
    if df is None or df.empty:
        return "<p><em>No data</em></p>"

    df_fmt = df.copy()
    # currency format
    if "Amount (£)" in df_fmt.columns:
        df_fmt["Amount (£)"] = df_fmt["Amount (£)"].apply(lambda x: _fmt_cell(x))

    # Colour negatives red
    if "Amount (£)" in df_fmt.columns:
        def td(val):
            try:
                v = float(str(val).replace("£","").replace(",",""))
            except Exception:
                v = None
            klass = "neg" if (v is not None and v < 0) else ""
            return f"<span class='{klass}'>{val}</span>"
        df_fmt["Amount (£)"] = df_fmt["Amount (£)"].apply(td)

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
# Adjust table for productivity
# -------------------------------
def adjust_table(df: pd.DataFrame, factor: float) -> pd.DataFrame:
    if df is None or df.empty:
        return df

    df_adj = df.copy()
    for col in df_adj.columns:
        if col == "Amount (£)":
            def try_scale(val):
                try:
                    v = float(str(val).replace("£", "").replace(",", ""))
                    return fmt_currency(v * factor)
                except Exception:
                    return val
            df_adj[col] = df_adj[col].map(try_scale)
    return df_adj