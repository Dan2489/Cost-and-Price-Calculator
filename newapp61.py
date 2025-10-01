# newapp61.py
# Main app shell. Business logic remains in host61.py / production61.py.
from __future__ import annotations

import streamlit as st
import pandas as pd
from datetime import date

from config61 import CFG                     # dataclass with global_output_default, etc.
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
import host61
import production61

# Utils (names MUST match)
from utils61 import (
    inject_govuk_css,
    fmt_currency,
    sidebar_controls,
    adjust_table,
    render_table_html,
    build_html_page,
)

# ──────────────────────────────────────────────────────────────────────────────
# App
# ──────────────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Cost and Price Calculator", layout="centered")
inject_govuk_css()

def header():
    st.markdown('<div class="govuk-heading-l">Cost and Price Calculator</div>', unsafe_allow_html=True)

def main():
    header()

    # Sidebar controls (exactly as before)
    lock_overheads, instructor_pct, prisoner_output = sidebar_controls(CFG.global_output_default)

    # ── Main form (identical questions you’ve been using) ─────────────────────
    prisons = list(PRISON_TO_REGION.keys())
    prison = st.selectbox("Prison Name", prisons, index=0)
    customer = st.text_input("Customer Name", value="")
    contract_type = st.selectbox("Contract Type", ["Host", "Production"], index=0)

    workshop_hours = st.number_input("How many hours is the workshop open per week?", min_value=0.0, step=0.25, value=0.0, format="%.2f")
    num_prisoners  = st.number_input("How many prisoners employed per week?", min_value=0, step=1, value=0)
    prisoner_salary= st.number_input("Average prisoner salary per week (£)", min_value=0.0, step=0.25, value=0.0)
    num_instructors= st.number_input("How many instructors?", min_value=0, step=1, value=0)

    # Dynamic instructor titles (same behaviour: appears as soon as you set count)
    region = PRISON_TO_REGION.get(prison, "National")
    titles = [entry["title"] for entry in SUPERVISOR_PAY.get(region, [])]
    salaries = [entry["avg_total"] for entry in SUPERVISOR_PAY.get(region, [])]

    chosen_titles, chosen_salaries = [], []
    if num_instructors > 0:
        st.caption(f"Region: **{region}**")
        for i in range(num_instructors):
            sel = st.selectbox(f"Instructor {i+1} Title", titles, key=f"inst_title_{i}")
            idx = titles.index(sel)
            chosen_titles.append(sel)
            chosen_salaries.append(salaries[idx])
            st.caption(f"{region} — {fmt_currency(salaries[idx])}")

    contracts_overseen = st.number_input("How many contracts do they oversee in this workshop?", min_value=1, step=1, value=1)

    employment_support = st.selectbox(
        "What employment support does the customer offer?",
        ["None", "Employment on release/RoTL", "Post-release support", "Both"],
        index=0,
    )

    # action button label depends on contract type (Host vs Production)
    btn_label = "Generate Host Costs" if contract_type == "Host" else "Generate Production Costs"
    go = st.button(btn_label)

    if not go:
        return

    # ── HOST PATH ─────────────────────────────────────────────────────────────
    if contract_type == "Host":
        df, ctx = host61.generate_host_quote(
            workshop_hours=workshop_hours,
            area_m2=0.0,                         # (unused in 61% logic, kept for compatibility)
            usage_key="low",                     # (unused)
            num_prisoners=num_prisoners,
            prisoner_salary=prisoner_salary,
            num_supervisors=num_instructors,
            customer_covers_supervisors=False,   # checkbox removed per your rules; using salary list below
            supervisor_salaries=chosen_salaries,
            effective_pct=float(instructor_pct),
            customer_type="Commercial",          # dev charge applies unless Other Government Dept
            apply_vat=True,
            vat_rate=20.0,
            dev_rate=0.20,                       # will be reduced based on employment_support in host61
            employment_support=employment_support,
            contracts_overseen=int(contracts_overseen),
            lock_overheads=bool(st.session_state.get("lock_overheads", False)),
            region=region,
        )

        # show main table
        st.markdown(render_table_html(df), unsafe_allow_html=True)

        # Productivity slider (post-table)
        st.write("")
        prod = st.slider("Adjust for Productivity (%)", 50, 100, 100, help="Applies a % factor to the table above for review only.")
        factor = prod / 100.0

        st.subheader("Adjusted Costs (for review only)")
        df_adj = adjust_table(df, factor)
        st.markdown(render_table_html(df_adj, highlight=True), unsafe_allow_html=True)

        # Download: single HTML with both tables + UTF-8 meta (fixes £)
        body = f"""
        <h1>Host Quote</h1>
        {render_table_html(df)}
        <h2>Adjusted Costs (for review only)</h2>
        {render_table_html(df_adj, highlight=True)}
        <p class="caption">Productivity assumptions have been applied. These will be reviewed annually with Commercial.</p>
        """
        html = build_html_page("Host Quote", body)
        st.download_button("Download PDF-ready HTML (Host)", data=html, file_name="host_quote.html", mime="text/html")

        return

    # ── PRODUCTION PATH ───────────────────────────────────────────────────────
    # (Inputs for production items were unchanged in your working version;
    #  using your existing functions from production61)
    pricing_mode = st.selectbox("Production mode", ["Contractual", "Ad-hoc"], index=0)

    if pricing_mode == "Contractual":
        # Collect one or more items (your app already does this in prior working code)
        # Here we assume you’re using the prior items list from session_state:
        items: list[dict] = st.session_state.get("prod_items", [])
        if not items:
            st.warning("Enter production items in the section above, then click Generate Production Costs.")
            return

        results = production61.calculate_production_contractual(
            items=items,
            output_pct=int(prisoner_output),
            workshop_hours=workshop_hours,
            prisoner_salary=prisoner_salary,
            supervisor_salaries=chosen_salaries,
            effective_pct=float(instructor_pct),
            customer_covers_supervisors=False,
            region=region,
            customer_type="Commercial",
            apply_vat=True,
            vat_rate=20.0,
            num_prisoners=num_prisoners,
            num_supervisors=num_instructors,
            dev_rate=production61.dev_rate_from_support(employment_support),
            pricing_mode="as-is",
            targets=None,
            lock_overheads=bool(st.session_state.get("lock_overheads", False)),
        )

        df = pd.DataFrame(results)
        # Hide "Feasible" and "Note" for Contractual as requested
        for col in ("Feasible", "Note"):
            if col in df.columns:
                df.drop(columns=[col], inplace=True)

        st.markdown(render_table_html(df), unsafe_allow_html=True)

        # Productivity slider on the contractual table
        st.write("")
        prod = st.slider("Adjust for Productivity (%)", 50, 100, 100)
        factor = prod / 100.0
        st.subheader("Adjusted Costs (for review only)")
        df_adj = adjust_table(df, factor)
        st.markdown(render_table_html(df_adj, highlight=True), unsafe_allow_html=True)

        body = f"""
        <h1>Production – Contractual Quote</h1>
        <p class="caption">Date: {date.today().strftime('%d/%m/%Y')}<br>
        Customer: {customer}<br>
        Prison: {prison}<br>
        Region: {region}</p>
        {render_table_html(df)}
        <h2>Adjusted Costs (for review only)</h2>
        {render_table_html(df_adj, highlight=True)}
        <p class="caption">Productivity assumptions have been applied. These will be reviewed annually with Commercial.</p>
        """
        html = build_html_page("Production – Contractual Quote", body)
        st.download_button("Download PDF-ready HTML (Production – Contractual)", data=html,
                           file_name="production_contractual.html", mime="text/html")
        return

    else:
        # Ad-hoc (unchanged core logic; your production61 handles all calculations)
        # Collect ad-hoc lines from session (as per your working version)
        adhoc_lines: list[dict] = st.session_state.get("adhoc_lines", [])
        if not adhoc_lines:
            st.warning("Enter ad-hoc lines in the section above, then click Generate Production Costs.")
            return

        out = production61.calculate_adhoc(
            lines=adhoc_lines,
            output_pct=int(prisoner_output),
            workshop_hours=workshop_hours,
            num_prisoners=num_prisoners,
            prisoner_salary=prisoner_salary,
            supervisor_salaries=chosen_salaries,
            effective_pct=float(instructor_pct),
            customer_covers_supervisors=False,
            customer_type="Commercial",
            apply_vat=True,
            vat_rate=20.0,
            area_m2=0.0,
            usage_key="low",
            dev_rate=production61.dev_rate_from_support(employment_support),
            today=date.today(),
        )

        per_line = pd.DataFrame(out["per_line"])
        # Titles (UK date) + table rendering
        st.markdown(render_table_html(per_line), unsafe_allow_html=True)

        # Slider and adjusted copy
        st.write("")
        prod = st.slider("Adjust for Productivity (%)", 50, 100, 100)
        factor = prod / 100.0
        st.subheader("Adjusted Costs (for review only)")
        per_line_adj = adjust_table(per_line, factor)
        st.markdown(render_table_html(per_line_adj, highlight=True), unsafe_allow_html=True)

        body = f"""
        <h1>Production – Ad-hoc Quote</h1>
        <p class="caption">Date: {date.today().strftime('%d/%m/%Y')}<br>
        Customer: {customer}<br>
        Prison: {prison}<br>
        Region: {region}</p>
        {render_table_html(per_line)}
        <h2>Adjusted Costs (for review only)</h2>
        {render_table_html(per_line_adj, highlight=True)}
        <p class="caption">Productivity assumptions have been applied. These will be reviewed annually with Commercial.</p>
        """
        html = build_html_page("Production – Ad-hoc Quote", body)
        st.download_button("Download PDF-ready HTML (Production – Ad-hoc)", data=html,
                           file_name="production_adhoc.html", mime="text/html")
        return


if __name__ == "__main__":
    main()