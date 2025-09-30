# config61.py
# Central configuration file for the Cost and Price Calculator

class AppConfig:
    def __init__(self):
        # Default VAT rate
        self.vat_rate = 20.0

        # Development charge (Commercial contracts only)
        # Starts at 20%, deductions applied based on employment support
        self.development_charge = 0.20

        # Default output for prisoner labour (%)
        self.GLOBAL_OUTPUT_DEFAULT = 100

        # Overheads method (fixed at 61% of instructor/shadow costs)
        self.overheads_rate = 0.61


CFG = AppConfig()