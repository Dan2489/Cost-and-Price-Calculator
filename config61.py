from dataclasses import dataclass

@dataclass(frozen=True)
class AppConfig:
    DAYS_PER_MONTH: float = 365.0 / 12.0  # ≈30.42
    DEFAULT_ADMIN_MONTHLY: float = 150.0
    GLOBAL_OUTPUT_DEFAULT: int = 100

CFG = AppConfig()