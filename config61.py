# config61.py
from dataclasses import dataclass

@dataclass(frozen=True)
class AppConfig:
    # General constants
    FT2_TO_M2: float = 0.092903
    DAYS_PER_MONTH: float = 365.0 / 12.0   # ≈30.42 days/month
    FULL_UTILISATION_WEEK: float = 37.5    # reference week for scaling

    # Admin/legacy switches (kept for compatibility, though not used with 61% model)
    APPORTION_FIXED_ENERGY: bool = False
    APPORTION_MAINTENANCE: bool = True

    # Default monthly admin cost (legacy, not used with 61% model)
    DEFAULT_ADMIN_MONTHLY: float = 150.0

    # NEW: prisoner output default (%)
    GLOBAL_OUTPUT_DEFAULT: int = 100

    # VAT default
    vat_rate: float = 20.0


# Create a global config instance
CFG = AppConfig()# config61.py
from dataclasses import dataclass

@dataclass(frozen=True)
class AppConfig61:
    # Default prisoner labour output (%) for Production when the user doesn’t touch the slider
    global_output_default: int = 100

CFG = AppConfig61()