import io
import pandas as pd
from typing import Optional, Dict, Any, List

# -------------------------------
# GOV.UK styling
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
            --govuk-grey: #b1b4b6;
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
            border: 1px solid var(--govuk-grey);
            padding: 6px 10px;
            text-align: left;
            vertical-align: top;
          }
          table.custom th {
            background: #f3f2f1;
            font-weight: bold;
          }
          table.custom td.neg { color: var(--govuk-red); }
          table.custom tr.grand td { font-weight: bold; }
          /* Make discount & reduction rows red */
          table.custom td .discount, table.custom td .reduction { color: var(--govuk-red); }
        </style>
        """,
        unsafe_allow_html=True
    )

# -------------------------------
# Sidebar controls (simplified)
# -------------------------------
def sidebar_controls(default_output: int) -> int:
    """
    Only return Prisoner labour output (%) as requested.
    Old controls (lock_overheads, instructor %) removed.
    """
    import streamlit as st
    with st.sidebar:
        st.header("Controls")
        prisoner_output = st.slider(
            "Prisoner labour output (%)",
            min_value=0, max_value=100,
            value=int(default_output), step=1
        )
    return prisoner_output

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
        # If already looks like currency, normalise
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
    """
    Renders a DataFrame with:
    - Currency formatting for columns named with key words.
    - Negative values in red.
    - Any row whose Item contains 'discount' or 'reduction' shows the Item in red.
    """
    if df is None or df.empty:
        return "<p><em>No data</em></p>"

    df_fmt = df.copy()
    # Detect currency-ish columns by header keywords
    currency_keys = ["£", "Cost", "Total", "Price", "Grand", "Amount"]
    for col in df_fmt.columns:
        if any(key.lower() in str(col).lower() for key in currency_keys):
            df_fmt[col] = df_fmt[col].apply(_fmt_cell)

    # Color negative strings (start with £-)
    for col in df_fmt.columns:
        try:
            def _neg_red(v):
                sv = str(v)
                if sv.startswith("£-") or sv.startswith("-£"):
                    # strip possible formats, keep symbol, add CSS class
                    return f"<span class='discount'>{sv}</span>"
                return sv
            df_fmt[col] = df_fmt[col].apply(_neg_red)
        except Exception:
            pass

    # Red Item labels for reductions/discount
    if "Item" in df_fmt.columns:
        def _maybe_red_item(v):
            s = str(v)
            if ("discount" in s.lower()) or ("reduction" in s.lower()):
                return f"<span class='discount'>{s}</span>"
            return s
        df_fmt["Item"] = df_fmt["Item"].apply(_maybe_red_item)

    cls = "custom highlight" if highlight else "custom"
    return df_fmt.to_html(index=False, classes=cls, border=0, justify="left", escape=False)

# -------------------------------
# Export helpers
# -------------------------------
def export_csv_bytes_rows(rows: List[Dict[str, Any]]) -> bytes:
    """
    Export a list of dict rows to CSV bytes.
    """
    df = pd.DataFrame(rows)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

def export_csv_single_row(common: Dict[str, Any],
                          main_df: Optional[pd.DataFrame],
                          seg_df: Optional[pd.DataFrame]) -> bytes:
    """
    Flattens the 'main_df' (e.g., Production results) and optional 'seg_df' (segregated)
    into a single wide row together with 'common' metadata.
    - Each item row becomes its own set of columns: Item i - Name, ... etc.
    - Seg rows become: Seg Item i - Name, ...
    """
    row = dict(common)  # copy

    # Main table
    if isinstance(main_df, pd.DataFrame) and not main_df.empty:
        # reset index to ensure stable order
        tmp = main_df.reset_index(drop=True)
        for i, r in tmp.iterrows():
            prefix = f"Item {i+1}"
            for c in tmp.columns:
                key = f"{prefix} - {c}"
                row[key] = r.get(c)

    # Segregated table
    if isinstance(seg_df, pd.DataFrame) and not seg_df.empty:
        tmp = seg_df.reset_index(drop=True)
        for i, r in tmp.iterrows():
            prefix = f"Seg Item {i+1}"
            for c in tmp.columns:
                key = f"{prefix} - {c}"
                row[key] = r.get(c)

    # Export
    return export_csv_bytes_rows([row])

# -------------------------------
# Header block for PDFs/HTML
# -------------------------------
def build_header_block(*, uk_date: str, customer_name: str, prison_name: str, region: str) -> str:
    """
    Returns an HTML snippet for the quote header + boilerplate text.
    """
    boiler = (
        "<p>We are pleased to set out below the terms of our Quotation for the Goods and/or Services you are "
        "currently seeking. We confirm that this Quotation and any subsequent contract entered into as a result "
        "is, and will be, subject exclusively to our Standard Conditions of Sale of Goods and/or Services a copy "
        "of which is available on request. Please note that all prices are exclusive of VAT and carriage costs at "
        "time of order of which the customer shall be additionally liable to pay.</p>"
    )
    head = f"""
    <div style="margin-bottom:10px">
      <div><strong>Date:</strong> {uk_date}</div>
      <div><strong>Prison:</strong> {prison_name} ({region})</div>
      <div><strong>Customer:</strong> {customer_name}</div>
    </div>
    <div>{boiler}</div>
    """
    return head

# -------------------------------
# HTML export (PDF-ready)
# -------------------------------
def export_html(df_host: Optional[pd.DataFrame],
                df_prod: Optional[pd.DataFrame],
                title: str,
                header_block: Optional[str] = None) -> str:
    """
    Builds a simple HTML doc with a header + one or both tables.
    Red/discount styling is preserved via render_table_html.
    """
    styles = """
    <style>
        body { font-family: Arial, sans-serif; }
        h1, h2, h3 { margin: 0.4em 0; }
        table.custom { width: 100%; border-collapse: collapse; margin: 12px 0; }
        table.custom th, table.custom td { border: 1px solid #b1b4b6; padding: 6px 10px; text-align: left; }
        table.custom th { background: #f3f2f1; font-weight: bold; }
        table.custom td .discount, table.custom td .reduction { color: #d4351c; }
    </style>
    """
    html = f"<html><head><meta charset='utf-8' />{styles}</head><body>"
    html += f"<h1>{title}</h1>"
    if header_block:
        html += header_block

    if df_host is not None:
        html += "<h3>Summary</h3>"
        html += render_table_html(df_host)

    if df_prod is not None:
        html += "<h3>Summary</h3>"
        html += render_table_html(df_prod)

    html += "</body></html>"
    return html

# -------------------------------
# Adjust table (kept for completeness)
# -------------------------------
def adjust_table(df: pd.DataFrame, factor: float) -> pd.DataFrame:
    """
    Scale numeric/currency values by factor and return formatted copy.
    """
    if df is None or df.empty:
        return df

    df_adj = df.copy()
    currency_keys = ["£", "Cost", "Total", "Price", "Grand", "Amount"]
    for col in df_adj.columns:
        if any(key.lower() in str(col).lower() for key in currency_keys):
            def try_scale(val):
                try:
                    v = float(str(val).replace("£", "").replace(",", ""))
                    return fmt_currency(v * factor)
                except Exception:
                    return val
            df_adj[col] = df_adj[col].map(try_scale)
    return df_adj