from dataclasses import dataclass

@dataclass(frozen=True)
class AppConfig:
    GLOBAL_OUTPUT_DEFAULT: int = 100   # prisoner labour output slider default

CFG = AppConfig()