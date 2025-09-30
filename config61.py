# config61.py
from dataclasses import dataclass, field

@dataclass(frozen=True)
class AppConfig:
    VAT_RATE: float = 20.0                 # VAT used for Commercial pricing display
    DEV_RATE_BASE: float = 0.20            # Development charge starts at 20%
    GLOBAL_OUTPUT_DEFAULT: int = 100       # Default prisoner output %
    SHADOW_COSTS: dict = field(default_factory=lambda: {
        "Outer London": 45855.97,
        "Inner London": 49202.70,
        "National": 42247.81,
    })

    # Allow dict-style access too: CFG["VAT_RATE"]
    def __getitem__(self, key: str):
        return getattr(self, key)

# single shared config instance
CFG = AppConfig()
    },
}