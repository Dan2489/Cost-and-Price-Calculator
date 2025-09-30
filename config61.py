# config61.py
from dataclasses import dataclass

@dataclass(frozen=True)
class AppConfig:
    FULL_UTILISATION_WEEK: float = 37.5   # reference week for hours scaling
    GLOBAL_OUTPUT_DEFAULT: int = 100      # default planned prisoner output %

CFG = AppConfig()