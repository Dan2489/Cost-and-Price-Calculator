# config61.py
from dataclasses import dataclass

@dataclass(frozen=True)
class AppConfig61:
    # Default prisoner labour output (%) for Production when the user doesn’t touch the slider
    global_output_default: int = 100

CFG = AppConfig61()