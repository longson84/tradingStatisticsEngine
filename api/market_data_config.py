"""Shared market-data paths and supported universe identifiers."""
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
US_UNIVERSES = ("US500", "US2000", "US100")
VN_UNIVERSES = ("VNALL", "VN100", "VN30", "VNMID", "VNSML")
SUPPORTED_UNIVERSES = {*US_UNIVERSES, *VN_UNIVERSES}
DEFAULT_REFRESH_CHECKPOINT_DIR = PROJECT_ROOT / ".cache" / "refresh_checkpoints"
