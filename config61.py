from dataclasses import dataclass
from typing import Optional  # 3.9-safe alternative to float | None

@dataclass(frozen=True)
class AppConfig:
    DAYS_PER_MONTH: float = 365.0 / 12.0  # ≈30.42
    FULL_UTILISATION_WEEK: float = 37.5   # reference week for scaling
    DEFAULT_ADMIN_MONTHLY: float = 150.0
    GLOBAL_OUTPUT_DEFAULT: int = 100
    OVERHEAD_PCT: float = 0.61  # fixed 61% overhead model

CFG = AppConfig()

def hours_scale(hours_open_per_week: float, full_week: Optional[float] = None) -> float:
    """
    Scale factor based on hours open compared to a full utilisation week.
    """
    try:
        h = float(hours_open_per_week)
        f = float(full_week if full_week is not None else CFG.FULL_UTILISATION_WEEK)
        if f <= 0:
            return 1.0
        return max(0.0, h / f)
    except Exception:
        return 1.0