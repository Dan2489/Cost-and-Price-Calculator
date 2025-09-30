# config61.py
from dataclasses import dataclass

@dataclass(frozen=True)
class AppConfig:
    vat_rate: float = 20.0
    development_charge: float = 0.20
    GLOBAL_OUTPUT_DEFAULT: int = 100
    overheads_rate: float = 0.61

CFG = AppConfig()