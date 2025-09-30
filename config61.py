from dataclasses import dataclass
from typing import Optional  # 3.9-safe

@dataclass(frozen=True)
class AppConfig:
    FT2_TO_M2: float = 0.092903
    DAYS_PER_MONTH: float = 365.0 / 12.0
    FULL_UTILISATION_WEEK: float = 37.5
    APPORTION_FIXED_ENERGY: bool = False
    APPORTION_MAINTENANCE: bool = True
    DEFAULT_ADMIN_MONTHLY: float = 150.0
    GLOBAL_OUTPUT_DEFAULT: int = 100

CFG61 = AppConfig()

def hours_scale(hours_open_per_week: float, full_week: Optional[float] = None) -> float:
    try:
        h = float(hours_open_per_week)
        f = float(full_week if full_week is not None else CFG61.FULL_UTILISATION_WEEK)
        if f <= 0:
            return 1.0
        return max(0.0, h / f)
    except Exception:
        return 1.0