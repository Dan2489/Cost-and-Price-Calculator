import io
import csv
import html
from typing import Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st


# =========================
# Styling / CSS helpers
# =========================
def inject_govuk_css() -> None:
    """
    Injects minimal GOV.UK-like styling plus table borders for HTML exports & on-screen tables.
    """
    st.markdown(
        """
        <style>
          :root{
            --govuk-black:#0b0c0c;
            --govuk-blue:#1d70b8;
            --govuk-green:#00703c;
            --govuk-red:#d4351c;
            --soft-border:#dcdcdc;
          }
          body { font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, "Helvetica Neue", Helvetica, sans-serif; }
          h1,h2,h3 { color: var(--govuk-black); margin-bottom: .5rem; }
          .govuk-caption { color:#505a5f; font-size:.9rem; margin-bottom:1rem; }

          /* Buttons look */
          .stButton>button {
            background: var(--govuk-blue) !important;
            color: white !important;
            border: 1px solid var(--govuk-blue) !important;
            border-radius: 6px !important;
            padding: .45rem .9rem !important;
          }
          .stButton>button:hover { filter: brightness(.95); }

          /* Table styling (borders) */
          table.bordered {
            border-collapse: collapse;
            width: 100%;
            margin: .5rem 0 1.25rem 0;
            table-layout: auto;
          }
          table.bordered th, table.bordered td {
            border: 1px solid var(--soft-border);
            padding: 6px 8px;
            vertical-align: top;
            word-break: break-word;
          }
          table.bordered th {
            background: #f8f8f8;
            font-weight: 600;
            text-align: left;
          }
          .muted { color:#6a6f73; }
          .small { font-size: .92rem; }
          .red { color: var(--govuk-red); }
          .green { color: var(--govuk-green); }
          .note { background:#fff7f5; border:1px solid #f3d2cf; padding:.5rem .75rem; border-radius:6px; }
          .header-block { margin:.5rem 0 1rem 0; }
          .header-block p { margin:.25rem 0; }
          .kv { margin:.15rem 0; }
          .kv b { display:inline-block; min-width: 140px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


# =========================
# Sidebar controls
# =========================
def sidebar_controls(default_output_pct: int) -> Tuple[bool, float, int]:
    """
    Historically returned (lock_overheads, instructor_pct, prisoner_output).
    Per latest requirements, we still RETURN 3 values for compatibility,
    but only expose the prisoner labour output slider in the UI.

    Returns:
        lock_overheads: always False (deprecated)
        instructor_pct: dummy 100.0 (deprecated, ignored by app)
        prisoner_output: int 0..100 from slider
    """
    with st.sidebar:
        st.markdown("### Controls")
        prisoner_output = st.slider("Prisoner labour output (%)", 0, 100, int(default_output_pct), step=1)
    # Keep backward-compatible return shape
    return (False, 100.0, int(prisoner_output))


# =========================
# Formatting helpers
# =========================
def fmt_currency(val: Optional[float]) -> str:
    if val is None:
        return ""
    try:
        return f"£{float(val):,.2f}"
    except Exception:
        return str(val)


# =========================
# HTML table render
# =========================
def _df_to_html(df: pd.DataFrame) -> str:
    """
    Render a DataFrame as a bordered HTML table with safe escaping.
    Preserves any deliberate HTML tags (e.g., red spans) already in cell strings.
    """
    if df is None or df.empty:
        return "<p class='muted'>No data.</p>"

    # Build header
    cols = list(df.columns)
    thead = "<tr>" + "".join(f"<th>{html.escape(str(c))}</th>" for c in cols) + "</tr>"

    # Build rows
    body_rows = []
    for _, row in df.iterrows():
        tds = []
        for c in cols:
            v = row.get(c, "")
            if isinstance(v, str):
                # Allow existing HTML for red reductions etc.
                cell = v
            else:
                cell = fmt_currency(v) if isinstance(v, (int, float)) and ("£" in str(c) or "Price" in str(c)) else str(v)
            tds.append(f"<td>{cell}</td>")
        body_rows.append("<tr>" + "".join(tds) + "</tr>")
    tbody = "\n".join(body_rows)
    return f"<table class='bordered'><thead>{thead}</thead><tbody>{tbody}</tbody></table>"


def render_table_html(df: pd.DataFrame) -> str:
    return _df_to_html(df)


# =========================
# HTML export
# =========================
def build_header_block(
    uk_date: str,
    customer_name: str,
    prison_name: str,
    region: str,
    benefits_desc: Optional[str] = None,
) -> str:
    """
    Returns an HTML header block that your app injects above quote tables.
    """
    ben = ""
    if benefits_desc:
        ben = f"<p class='kv'><b>Additional Benefits:</b> {html.escape(benefits_desc)}</p>"

    return f"""
    <div class='header-block'>
      <p class='kv'><b>Date:</b> {html.escape(uk_date)}</p>
      <p class='kv'><b>Customer:</b> {html.escape(customer_name)}</p>
      <p class='kv'><b>Prison:</b> {html.escape(prison_name)}</p>
      <p class='kv'><b>Region:</b> {html.escape(region)}</p>
      {ben}
      <p class='small muted'>All prices shown are exclusive of VAT unless otherwise stated. Overheads and development
      charges are calculated per current policy. Where the customer provides instructors, only shadow overheads apply.</p>
    </div>
    """


def export_html(
    host_df: Optional[pd.DataFrame],
    prod_df: Optional[pd.DataFrame],
    title: str,
    header_block: str,
    segregated_df: Optional[pd.DataFrame] = None,
) -> bytes:
    """
    Creates a standalone HTML document (with borders) suitable for printing to PDF.
    We avoid reportlab; everything is styled via CSS.
    """
    parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        "<title>Quote</title>",
        # Inline minimal CSS (same as Streamlit injection)
        """
        <style>
          body { font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, "Helvetica Neue", Helvetica, sans-serif; margin:20px; }
          h1,h2 { margin:.2rem 0 .6rem 0; }
          .muted { color:#6a6f73; }
          table.bordered { border-collapse: collapse; width: 100%; margin: .5rem 0 1.25rem 0; table-layout: auto; }
          table.bordered th, table.bordered td { border: 1px solid #dcdcdc; padding: 6px 8px; vertical-align: top; word-break: break-word; }
          table.bordered th { background: #f8f8f8; font-weight: 600; text-align: left; }
          .red { color: #d4351c; }
          .header-block { margin:.5rem 0 1rem 0; }
          .kv { margin:.15rem 0; }
          .kv b { display:inline-block; min-width: 140px; }
        </style>
        """,
        "</head><body>",
        f"<h1>{html.escape(title)}</h1>",
        header_block or "",
    ]

    if host_df is not None:
        parts.append("<h2>Summary</h2>")
        parts.append(_df_to_html(host_df))

    if prod_df is not None:
        parts.append("<h2>Summary</h2>")
        parts.append(_df_to_html(prod_df))

    if segregated_df is not None and not segregated_df.empty:
        parts.append("<h2>Segregated Costs</h2>")
        parts.append(_df_to_html(segregated_df))

    parts.append("</body></html>")
    return "\n".join(parts).encode("utf-8")


# =========================
# CSV export helpers
# =========================
def export_csv_bytes(df: pd.DataFrame, filename_hint: str = "export.csv") -> bytes:
    """
    Simple DataFrame -> CSV bytes.
    """
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8-sig")


def export_csv_bytes_rows(rows: List[Dict]) -> bytes:
    """
    List[dict] -> CSV bytes. Column order based on first row's keys.
    """
    if not rows:
        return b""
    fieldnames = list(rows[0].keys())
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow({k: r.get(k, "") for k in fieldnames})
    return out.getvalue().encode("utf-8-sig")


def _flatten_items(prefix: str, df: Optional[pd.DataFrame], max_items: int = 40) -> Dict[str, Optional[str]]:
    """
    Flattens a pricing results table into a single row with columns like:
      Item 1 - Name, Item 1 - Output %, Item 1 - Capacity (units/week), ...
    Only columns present in df will be exported.
    """
    out: Dict[str, Optional[str]] = {}
    if df is None or df.empty:
        return out

    cols = list(df.columns)
    n = min(len(df), max_items)

    for i in range(n):
        row = df.iloc[i].to_dict()
        name = str(row.get("Item", f"Item {i+1}"))
        out[f"{prefix} {i+1} - Name"] = name

        def put(colname: str, label: str):
            if colname in cols:
                val = row.get(colname, "")
                if isinstance(val, (int, float)) and "£" in label:
                    out[label] = fmt_currency(val)
                else:
                    out[label] = "" if val is None else str(val)

        put("Output %", f"{prefix} {i+1} - Output %")
        put("Capacity (units/week)", f"{prefix} {i+1} - Capacity (units/week)")
        put("Units/week", f"{prefix} {i+1} - Units/week")
        put("Unit Cost (£)", f"{prefix} {i+1} - Unit Cost (£)")
        put("Unit Price ex VAT (£)", f"{prefix} {i+1} - Unit Price ex VAT (£)")
        put("Unit Price inc VAT (£)", f"{prefix} {i+1} - Unit Price inc VAT (£)")
        put("Monthly Total ex VAT (£)", f"{prefix} {i+1} - Monthly Total ex VAT (£)")
        put("Monthly Total inc VAT (£)", f"{prefix} {i+1} - Monthly Total inc VAT (£)")
        put("Unit Cost excl Instructor (£)", f"{prefix} {i+1} - Unit Cost excl Instructor (£)")
        put("Monthly Total excl Instructor ex VAT (£)", f"{prefix} {i+1} - Monthly Total excl Instructor ex VAT (£)")

    # Totals if present as a single-row df (e.g., production summary totals were already summed outside)
    if "Production: Total Monthly ex VAT (£)" in cols:
        out["Production: Total Monthly ex VAT (£)"] = fmt_currency(
            _coerce_float(df["Production: Total Monthly ex VAT (£)"].iloc[0])
        )
    if "Production: Total Monthly inc VAT (£)" in cols:
        out["Production: Total Monthly inc VAT (£)"] = fmt_currency(
            _coerce_float(df["Production: Total Monthly inc VAT (£)"].iloc[0])
        )

    return out


def export_csv_single_row(common: Dict, main_df: Optional[pd.DataFrame], seg_df: Optional[pd.DataFrame]) -> bytes:
    """
    Flattens main_df and seg_df into columns and prepends 'common' fields.
    """
    flat_main = _flatten_items("Item", main_df)
    flat_seg = _flatten_items("Seg Item", seg_df)
    row = {**common, **flat_main, **flat_seg}
    return export_csv_bytes_rows([row])


def _coerce_float(x):
    try:
        return float(str(x).replace("£", "").replace(",", "").strip())
    except Exception:
        return None


# =========================
# Table post-processing hook
# =========================
def adjust_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Hook for any display adjustments if needed later.
    Currently returns df unchanged.
    """
    return df