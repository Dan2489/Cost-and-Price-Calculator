# newapp61.py

import streamlit as st
import pandas as pd
from datetime import date
from io import StringIO

from config61 import CFG
from tariff61 import PRISON_TO_REGION, SUPERVISOR_PAY
from production61 import (
    labour_minutes_budget,
    calculate_production_contractual,
    calculate_adhoc,
    build_adhoc_table,
)
import host61


# -------------------------------
# Minimal local helpers (instead of utils61)
# -------------------------------
def inject_govuk_css():
    st.markdown("""
    <style>
      body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; }
      table { border-collapse: collapse; width: 100%; }
      th, td { border:1px solid #ddd; padding:6px; font-size:14px; }
      th { background:#f5f5f5; text-align:left; }
      .muted { color:#555; }
    </style>
    """, unsafe_allow_html=True)

def sidebar_controls(default_output_pct:int):
    with st.sidebar:
        prisoner_output = st.slider("Prisoner labour output (%)", 0, 100, default_output_pct, 1)
    return False, 0.0, prisoner_output

def fmt_currency(x):
    try: return f"£{float(x):,.2f}"
    except: return x

def render_table_html(df):
    df2 = df.copy()
    for c in df2.columns:
        if "£" in c or "Amount" in c:
            df2[c] = df2[c].apply(lambda v: fmt_currency(v) if isinstance(v, (int, float, float)) else v)
    return df2.to_html(index=False, escape=False)

def export_csv_bytes_rows(rows:list[dict]) -> bytes:
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig")

def build_header_block(uk_date, customer_name, prison_name, region):
    return f"""
    <div class='muted'>
      <b>Date:</b> {uk_date}<br>
      <b>Customer:</b> {customer_name}<br>
      <b>Prison:</b> {prison_name} ({region})
    </div>
    """

def export_html(df, main_df, title, header_block, segregated_df):
    parts = [f"<html><head><title>{title}</title></head><body>{header_block}<h2>{title}</h2>"]
    if df is not None and not df.empty: parts.append(df.to_html(index=False, escape=False))
    if segregated_df is not None and not segregated_df.empty:
        parts.append("<h3>Segregated Costs</h3>")
        parts.append(segregated_df.to_html(index=False, escape=False))
    parts.append("</body></html>")
    return "".join(parts).encode("utf-8")


# -------------------------------
# Page setup
# -------------------------------
st.set_page_config(page_title="Cost and Price Calculator", page_icon="💷", layout="centered")
inject_govuk_css()
st.title("Cost and Price Calculator")

# -------------------------------
# Sidebar
# -------------------------------
_lock, _pct, prisoner_output = sidebar_controls(CFG.GLOBAL_OUTPUT_DEFAULT)

# -------------------------------
# Base inputs
# -------------------------------
prisons_sorted = ["Select"] + sorted(PRISON_TO_REGION.keys())
prison_choice = st.selectbox("Prison Name", prisons_sorted)
region = PRISON_TO_REGION.get(prison_choice, "Select") if prison_choice != "Select" else "Select"
st.session_state["region"] = region

customer_name = st.text_input("Customer Name")
contract_type = st.selectbox("Contract Type", ["Select", "Host", "Production"])

workshop_hours = st.number_input("How many hours is the workshop open per week?", min_value=0.0, format="%.2f")
num_prisoners = st.number_input("How many prisoners employed per week?", min_value=0, step=1)
prisoner_salary = st.number_input("Average prisoner salary per week (£)", min_value=0.0, format="%.2f")

num_supervisors = st.number_input("How many instructors are required at full contract capacity.", min_value=1, step=1)
customer_covers_supervisors = st.checkbox("Customer provides Instructor(s)?", value=False)

supervisor_salaries=[]
if num_supervisors>0 and region!="Select" and not customer_covers_supervisors:
    titles = SUPERVISOR_PAY.get(region, [])
    for i in range(int(num_supervisors)):
        opts=[t["title"] for t in titles]
        sel=st.selectbox(f"Instructor {i+1} Title", opts, key=f"inst_title_{i}")
        pay=next(t["avg_total"] for t in titles if t["title"]==sel)
        st.caption(f"{region} — £{pay:,.0f}")
        supervisor_salaries.append(float(pay))

contracts = st.number_input("How many contracts do they oversee in this workshop?", min_value=1, value=1)

employment_support = st.selectbox("What employment support does the customer offer?",
                                  ["None", "Employment on release/RoTL", "Post release", "Both"])

benefits_yes = st.checkbox("Any additional prison benefits that you feel warrant a further reduction?")
benefits_text = ""
if benefits_yes:
    benefits_text = st.text_area("Describe the benefits")
instructor_benefits_discount = 0.10 if benefits_yes else 0.0


# -------------------------------
# Validation
# -------------------------------
def validate_inputs():
    errs=[]
    if prison_choice=="Select": errs.append("Select prison")
    if region=="Select": errs.append("Region not found")
    if not customer_name.strip(): errs.append("Enter customer name")
    if contract_type=="Select": errs.append("Select contract type")
    if workshop_hours<=0: errs.append("Workshop hours > 0")
    if num_prisoners<0: errs.append("Prisoners cannot be negative")
    if not customer_covers_supervisors and len(supervisor_salaries)!=num_supervisors:
        errs.append("Choose instructor titles")
    return errs


# -------------------------------
# Small helpers
# -------------------------------
def _grab_amount(df, label):
    try:
        m=df["Item"].astype(str).str.contains(label, case=False, regex=False, na=False)
        if m.any():
            raw=str(df.loc[m, "Amount (£)"].iloc[-1]).replace("£","").replace(",","")
            return float(raw)
    except: return 0.0
    return 0.0

def _uk_date(d:date): return d.strftime("%d/%m/%Y")

def _dev_rate_from_support(s:str)->float:
    if s=="None": return 0.20
    if s in ("Employment on release/RoTL","Post release"): return 0.10
    return 0.00

# -------------------------------
# Deterministic Host summary builder
# -------------------------------
def _build_host_summary_display(df):
    wages=_grab_amount(df,"Prisoner Wages")
    inst=_grab_amount(df,"Instructor Salary")
    dev_charge=_grab_amount(df,"Development charge (before") or _grab_amount(df,"Development Charge")
    dev_disc=_grab_amount(df,"Development charge reduction")
    addl_disc=_grab_amount(df,"Additional benefits reduction")
    overheads=_grab_amount(df,"Overheads (61%)") or _grab_amount(df,"Overheads")
    subtotal=_grab_amount(df,"Subtotal")
    vat=_grab_amount(df,"VAT")
    gt=_grab_amount(df,"Grand Total")

    has_any_dev=(dev_charge!=0 or dev_disc!=0)
    dev_revised=dev_charge - dev_disc if has_any_dev else 0

    if subtotal==0: subtotal=wages+inst+overheads+dev_charge+dev_disc+addl_disc
    if vat==0: vat=max(0,subtotal*0.20)
    if gt==0: gt=subtotal+vat

    rows=[
        ("Prisoner Wages", wages, False),
        ("Instructor Salary", inst, False),
        ("Development Charge", dev_charge, False),
        ("Development discount", dev_disc, True),
        ("Revised Development Charge", dev_revised, False),
        ("Additional benefits reduction", addl_disc, True),
        ("Overheads", overheads, False),
        ("Grand Total (ex VAT)", subtotal, False),
        ("Grand Total (inc VAT)", gt, False),
    ]
    rows=[(n,v,r) for (n,v,r) in rows if v and abs(v)>1e-9]

    disp=pd.DataFrame([{"Item":n,"Amount (£)":v} for (n,v,r) in rows])
    if not disp.empty:
        disp["Item"]=[f"<span style='color:#c00'>{n}</span>" if r else n for (n,_,r) in rows]
    return disp


# -------------------------------
# HOST SECTION
# -------------------------------
if contract_type=="Host":
    if st.button("Generate Host Costs"):
        errs=validate_inputs()
        if errs:
            st.error("Fix errors:\n- "+"\n- ".join(errs))
        else:
            try:
                effective_instructor_pct=min(100.0,(workshop_hours/37.5)*(1/contracts)*100.0)
            except: effective_instructor_pct=0
            host_df,_=host61.generate_host_quote(
                workshop_hours=workshop_hours,
                num_prisoners=num_prisoners,
                prisoner_salary=prisoner_salary,
                num_supervisors=num_supervisors,
                customer_covers_supervisors=customer_covers_supervisors,
                supervisor_salaries=supervisor_salaries,
                region=region,
                contracts=contracts,
                employment_support=employment_support,
                instructor_allocation=effective_instructor_pct,
                lock_overheads=False,
            )
            # apply 10% instructor discount if benefits checked
            if not customer_covers_supervisors and instructor_benefits_discount>0:
                inst_mask=host_df["Item"].astype(str).str.contains("Instructor Salary",case=False,regex=False,na=False)
                if inst_mask.any():
                    i=inst_mask[inst_mask].index[-1]
                    host_df.loc[i,"Amount (£)"]=float(host_df.loc[i,"Amount (£)"])*0.9
                    new_row=pd.DataFrame([{"Item":"Additional benefits reduction","Amount (£)":-abs(float(host_df.loc[i,"Amount (£)"])*0.1111)}])
                    host_df=pd.concat([host_df,new_row],ignore_index=True)
            st.session_state["host_df"]=host_df

    if "host_df" in st.session_state:
        src=st.session_state["host_df"].copy()
        disp=_build_host_summary_display(src)
        st.markdown(render_table_html(disp), unsafe_allow_html=True)

        header=build_header_block(_uk_date(date.today()),customer_name,prison_choice,region)
        common={
            "Quote Type":"Host","Date":_uk_date(date.today()),"Prison Name":prison_choice,
            "Region":region,"Customer Name":customer_name,"Contract Type":"Host",
            "Workshop Hours / week":workshop_hours,"Prisoners Employed":num_prisoners,
            "Prisoner Salary / week":prisoner_salary,"Instructors Count":num_supervisors,
            "Customer Provides Instructors":"Yes" if customer_covers_supervisors else "No",
            "Instructor Allocation (%)":min(100.0,(workshop_hours/37.5)*(1/contracts)*100.0) if workshop_hours>0 else 0,
            "Employment Support":employment_support,
            "Additional Benefits?":"Yes" if benefits_yes else "No",
            "Additional Benefits Notes":benefits_text or "",
            "Contracts Overseen":contracts,"VAT Rate (%)":20.0
        }

        def _pull(name):
            m=disp["Item"].astype(str).str.contains(name,case=False,regex=False,na=False)
            if not m.any(): return 0
            try: return float(str(disp.loc[m,"Amount (£)"].iloc[-1]).replace("£","").replace(",",""))
            except: return 0

        amounts={
            "Host: Prisoner wages (£/month)":_pull("Prisoner Wages"),
            "Host: Instructor Salary (£/month)":_pull("Instructor Salary"),
            "Host: Development charge (£/month)":_pull("Development Charge"),
            "Host: Development Reduction (£/month)":_pull("Development discount"),
            "Host: Development Revised (£/month)":_pull("Revised Development Charge"),
            "Host: Additional benefits reduction (£/month)":_pull("Additional benefits reduction"),
            "Host: Overheads (£/month)":_pull("Overheads"),
            "Host: Grand Total (ex VAT) (£/month)":_pull("Grand Total (ex VAT)"),
            "Host: Grand Total (inc VAT) (£/month)":_pull("Grand Total (inc VAT)")
        }

        host_csv=export_csv_bytes_rows([{**common,**amounts}])
        c1,c2=st.columns(2)
        with c1: st.download_button("Download CSV (Host)",data=host_csv,file_name="host_quote.csv",mime="text/csv")
        with c2: st.download_button("Download PDF-ready HTML (Host)",
                                   data=export_html(disp,None,"Host Quote",header,None),
                                   file_name="host_quote.html",mime="text/html")


# -------------------------------
# PRODUCTION (unchanged core)
# -------------------------------
if contract_type=="Production":
    st.markdown("---")
    st.subheader("Production settings")

    output_scale=float(prisoner_output)/100.0
    budget_raw=labour_minutes_budget(int(num_prisoners),float(workshop_hours))
    budget_planned=budget_raw*output_scale
    st.info(f"Available Labour minutes per week @ {prisoner_output}% = **{budget_planned:,.0f} minutes**.")
if contract_type == "Production":
    st.markdown("---")
    st.subheader("Production settings")
    ...