from dataclasses import dataclass

@dataclass(frozen=True)
class AppConfig:
    """
    Core configuration constants for the Instructor-only model.
    (Utilities, tariffs, and workshop size are no longer used.)
    """
    DAYS_PER_MONTH: float = 365.0 / 12.0   # ≈30.42
    FULL_UTILISATION_WEEK: float = 37.5    # reference week for instructor % allocation
    GLOBAL_OUTPUT_DEFAULT: int = 100       # default output %

CFG = AppConfig()

def hours_scale(hours_open_per_week: float, full_week: float | None = None) -> float:
    """
    Scale factor: actual open hours ÷ reference week hours.
    Used for instructor % allocation guidance.
    """
    try:
        h = float(hours_open_per_week)
        f = float(full_week if full_week is not None else CFG.FULL_UTILISATION_WEEK)
        if f <= 0:
            return 1.0
        return max(0.0, h / f)
    except Exception:
        return 1.0