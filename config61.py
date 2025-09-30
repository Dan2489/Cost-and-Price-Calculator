# config61.py
# Central configuration file for the Cost and Price Calculator

CFG = {
    # Default VAT rate (always 20%)
    "vat_rate": 20.0,

    # Development charge (Commercial contracts only)
    # Starts at 20%, deductions applied based on employment support
    "development_charge": 0.20,

    # Default output for prisoner labour (%)
    "GLOBAL_OUTPUT_DEFAULT": 100,

    # Overheads method (fixed at 61% of instructor/shadow costs)
    "overheads_rate": 0.61,
}