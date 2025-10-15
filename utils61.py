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
          :root { --govuk-green:#00703c; --govuk-yellow:#ffdd00; }
          .stButton > button {
            background: var(--govuk-green) !important;
            color:#fff !important; border:2px solid transparent !important;
            border-radius:0 !important; font-weight:600;
          }
          .stButton > button:hover { filter: brightness(0.95); }
          .stButton > button:focus {
            outline:3px solid var(--govuk-yellow) !important;
            box-shadow:0 0 0 1px #000 inset !important;
          }
          table.custom { width:100%; border-collapse:collapse; margin:12px 0; }
          table.custom th, table.custom td {
            border:1px solid #b1b4b6; padding:6px 10px; text-align:left;
          }
          table.custom th { background:#f3f2f1; font-weight:bold; }
          table.custom td.neg { color:#d4351c; }
          table.custom tr.grand td { font-weight:bold; }
          table.custom.highlight { background-color:#fff8dc; }
        </style>
        """,
        unsafe_allow_html=True
    )

# -------------------------------
# Sidebar controls (ONLY labour output slider now)
# -------------------------------
def sidebar_controls(default_output: int):
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
# Export functions
# -------------------------------
def export_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

def export_csv_bytes_rows(rows: list[dict]) -> bytes:
    df = pd.DataFrame(rows)
    return export_csv_bytes(df)

def export_csv_single_row(common: dict, df_main: pd.DataFrame, seg_df: pd.DataFrame | None) -> bytes:
    row = dict(common)
    # Flatten up to 20 items from df_main
    if df_main is not None and not df_main.empty:
        for i, (_, r) in enumerate(df_main.iterrows()):
            if i >= 20: break
            row[f"Item {i+1} - Name"] = r.get("Item")
            row[f"Item {i+1} - Output %"] = r.get("Output %")
            row[f"Item {i+1} - Capacity (units/week)"] = r.get("Capacity (units/week)")
            row[f"Item {i+1} - Units/week"] = r.get("Units/week")
            row[f"Item {i+1} - Unit Cost (£)"] = r.get("Unit Cost (£)")
            row[f"Item {i+1} - Unit Price ex VAT (£)"] = r.get("Unit Price ex VAT (£)")
            row[f"Item {i+1} - Unit Price inc VAT (£)"] = r.get("Unit Price inc VAT (£)")
            row[f"Item {i+1} - Monthly Total ex VAT (£)"] = r.get("Monthly Total ex VAT (£)")
            row[f"Item {i+1} - Monthly Total inc VAT (£)"] = r.get("Monthly Total inc VAT (£)")
        # totals if present
        for col in ["Monthly Total ex VAT (£)", "Monthly Total inc VAT (£)"]:
            if col in df_main.columns:
                try:
                    row[f"Production: Total {col}"] = float(pd.to_numeric(df_main[col], errors="coerce").fillna(0).sum())
                except Exception:
                    pass
    # Segregated
    if seg_df is not None and not seg_df.empty:
        for i, (_, r) in enumerate(seg_df.iterrows()):
            if i >= 20: break
            row[f"Seg Item {i+1} - Name"] = r.get("Item")
            row[f"Seg Item {i+1} - Output %"] = r.get("Output %")
            row[f"Seg Item {i+1} - Capacity (units/week)"] = r.get("Capacity (units/week)")
            row[f"Seg Item {i+1} - Units/week"] = r.get("Units/week")
            row[f"Seg Item {i+1} - Unit Cost excl Instructor (£)"] = r.get("Unit Cost excl Instructor (£)")
            row[f"Seg Item {i+1} - Monthly Total excl Instructor ex VAT (£)"] = r.get("Monthly Total excl Instructor ex VAT (£)")
        # try capture the last two rows by name
        m_inst = seg_df["Item"].astype(str) == "Instructor Salary (monthly)"
        if m_inst.any():
            row["Seg: Instructor Salary (monthly £)"] = seg_df.loc[m_inst, "Monthly Total excl Instructor ex VAT (£)"].iloc[-1]
        m_gt = seg_df["Item"].astype(str) == "Grand Total (ex VAT)"
        if m_gt.any():
            row["Seg: Grand Total ex VAT (£)"] = seg_df.loc[m_gt, "Monthly Total excl Instructor ex VAT (£)"].iloc[-1]

    return export_csv_bytes_rows([row])

def export_html(df_host: pd.DataFrame | None,
                df_prod: pd.DataFrame | None,
                title: str,
                header_block: str | None = None,
                segregated_df: pd.DataFrame | None = None,
                prepend_html: str | None = None) -> str:
    styles = """
    <style>
        body { font-family: Arial, sans-serif; }
        table.custom { width: 100%; border-collapse: collapse; margin: 12px 0; }
        table.custom th, table.custom td { border: 1px solid #b1b4b6; padding: 6px 10px; text-align: left; }
        table.custom th { background: #f3f2f1; font-weight: bold; }
        table.custom.highlight { background-color: #fff8dc; }
        .muted { color:#505a5f; }
    </style>
    """
    html = f"<html><head><meta charset='utf-8' />{styles}</head><body>"
    html += f"<h1>{title}</h1>"

    if header_block:
        html += header_block
    if prepend_html:
        html += prepend_html

    if df_host is not None:
        html += render_table_html(df_host)
    if df_prod is not None:
        html += render_table_html(df_prod)
    if segregated_df is not None:
        html += "<h3>Segregated Costs (for review)</h3>"
        html += render_table_html(segregated_df, highlight=False)

    html += "</body></html>"
    return html

# -------------------------------
# Table rendering
# -------------------------------
def render_table_html(df: pd.DataFrame, highlight: bool = False) -> str:
    if df is None or df.empty:
        return "<p><em>No data</em></p>"

    df_fmt = df.copy()
    # format currency / negative in red for "Reduction"
    if "Item" in df_fmt.columns and "Amount (£)" in df_fmt.columns:
        def _fmt_amt(lbl, val):
            try:
                v = float(str(val).replace("£", "").replace(",", ""))
            except Exception:
                return val
            s = fmt_currency(v)
            if "Reduction" in str(lbl) or "benefits" in str(lbl).lower():
                return f"<span style='color:#d4351c'>{s}</span>"
            return s
        df_fmt["Amount (£)"] = [
            _fmt_amt(lbl, val) for lbl, val in zip(df_fmt["Item"], df_fmt["Amount (£)"])
        ]

    for col in df_fmt.columns:
        if any(key in col for key in ["£", "Cost", "Total", "Price", "Grand"]):
            try:
                df_fmt[col] = df_fmt[col].apply(lambda x: _fmt_cell(x))
            except Exception:
                pass
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
# Adjust table (kept for compatibility)
# -------------------------------
def adjust_table(df: pd.DataFrame, factor: float) -> pd.DataFrame:
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

# -------------------------------
# Header & summary helpers
# -------------------------------
def build_header_block(uk_date: str, customer_name: str, prison_name: str, region: str, benefits_desc: str = "") -> str:
    quote_text = (
        "<p>We are pleased to set out below the terms of our Quotation for the Goods and/or Services you are "
        "currently seeking. We confirm that this Quotation and any subsequent contract entered into as a result "
        "is, and will be, subject exclusively to our Standard Conditions of Sale of Goods and/or Services a copy "
        "of which is available on request. Please note that all prices are exclusive of VAT and carriage costs at "
        "time of order of which the customer shall be additionally liable to pay.</p>"
    )
    extra = f"<p class='muted'><strong>Date:</strong> {uk_date}<br><strong>Customer:</strong> {customer_name}<br><strong>Prison:</strong> {prison_name} ({region})</p>"
    if benefits_desc.strip():
        extra += f"<p><em>Additional benefits noted:</em> {benefits_desc.strip()}</p>"
    return quote_text + extra

def build_host_summary_block(df_host: pd.DataFrame) -> str:
    # Extract desired rows if present, hide if 0
    def pick(label):
        try:
            m = df_host["Item"].astype(str) == label
            if m.any():
                val = float(str(df_host.loc[m, "Amount (£)"].iloc[-1]).replace("£", "").replace(",", ""))
                if abs(val) < 0.005:
                    return None
                return val
        except Exception:
            return None
        return None

    parts = [
        ("Prisoner Wages", pick("Prisoner Wages")),
        ("Instructor Salary", pick("Instructor Salary")),
        ("Overheads", pick("Overheads")),
        ("Development charge", pick("Development charge")),
        ("Development Reduction", pick("Development Reduction")),
        ("Revised development charge", pick("Revised development charge")),
        ("Additional benefits reduction", pick("Additional benefits reduction")),
        ("Grand Total", pick("Grand Total")),
        ("VAT", pick("VAT")),
        ("Grand Total + VAT", (pick("Grand Total") or 0) + (pick("VAT") or 0) if (pick("Grand Total") is not None and pick("VAT") is not None) else None),
    ]

    rows = []
    for label, val in parts:
        if val is None:
            continue
        disp = fmt_currency(val)
        if "Reduction" in label:
            disp = f"<span style='color:#d4351c'>{disp}</span>"
        rows.append(f"<tr><td>{label}</td><td>{disp}</td></tr>")

    if not rows:
        return ""
    return (
        "<h3>Summary</h3>"
        "<table class='custom'>"
        "<thead><tr><th>Item</th><th>Amount (£/month)</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )