# config61.py
from dataclasses import dataclass

@dataclass(frozen=True)
class AppConfig:
    days_per_month: float = 365.0 / 12.0   # ~30.42
    full_utilisation_week: float = 37.5    # reference week
    default_admin_monthly: float = 150.0   # unused, kept for compatibility
    global_output_default: int = 100       # default slider value (%)

CFG = AppConfig()