# tariff61.py
# Instructor pay bands and Band 3 shadow costs (no utilities/energy tariffs)

# Prison → Region lookup
PRISON_TO_REGION = {
    "HMP Brixton": "Inner London",
    "HMP Pentonville": "Inner London",
    "HMP Wandsworth": "Outer London",
    "HMP Manchester": "National",
    "HMP Liverpool": "National",
    # ... extend as required
}

# Instructor salary bands per region (simplified example, add all as needed)
SUPERVISOR_PAY = {
    "Outer London": [
        {"title": "Production Instructor Band 1", "avg_total": 30000.00},
        {"title": "Production Instructor Band 2", "avg_total": 38000.00},
        {"title": "Production Instructor Band 3", "avg_total": 45855.97}, # key value
        {"title": "Production Instructor Band 4", "avg_total": 52000.00},
    ],
    "Inner London": [
        {"title": "Production Instructor Band 1", "avg_total": 32000.00},
        {"title": "Production Instructor Band 2", "avg_total": 40000.00},
        {"title": "Production Instructor Band 3", "avg_total": 49202.70}, # key value
        {"title": "Production Instructor Band 4", "avg_total": 54000.00},
    ],
    "National": [
        {"title": "Production Instructor Band 1", "avg_total": 28000.00},
        {"title": "Production Instructor Band 2", "avg_total": 35000.00},
        {"title": "Production Instructor Band 3", "avg_total": 42247.81}, # key value
        {"title": "Production Instructor Band 4", "avg_total": 49000.00},
    ],
}

# Band 3 "shadow costs" (for when customer provides instructors)
# Salaries are removed; overheads only (61% applied later).
BAND3_SHADOW = {
    "Outer London": 45855.97,
    "Inner London": 49202.70,
    "National": 42247.81,
}

# Convenience: average monthly and weekly equivalents (for shadow costing)
BAND3_SHADOW["monthly"] = sum(BAND3_SHADOW.values()) / len(BAND3_SHADOW) / 12.0
BAND3_SHADOW["weekly"] = sum(BAND3_SHADOW.values()) / len(BAND3_SHADOW) / 52.0
