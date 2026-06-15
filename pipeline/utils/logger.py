"""JSONL logging system for per-SKU audit trails."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from loguru import logger as loguru_logger

from config import LOGS_DIR


class SKULogger:
    """Per-SKU JSONL audit trail logger.

    Writes structured log entries to /logs/{sku_id}.jsonl.
    Also emits a global failures queue for retryable errors.
    """

    def __init__(self, sku_id: str) -> None:
        self.sku_id = sku_id
        self.log_path = LOGS_DIR / f"{sku_id}.jsonl"
        self.failures_path = LOGS_DIR / "failures.jsonl"
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def _write_entry(self, entry: dict[str, Any]) -> None:
        """Write a single JSONL entry to the SKU log file."""
        entry["timestamp"] = datetime.now(timezone.utc).isoformat()
        entry["sku_id"] = self.sku_id
        line = json.dumps(entry, ensure_ascii=False, default=str)
        with open(self.log_path, "a") as f:
            f.write(line + "\n")

    def log(self, stage: str, status: str, **extra: Any) -> None:
        """Log a structured event.

        Args:
            stage: Pipeline stage name (ingest, M1, M2, M3, M4, assembly, publish).
            status: 'started', 'completed', 'retry', 'failed'.
            extra: Additional key-value pairs (error, retryable, etc.).
        """
        entry = {"stage": stage, "status": status, **extra}
        self._write_entry(entry)
        loguru_logger.info("[{}] {}: {}", self.sku_id, stage, status)

    def log_failure(self, stage: str, error: str, retryable: bool = False) -> None:
        """Log a failure both to SKU log and the global failures queue."""
        entry = {
            "stage": stage,
            "status": "failed",
            "error": error,
            "retryable": retryable,
        }
        self._write_entry(entry)
        # Also write to shared failures queue
        fail_entry = {
            "sku_id": self.sku_id,
            "stage": stage,
            "error": error,
            "retryable": retryable,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.failures_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.failures_path, "a") as f:
            f.write(json.dumps(fail_entry, ensure_ascii=False) + "\n")
        loguru_logger.error("[{}] FAILED at {}: {} (retryable={})",
                            self.sku_id, stage, error, retryable)

    def log_started(self, stage: str) -> None:
        self.log(stage, "started")

    def log_completed(self, stage: str) -> None:
        self.log(stage, "completed")

    def log_retry(self, stage: str, error: str, attempt: int) -> None:
        self.log(stage, "retry", error=error, attempt=attempt)

    def read_log(self) -> list[dict[str, Any]]:
        """Read all log entries for this SKU."""
        if not self.log_path.exists():
            return []
        entries = []
        with open(self.log_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries


class PipelineLogger:
    """Global pipeline logging helper."""

    @staticmethod
    def setup() -> None:
        """Configure loguru for pipeline-wide logging."""
        loguru_logger.remove()
        loguru_logger.add(
            lambda msg: print(msg, end=""),
            format=(
                "<green>{time:HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan> | "
                "<level>{message}</level>"
            ),
            level="DEBUG",
        )
        loguru_logger.add(
            LOGS_DIR / "pipeline.log",
            rotation="10 MB",
            retention=7,
            level="DEBUG",
        )
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
