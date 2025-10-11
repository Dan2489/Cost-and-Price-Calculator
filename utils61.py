# utils61.py
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

          /* Make sidebar usable on mobile (collapses cleanly) */
          [data-testid="stSidebar"] {
            min-width: 320px !important;
            max-width: 320px !important;
          }
          @media (max-width: 992px) {
            [data-testid="stSidebar"] {
              position: fixed !important;
              left: 0; top: 0; bottom: 0;
              transform: translateX(-100%);
              transition: transform 0.2s ease;
              z-index: 1000;
            }
            [data-testid="stSidebar"][aria-expanded="true"] {
              transform: translateX(0);
            }
          }
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

# Small helper used by table rendering
def _fmt_cell(x):
    import pandas as pd
    if pd.isna(x):
        return ""
    s = str(x)
    if s.strip() == "":
        return ""
    try:
        # already currency?
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
    if df is None or df.empty:
        return "<p><em>No data</em></p>"

    df_fmt = df.copy()
    for col in df_fmt.columns:
        # Format likely-money columns
        if any(key in col for key in ["£", "Cost", "Total", "Price", "Grand"]):
            df_fmt[col] = df_fmt[col].apply(lambda x: _fmt_cell(x))

    cls = "custom highlight" if highlight else "custom"
    return df_fmt.to_html(index=False, classes=cls, border=0, justify="left", escape=False)

# -------------------------------
# Adjust table for productivity (kept for compatibility)
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

# -------------------------------
# CSV Export — flat, Power BI friendly
# -------------------------------
def export_csv_flat(meta: dict,
                    df_host: pd.DataFrame | None,
                    df_prod_combined: pd.DataFrame | None,
                    df_prod_segregated: pd.DataFrame | None) -> bytes:
    """
    Produces a *flat* CSV with distinct columns for:
      - Host rows (host_* columns)
      - Production Combined rows (prod_* columns)
      - Production Segregated rows (prodseg_* columns)
    Meta fields are repeated on every row.
    """
    rows = []

    # Ensure meta keys exist (stable schema)
    meta_defaults = {
        "prison_name": "", "region": "", "customer_name": "", "date": "",
        "contract_type": "", "employment_support": "",
        "workshop_hours": "", "num_prisoners": "", "prisoner_salary": "",
        "num_supervisors": "", "customer_covers_supervisors": "",
        "instructor_allocation": "", "recommended_allocation": "",
        "contracts": "", "lock_overheads": "", "prisoner_output_percent": "",
    }
    safe_meta = {**meta_defaults, **(meta or {})}

    # Host rows
    if df_host is not None and not df_host.empty:
        for _, r in df_host.iterrows():
            rows.append({
                **safe_meta,
                "table_type": "host",
                "host_item": str(r.get("Item", "")),
                "host_amount_gbp": _number_or_none(r.get("Amount (£)")),
                # empty prod columns
                "prod_item": "", "prod_output_pct": "", "prod_capacity_units_week": "", "prod_units_week": "",
                "prod_unit_cost_gbp": "", "prod_unit_price_ex_vat_gbp": "",
                "prod_monthly_total_ex_vat_gbp": "", "prod_monthly_total_inc_vat_gbp": "",
                # empty prodseg
                "prodseg_item": "", "prodseg_unit_cost_no_instructor_gbp": "",
                "prodseg_instructor_monthly_gbp": "", "prodseg_monthly_total_ex_vat_gbp": "",
                "prodseg_monthly_total_inc_vat_gbp": "",
            })

    # Production — Combined rows
    if df_prod_combined is not None and not df_prod_combined.empty:
        for _, r in df_prod_combined.iterrows():
            rows.append({
                **safe_meta,
                "table_type": "production_combined",
                # empty host
                "host_item": "", "host_amount_gbp": "",
                # combined
                "prod_item": str(r.get("Item", "")),
                "prod_output_pct": _number_or_none(r.get("Output %")),
                "prod_capacity_units_week": _number_or_none(r.get("Capacity (units/week)")),
                "prod_units_week": _number_or_none(r.get("Units/week")),
                "prod_unit_cost_gbp": _number_or_none(r.get("Unit Cost (£)")),
                "prod_unit_price_ex_vat_gbp": _number_or_none(r.get("Unit Price ex VAT (£)")),
                "prod_monthly_total_ex_vat_gbp": _number_or_none(r.get("Monthly Total ex VAT (£)")),
                "prod_monthly_total_inc_vat_gbp": _number_or_none(r.get("Monthly Total inc VAT (£)")),
                # empty prodseg
                "prodseg_item": "", "prodseg_unit_cost_no_instructor_gbp": "",
                "prodseg_instructor_monthly_gbp": "", "prodseg_monthly_total_ex_vat_gbp": "",
                "prodseg_monthly_total_inc_vat_gbp": "",
            })

    # Production — Segregated rows
    if df_prod_segregated is not None and not df_prod_segregated.empty:
        for _, r in df_prod_segregated.iterrows():
            rows.append({
                **safe_meta,
                "table_type": "production_segregated",
                # empty host
                "host_item": "", "host_amount_gbp": "",
                # empty combined key cols we don't repeat here
                "prod_item": "", "prod_output_pct": "", "prod_capacity_units_week": "", "prod_units_week": "",
                "prod_unit_cost_gbp": "", "prod_unit_price_ex_vat_gbp": "",
                "prod_monthly_total_ex_vat_gbp": "", "prod_monthly_total_inc_vat_gbp": "",
                # segregated
                "prodseg_item": str(r.get("Item", "")),
                "prodseg_unit_cost_no_instructor_gbp": _number_or_none(r.get("Unit Cost (no instructor) (£)")),
                "prodseg_instructor_monthly_gbp": _number_or_none(r.get("Instructor Monthly (£)")),
                "prodseg_monthly_total_ex_vat_gbp": _number_or_none(r.get("Monthly Total ex VAT (£)")),
                "prodseg_monthly_total_inc_vat_gbp": _number_or_none(r.get("Monthly Total inc VAT (£)")),
            })

    df_out = pd.DataFrame(rows)
    buf = io.StringIO()
    df_out.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

def _number_or_none(v):
    try:
        if v is None or v == "":
            return ""
        s = str(v).replace("£", "").replace(",", "").strip()
        return float(s)
    except Exception:
        return ""

# -------------------------------
# HTML Export (PDF-ready)
# -------------------------------
def export_html(df_host: pd.DataFrame | None,
                df_prod: pd.DataFrame | None,
                *,
                title: str,
                meta: dict | None = None,
                df_prod_segregated: pd.DataFrame | None = None,
                extra_note: str | None = None) -> str:
    """
    Builds a UTF-8 HTML with header, quotation text, and any tables passed in.
    """
    meta = meta or {}
    styles = """
    <style>
        body { font-family: Arial, sans-serif; }
        h1 { margin-bottom: 0.25rem; }
        .meta { margin: 0.25rem 0 1rem 0; font-size: 0.95rem; }
        table.custom { width: 100%; border-collapse: collapse; margin: 12px 0; }
        table.custom th, table.custom td { border: 1px solid #b1b4b6; padding: 6px 10px; text-align: left; }
        table.custom th { background: #f3f2f1; font-weight: bold; }
        table.custom.highlight { background-color: #fff8dc; }
        .neg { color: #d4351c; }
    </style>
    """

    # Quotation preamble (as requested)
    quote_txt = (
        "We are pleased to set out below the terms of our Quotation for the Goods and/or Services you are "
        "currently seeking. We confirm that this Quotation and any subsequent contract entered into as a result "
        "is, and will be, subject exclusively to our Standard Conditions of Sale of Goods and/or Services a copy "
        "of which is available on request. Please note that all prices are exclusive of VAT and carriage costs at "
        "time of order of which the customer shall be additionally liable to pay."
    )

    html = f"<html><head><meta charset='utf-8' />{styles}</head><body>"
    html += f"<h1>{title}</h1>"
    html += (
        "<div class='meta'>"
        f"<strong>Prison:</strong> {meta.get('prison_name','')} &nbsp; "
        f"<strong>Region:</strong> {meta.get('region','')} &nbsp; "
        f"<strong>Customer:</strong> {meta.get('customer_name','')} &nbsp; "
        f"<strong>Date:</strong> {meta.get('date','')}"
        "</div>"
    )
    html += f"<p>{quote_txt}</p>"

    if df_host is not None:
        html += render_table_html(df_host)

    if df_prod is not None:
        html += render_table_html(df_prod)

    if df_prod_segregated is not None and not df_prod_segregated.empty:
        html += "<h3>Production — Segregated View</h3>"
        html += render_table_html(df_prod_segregated)

    if extra_note:
        html += f"<div style='margin-top:1em'>{extra_note}</div>"

    html += "</body></html>"
    return html