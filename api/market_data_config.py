"""Shared market-data paths and supported universe identifiers."""
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SUPPORTED_UNIVERSES = {"US100", "US2000", "US500", "VN30", "VN100"}
DEFAULT_REFRESH_CHECKPOINT_DIR = PROJECT_ROOT / ".cache" / "refresh_checkpoints"
