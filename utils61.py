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
          /* Sidebar */
          [data-testid="stSidebar"] {
            min-width: 320px !important;
            max-width: 320px !important;
          }

          /* GOV.UK colours */
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
          .stButton > button:focus, .stButton > button:focus-visible {
            outline: 3px solid var(--govuk-yellow) !important;
            outline-offset: 0 !important;
            box-shadow: 0 0 0 1px #000 inset !important;
          }

          /* Tables */
          table.custom { 
            width: 100%; 
            border-collapse: collapse; 
            margin: 12px 0; 
          }
          table.custom th, table.custom td { 
            border: 1px solid #b1b4b6; 
            padding: 6px 10px; 
            text-align: left; 
          }
          table.custom th { 
            background: #f3f2f1; 
            font-weight: bold; 
          }
          table.custom td.neg { color: #d4351c; }
          table.custom tr.grand td { font-weight: bold; }
          table.custom.highlight { background-color: #fff8dc; } /* light yellow for adjusted */
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
        return f"£{val:,.2f}"
    except Exception:
        return str(val)

# -------------------------------
# Export functions
# -------------------------------
def export_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

def export_html(df_host: pd.DataFrame, df_prod: pd.DataFrame,
                title: str, extra_note: str = None, adjusted_df: pd.DataFrame = None) -> str:
    """Export to standalone HTML for PDF generation."""
    styles = """
    <style>
        body { font-family: Arial, sans-serif; }
        h1, h2, h3 { margin-top: 1em; }
        table.custom { 
            width: 100%; 
            border-collapse: collapse; 
            margin: 12px 0; 
        }
        table.custom th, table.custom td { 
            border: 1px solid #b1b4b6; 
            padding: 6px 10px; 
            text-align: left; 
        }
        table.custom th { 
            background: #f3f2f1; 
            font-weight: bold; 
        }
        table.custom.highlight { background-color: #fff8dc; }
    </style>
    """
    html = f"<html><head>{styles}</head><body>"
    html += f"<h1>{title}</h1>"

    if df_host is not None:
        html += df_host.to_html(index=False, classes="custom", border=0, justify="left")

    if df_prod is not None:
        html += df_prod.to_html(index=False, classes="custom", border=0, justify="left")

    if adjusted_df is not None:
        html += "<h3>Adjusted Costs (for review only)</h3>"
        html += adjusted_df.to_html(index=False, classes="custom highlight", border=0, justify="left")

    if extra_note:
        html += f"<div style='margin-top:1em'>{extra_note}</div>"

    html += "</body></html>"
    return html

# -------------------------------
# Table rendering
# -------------------------------
def render_table_html(df: pd.DataFrame, highlight: bool = False) -> str:
    """Render DataFrame as styled HTML table with GOV.UK styles."""
    if df is None or df.empty:
        return "<p><em>No data</em></p>"

    cls = "custom highlight" if highlight else "custom"
    return df.to_html(index=False, classes=cls, border=0, justify="left")

# -------------------------------
# Adjust table for productivity
# -------------------------------
def adjust_table(df: pd.DataFrame, factor: float) -> pd.DataFrame:
    """Return a copy of df with numeric values scaled by factor."""
    df_adj = df.copy()
    for col in df_adj.columns:
        if pd.api.types.is_numeric_dtype(df_adj[col]):
            df_adj[col] = df_adj[col].apply(lambda x: x * factor if pd.notnull(x) else x)
        else:
            # Try to strip currency signs
            def try_parse(val):
                try:
                    val_f = float(str(val).replace("£", "").replace(",", ""))
                    return f"£{val_f * factor:,.2f}"
                except Exception:
                    return val
            df_adj[col] = df_adj[col].apply(try_parse)
    return df_adj