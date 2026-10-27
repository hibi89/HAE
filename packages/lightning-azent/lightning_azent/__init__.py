"""Lightning Azent isolated, local-first workflow engine package (prototype)."""
__version__ = "0.1.0-dev"
from .engine import Engine, PlanError, ApprovalRequired, validate
from .contract import NATIVE_VERSION, LEGACY_VERSION, capabilities, prepare_plan
from .runtime import LAExecutor
