# config61.py
from dataclasses import dataclass

@dataclass(frozen=True)
class AppConfig61:
    FULL_UTILISATION_WEEK: float = 37.5   # reference week for scaling
    GLOBAL_OUTPUT_DEFAULT: int = 100      # default prisoner output per week

# this is what newapp61.py imports
CFG61 = AppConfig61()

def hours_scale(hours_open_per_week: float, full_week: float = None) -> float:
    """
    Scale factor for hours open compared to a full utilisation week.
    """
    try:
        h = float(hours_open_per_week)
        f = float(full_week if full_week is not None else CFG61.FULL_UTILISATION_WEEK)
        if f <= 0:
            return 1.0
        return max(0.0, h / f)
    except Exception:
        return 1.0