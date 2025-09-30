# config61.py
# Central configuration for the Cost and Price Calculator (61% overheads model)

from dataclasses import dataclass, field

@dataclass(frozen=True)
class AppConfig:
    VAT_RATE: float = 20.0                 # VAT applied only for Commercial in displays
    DEV_RATE_BASE: float = 0.20            # Development charge starts at 20% (Commercial only)
    GLOBAL_OUTPUT_DEFAULT: int = 100       # Planned Output% default
    FULL_UTILISATION_WEEK: float = 37.5    # for recommendations

    # Band 3 shadow costs (annual) for “customer provides instructor(s)”
    SHADOW_COSTS: dict = field(default_factory=lambda: {
        "Outer London": 45855.97,
        "Inner London": 49202.70,
        "National": 42247.81,
    })

CFG = AppConfig()