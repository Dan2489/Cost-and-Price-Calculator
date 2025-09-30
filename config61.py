from dataclasses import dataclass

@dataclass(frozen=True)
class AppConfig61:
    FT2_TO_M2: float = 0.092903
    GLOBAL_OUTPUT_DEFAULT: int = 100

CFG61 = AppConfig61()