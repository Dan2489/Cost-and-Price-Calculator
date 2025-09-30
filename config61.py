# config61.py
# Central configuration file for the Cost and Price Calculator

CFG = {
    # Default VAT rate (only applied to Commercial customers when selected)
    "vat_rate": 20.0,

    # Default workshop settings
    "default_hours": 37.5,             # hours per week
    "default_prisoner_salary": 10.0,   # £ per week

    # Development charge (applies only to Commercial contracts)
    # Starts at 20%, deductions applied based on employment support options
    "development_charge": 0.20,

    # Overheads method (fixed at 61% of instructor/shadow costs)
    "overheads_rate": 0.61,
}