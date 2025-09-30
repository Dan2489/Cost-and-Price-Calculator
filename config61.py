from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class AppConfig61:
    FULL_UTILISATION_WEEK: float = 37.5   # reference week
    GLOBAL_OUTPUT_DEFAULT: int = 100      # default output %

CFG61 = AppConfig61()

def hours_scale(hours_open_per_week: float, full_week: Optional[float] = None) -> float:
    """Scale factor for hours relative to full week."""
    try:
        h = float(hours_open_per_week)
        f = float(full_week if full_week is not None else CFG61.FULL_UTILISATION_WEEK)
        if f <= 0:
            return 1.0
        return max(0.0, h / f)
    except Exception:
        return 1.0