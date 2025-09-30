from dataclasses import dataclass
from typing import Optional  # 3.9-safe

@dataclass(frozen=True)
class AppConfig:
    DAYS_PER_MONTH: float = 365.0 / 12.0   # ≈30.42
    FULL_UTILISATION_WEEK: float = 37.5    # for % allocation guidance
    GLOBAL_OUTPUT_DEFAULT: int = 100       # default output %
    OVERHEAD_PCT: float = 0.61             # fixed overhead multiplier

CFG = AppConfig()

def hours_scale(hours_open_per_week: float, full_week: Optional[float] = None) -> float:
    try:
        h = float(hours_open_per_week)
        f = float(full_week if full_week is not None else CFG.FULL_UTILISATION_WEEK)
        if f <= 0:
            return 1.0
        return max(0.0, h / f)
    except Exception:
        return 1.0