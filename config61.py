# config61.py

from dataclasses import dataclass, field

@dataclass(frozen=True)
class AppConfig:
    # VAT percentage
    VAT_RATE: float = 20.0

    # Base development charge rate (20%)
    DEV_RATE_BASE: float = 0.20

    # Default prisoner output percentage (100%)
    GLOBAL_OUTPUT_DEFAULT: int = 100

    # Shadow Band 3 costs (annual) for when customer provides instructors
    SHADOW_COSTS: dict = field(default_factory=lambda: {
        "Outer London": 45855.97,
        "Inner London": 49202.70,
        "National": 42247.81,
    })

    def __getitem__(self, key: str):
        return getattr(self, key)

# Global config object
CFG = AppConfig()