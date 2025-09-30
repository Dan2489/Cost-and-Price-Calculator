import streamlit as st

# -------------------------------------------------------------------
# Prison → Region mapping (NO 'HMP' prefixes)
# -------------------------------------------------------------------
PRISON_TO_REGION = {
    "Altcourse": "National", "Ashfield": "National", "Askham Grange": "National",
    "Aylesbury": "National", "Bedford": "National", "Belmarsh": "Inner London",
    "Berwyn": "National", "Birmingham": "National", "Brinsford": "National",
    "Bristol": "National", "Brixton": "Inner London", "Bronzefield": "Outer London",
    "Buckley Hall": "National", "Bullingdon": "National", "Bure": "National",
    "Cardiff": "National", "Channings Wood": "National", "Chelmsford": "National",
    "Coldingley": "Outer London", "Cookham Wood": "National", "Dartmoor": "National",
    "Deerbolt": "National", "Doncaster": "National", "Dovegate": "National",
    "Downview": "Outer London", "Drake Hall": "National", "Durham": "National",
    "East Sutton Park": "National", "Eastwood Park": "National", "Elmley": "National",
    "Erlestoke": "National", "Exeter": "National", "Featherstone": "National",
    "Feltham A": "Outer London", "Feltham B": "Outer London", "Five Wells": "National",
    "Ford": "National", "Forest Bank": "National", "Fosse Way": "National",
    "Foston Hall": "National", "Frankland": "National", "Full Sutton": "National",
    "Garth": "National", "Gartree": "National", "Grendon": "National",
    "Guys Marsh": "National", "Hatfield": "National", "Haverigg": "National",
    "Hewell": "National", "High Down": "Outer London", "Highpoint": "National",
    "Hindley": "National", "Hollesley Bay": "National", "Holme House": "National",
    "Hull": "National", "Humber": "National", "Huntercombe": "National",
    "Isis": "Inner London", "Isle of Wight": "National", "Kirkham": "National",
    "Kirklevington Grange": "National", "Lancaster Farms": "National",
    "Leeds": "National", "Leicester": "National", "Lewes": "National",
    "Leyhill": "National", "Lincoln": "National", "Lindholme": "National",
    "Littlehey": "National", "Liverpool": "National", "Long Lartin": "National",
    "Low Newton": "National", "Lowdham Grange": "National", "Maidstone": "National",
    "Manchester": "National", "Moorland": "National", "Morton Hall": "National",
    "The Mount": "National", "New Hall": "National", "North Sea Camp": "National",
    "Northumberland": "National", "Norwich": "National", "Nottingham": "National",
    "Oakwood": "National", "Onley": "National", "Parc": "National", "Parc (YOI)": "National",
    "Pentonville": "Inner London", "Peterborough Female": "National",
    "Peterborough Male": "National", "Portland": "National", "Prescoed": "National",
    "Preston": "National", "Ranby": "National", "Risley": "National", "Rochester": "National",
    "Rye Hill": "National", "Send": "National", "Spring Hill": "National",
    "Stafford": "National", "Standford Hill": "National", "Stocken": "National",
    "Stoke Heath": "National", "Styal": "National", "Sudbury": "National",
    "Swaleside": "National", "Swansea": "National", "Swinfen Hall": "National",
    "Thameside": "Inner London", "Thorn Cross": "National", "Usk": "National",
    "Verne": "National", "Wakefield": "National", "Wandsworth": "Inner London",
    "Warren Hill": "National", "Wayland": "National", "Wealstun": "National",
    "Werrington": "National", "Wetherby": "National", "Whatton": "National",
    "Whitemoor": "National", "Winchester": "National", "Woodhill": "Inner London",
    "Wormwood Scrubs": "Inner London", "Wymott": "National",
}

# -------------------------------------------------------------------
# Instructor pay bands — ONLY Band 3 & Band 4 titles
# -------------------------------------------------------------------
SUPERVISOR_PAY = {
    "Inner London": [
        {"title": "Production Instructor: Band 3", "avg_total": 49203},
        {"title": "Specialist Instructor: Band 4", "avg_total": 55632},
    ],
    "Outer London": [
        {"title": "Production Instructor: Band 3", "avg_total": 45856},
        {"title": "Specialist Instructor: Band 4", "avg_total": 69584},
    ],
    "National": [
        {"title": "Production Instructor: Band 3", "avg_total": 42248},
        {"title": "Specialist Instructor: Band 4", "avg_total": 48969},
    ],
}

# Band 3 SHADOW salaries for customer-provided instructors (no salary shown/used, only overhead 61%)
BAND3_SHADOW = {
    "Outer London": 45855.97,
    "Inner London": 49202.70,
    "National": 42247.81,
}

# -------------------------------------------------------------------
# Styling
# -------------------------------------------------------------------
def inject_govuk_css() -> None:
    st.markdown(
        """
        <style>
          [data-testid="stSidebar"]{min-width:420px!important;max-width:420px!important}
          @media (max-width:1200px){
            [data-testid="stSidebar"]{min-width:360px!important;max-width:360px!important}
          }
          :root{--govuk-green:#00703c;--govuk-yellow:#ffdd00}
          .stButton>button{background:var(--govuk-green)!important;color:#fff!important;border:2px solid transparent!important;border-radius:0!important;font-weight:600}
          .stButton>button:hover{filter:brightness(0.95)}
          .stButton>button:focus,.stButton>button:focus-visible{outline:3px solid var(--govuk-yellow)!important;outline-offset:0!important;box-shadow:0 0 0 1px #000 inset!important}
          [data-testid="stSlider"] [role="slider"]{background:var(--govuk-green)!important;border:2px solid var(--govuk-green)!important;box-shadow:none!important}
          [data-testid="stSlider"] [role="slider"]:focus,[data-testid="stSlider"] [role="slider"]:focus-visible{outline:3px solid var(--govuk-yellow)!important;outline-offset:0!important;box-shadow:0 0 0 1px #000 inset!important}
          [data-testid="stSlider"] div[aria-hidden="true"]>div>div{background-color:var(--govuk-green)!important}
          .govuk-heading-l{font-weight:700;font-size:1.75rem;line-height:1.2}
          .app-header{display:flex;align-items:center;gap:12px;margin:.25rem 0 .75rem 0}
          table{width:100%;border-collapse:collapse;margin:12px 0}
          th,td{border-bottom:1px solid #b1b4b6;padding:8px;text-align:left}
          th{background:#f3f2f1} td.neg{color:#d4351c} tr.grand td{font-weight:700}
          /* bordered container (so we can avoid st.form blocking dynamic widgets) */
          .boxed{border:1px solid #b1b4b6;border-radius:6px;padding:16px;background:#fff}
        </style>
        """,
        unsafe_allow_html=True
    )