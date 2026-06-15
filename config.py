"""KF CPTEC Multi-AI Content Factory — Configuration & Settings.

Loads env vars, YAML category templates, and provides typed config.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import yaml
from dotenv import load_dotenv
from loguru import logger as log

load_dotenv()

# ── Project paths ─────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.resolve()
PIPELINE_DIR = PROJECT_ROOT / "pipeline"
OUTPUT_DIR = PIPELINE_DIR / "output"
LOGS_DIR = PIPELINE_DIR / "logs"
CONFIG_DIR = PROJECT_ROOT / "data" / "category_templates"
DATA_DIR = PROJECT_ROOT / "data" / "sample"

# ── API Keys ───────────────────────────────────────────────────
DEEPSEEK_API_KEY: Optional[str] = os.getenv("DEEPSEEK_API_KEY")
OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY") or os.getenv("GPT_API_KEY")
ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
YOUTUBE_API_KEY: Optional[str] = os.getenv("YOUTUBE_API_KEY")

# ── API Endpoints ──────────────────────────────────────────────
DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com")
ANTHROPIC_BASE_URL: str = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
YOUTUBE_BASE_URL: str = "https://www.googleapis.com/youtube/v3"

# ── Model names ────────────────────────────────────────────────
DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
GPT_MODEL: str = os.getenv("GPT_MODEL", "gpt-4o")
CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

# ── Pipeline settings ──────────────────────────────────────────
MAX_WORKERS: int = int(os.getenv("PIPELINE_MAX_WORKERS", "3"))
MAX_RETRIES: int = int(os.getenv("PIPELINE_MAX_RETRIES", "3"))
RETRY_MIN_WAIT: float = float(os.getenv("PIPELINE_RETRY_MIN_WAIT", "2.0"))
RETRY_MAX_WAIT: float = float(os.getenv("PIPELINE_RETRY_MAX_WAIT", "60.0"))
REQUIRED_KEYWORD_COVERAGE: float = float(os.getenv("KEYWORD_COVERAGE_PCT", "0.90"))

# ── YouTube quota ──────────────────────────────────────────────
YT_CACHE_TTL_DAYS: int = int(os.getenv("YT_CACHE_TTL_DAYS", "30"))
YT_MAX_RESULTS: int = int(os.getenv("YT_MAX_RESULTS", "10"))
YT_SCORE_THRESHOLD: float = float(os.getenv("YT_SCORE_THRESHOLD", "0.55"))
YT_DAILY_QUOTA: int = int(os.getenv("YT_DAILY_QUOTA", "10000"))

# ── Category templates (YAML) ──────────────────────────────────
_CATEGORY_TEMPLATES: dict[str, dict[str, Any]] | None = None


def get_category_template(category: str) -> dict[str, Any]:
    """Load a YAML category template by name (crimp, press, cutter, expander).

    Returns default template if file not found.
    """
    global _CATEGORY_TEMPLATES
    if _CATEGORY_TEMPLATES is None:
        _CATEGORY_TEMPLATES = {}
        if CONFIG_DIR.exists():
            for yaml_file in CONFIG_DIR.glob("*.yaml"):
                try:
                    with open(yaml_file) as f:
                        data = yaml.safe_load(f)
                    if data and "category" in data:
                        _CATEGORY_TEMPLATES[data["category"]] = data
                except Exception as e:
                    log.warning("Failed to load {}: {}", yaml_file, e)
        else:
            log.info("Category templates dir not found: {}", CONFIG_DIR)

    return _CATEGORY_TEMPLATES.get(category, {})


def list_categories() -> list[str]:
    """Return available category names."""
    get_category_template("")  # ensure loaded
    return list(_CATEGORY_TEMPLATES.keys()) if _CATEGORY_TEMPLATES else []


# ── State machine ──────────────────────────────────────────────
VALID_STATES: list[str] = [
    "PENDING", "M1", "M2", "M3", "M4",
    "ASSEMBLED", "QA_HOLD", "PUBLISH_READY", "PUBLISHED", "FAILED",
]
