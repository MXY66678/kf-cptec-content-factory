"""Per-SKU state machine for the pipeline workflow.

States: PENDING → M1 → M2 → M3 → M4 → ASSEMBLED → QA_HOLD → PUBLISH_READY → PUBLISHED → FAILED
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from loguru import logger as log

from config import OUTPUT_DIR, VALID_STATES


class SKUStateMachine:
    """Manages the state of a single SKU through the pipeline.

    State transitions:
    PENDING → M1 → M2 → M3 → M4 → ASSEMBLED → QA_HOLD → PUBLISH_READY → PUBLISHED
    Any state → FAILED
    """

    VALID_TRANSITIONS: dict[str, list[str]] = {
        "PENDING": ["M1", "FAILED"],
        "M1": ["M2", "FAILED"],
        "M2": ["M3", "FAILED"],
        "M3": ["M4", "FAILED"],
        "M4": ["ASSEMBLED", "FAILED"],
        "ASSEMBLED": ["QA_HOLD", "PUBLISH_READY", "FAILED"],
        "QA_HOLD": ["PUBLISH_READY", "FAILED"],
        "PUBLISH_READY": ["PUBLISHED", "FAILED"],
        "PUBLISHED": [],
        "FAILED": [],
    }

    def __init__(
        self,
        sku_id: str,
        initial_state: str = "PENDING",
    ) -> None:
        """Initialize state machine for a SKU.

        Args:
            sku_id: SKU identifier.
            initial_state: Starting state. Defaults to PENDING.
        """
        self.sku_id = sku_id
        self.state = initial_state
        self._state_path = OUTPUT_DIR / sku_id / "_state.json"
        self._output_dir = OUTPUT_DIR / sku_id
        self._output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def is_terminal(self) -> bool:
        """Check if the current state is terminal (PUBLISHED or FAILED)."""
        return self.state in ("PUBLISHED", "FAILED")

    @property
    def is_failed(self) -> bool:
        return self.state == "FAILED"

    def transition_to(self, new_state: str) -> None:
        """Transition to a new state.

        Args:
            new_state: Target state.

        Raises:
            ValueError: If transition is not allowed.
        """
        allowed = self.VALID_TRANSITIONS.get(self.state, [])
        if new_state not in allowed:
            raise ValueError(
                f"Invalid state transition: {self.state} → {new_state}. "
                f"Allowed: {allowed}"
            )
        old_state = self.state
        self.state = new_state
        log.info("[{}] State: {} → {}", self.sku_id, old_state, new_state)
        self._persist()

    def fail(self) -> None:
        """Transition to FAILED state."""
        self.transition_to("FAILED")

    def _persist(self) -> None:
        """Write current state to disk for idempotency."""
        data = {
            "sku_id": self.sku_id,
            "state": self.state,
            "output_dir": str(self._output_dir),
        }
        with open(self._state_path, "w") as f:
            json.dump(data, f, indent=2)

    def load_from_disk(self) -> Optional[dict[str, Any]]:
        """Reload state from disk. Returns None if no saved state."""
        if self._state_path.exists():
            with open(self._state_path) as f:
                saved = json.load(f)
            self.state = saved.get("state", "PENDING")
            return saved
        return None

    def get_module_output_path(self, module: str) -> Path:
        """Get the output path for a module's intermediate results."""
        return self._output_dir / f"{module}.json"

    def save_module_output(self, module: str, data: dict[str, Any]) -> None:
        """Save a module's output to disk."""
        path = self.get_module_output_path(module)
        with open(path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        log.debug("[{}] Saved {} output: {}", self.sku_id, module, path)

    def load_module_output(self, module: str) -> Optional[dict[str, Any]]:
        """Load a module's output from disk if it exists."""
        path = self.get_module_output_path(module)
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return None

    def get_output_paths(self) -> dict[str, Path]:
        """Get all final output paths for this SKU."""
        return {
            "master": self._output_dir / "master.json",
            "blog_structure": self._output_dir / "blog_structure.json",
            "amazon_listing": self._output_dir / "amazon_listing.json",
        }
