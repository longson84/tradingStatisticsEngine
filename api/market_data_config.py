"""Shared data-operation paths."""
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REFRESH_CHECKPOINT_DIR = PROJECT_ROOT / ".cache" / "refresh_checkpoints"
