from dataclasses import dataclass
from typing import Optional  # 3.9-safe alternative to float | None

@dataclass(frozen=True)
class AppConfig:
    FULL_UTILISATION_WEEK: float = 37.5   # reference week for hours scaling
    GLOBAL_OUTPUT_DEFAULT: int = 100      # % slider default

CFG = AppConfig()

def hours_scale(hours_open_per_week: float, full_week: Optional[float] = None) -> float:
    """
    Scale factor for hours relative to a reference 'full utilisation week'.
    """
    try:
        h = float(hours_open_per_week)
        f = float(full_week if full_week is not None else CFG.FULL_UTILISATION_WEEK)
        if f <= 0:
            return 1.0
        return max(0.0, h / f)
    except Exception:
        return 1.0