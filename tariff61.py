# tariff61.py
# Prison -> Region mapping and Instructor salaries

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

# Band 3 salaries (for shadow costs if customer provides instructor)
BAND3_COSTS = {
    "Outer London": 45855.97,
    "Inner London": 49202.70,
    "National": 42247.81,
}

# Supervisor pay bands
SUPERVISOR_PAY = {
    "Inner London": [
        {"title": "Production Instructor: Band 3", "avg_total": 49203},
        {"title": "Specialist Instructor: Band 4", "avg_total": 55632},
    ],
    "Outer London": [
        {"title": "Production Instructor: Band 3", "avg_total": 45856},
        {"title": "Prison Officer Specialist - Instructor: Band 4", "avg_total": 69584},
    ],
    "National": [
        {"title": "Production Instructor: Band 3", "avg_total": 42248},
        {"title": "Prison Officer Specialist - Instructor: Band 4", "avg_total": 48969},
    ],
}