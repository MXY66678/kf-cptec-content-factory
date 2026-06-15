# KF CPTEC Multi-AI Content Factory v2.0

> **Automated SEO content pipeline for e-commerce SKUs.**  
> DeepSeek → GPT → Claude → YouTube → Assembly — one command per SKU.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](pyproject.toml)

---

## Overview

The **KF CPTEC Content Factory** is a production-grade automation pipeline that takes raw SKU data and keyword research and produces publish-ready content assets for each product:

| Module | AI | What it produces |
|--------|-----|------------------|
| **M1** | DeepSeek | Keyword clusters grouped by search intent (informational / transactional / comparison) |
| **M2** | GPT | Feature → benefit mappings, Amazon listing blocks, Walmart rich attributes, ad copy variants |
| **M3** | Claude | Blog structure skeleton — heading tree, section briefs, schema markup — **no full prose** |
| **M4** | YouTube Data API | Existing video retrieval for each how-to step — **never generates video** |
| **Assembly** | Codex | Deep-merge into `master.json`, validate keyword coverage, enforce field length limits |

### Output per SKU

```
pipeline/output/{sku_id}/
├── master.json           # Complete assembled output
├── blog_structure.json   # Claude-generated blog skeleton
└── amazon_listing.json   # GPT-generated listing blocks
```

---

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/kf-cptec/content-factory.git
cd content-factory
pip install -r requirements.txt

# 2. Run sample pipeline (no API keys needed)
python main.py sample

# 3. Check output
cat pipeline/output/KF-CPTEC-CRIMP-001/master.json
```

### Live Run (requires API keys)

```bash
# 1. Configure API keys
cp .env.example .env
# Edit .env with your keys: DeepSeek, OpenAI, Anthropic, YouTube

# 2. Run full pipeline
python main.py run --live

# 3. Single SKU
python main.py run --sku KF-CPTEC-CRIMP-001 --live
```

---

## CLI Reference

The pipeline uses **typer** (built on Click) for a modern CLI experience with **rich** terminal formatting.

```bash
# Entry points
python main.py --help
# or if installed
kf-content-factory --help

# Commands:
run       Execute the full pipeline (batch or single SKU)
sample    Generate sample data with mock pipeline output
status    Show pipeline status for a specific SKU
check     Validate API configuration and environment
list-skus List all SKUs in a manifest
```

### `run` options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--manifest` | `-m` | `data/sample/sku_manifest.csv` | Path to SKU manifest CSV |
| `--keywords` | `-k` | `data/sample/keywords.csv` | Path to keyword table CSV |
| `--specs` | `-s` | `data/sample/specs.json` | Path to specs JSON file |
| `--sku` | `-u` | — | Process a single SKU only |
| `--workers` | `-w` | `3` | Parallel worker count |
| `--dry-run` | `-n` | — | Mock mode (no API calls) |
| `--live` | `-l` | — | Use real API calls |

---

## Project Structure

```
kf-cptec-content-factory/
├── main.py                      # Entry point (typer CLI)
├── config.py                    # Env-based config + YAML template loader
├── requirements.txt             # Python dependencies
├── pyproject.toml               # Package metadata
├── .env.example                 # API key template
├── .gitignore
├── LICENSE                      # MIT
│
├── pipeline/
│   ├── core/
│   │   ├── orchestrator.py      # DAG executor, batch runner
│   │   └── state_machine.py     # Per-SKU state machine
│   ├── modules/
│   │   ├── deepseek.py          # M1: Keyword clustering
│   │   ├── gpt.py               # M2: Feature/listing generation
│   │   ├── claude.py            # M3: Blog structure
│   │   └── youtube.py           # M4: Video retrieval
│   ├── schemas/
│   │   ├── sku_schema.py        # SKUCanonical (pydantic)
│   │   ├── blog_schema.py       # BlogStructure (pydantic)
│   │   ├── seo_schema.py        # SEOKeywords (pydantic)
│   │   └── video_schema.py      # VideoLinks (pydantic)
│   ├── utils/
│   │   ├── console.py           # Rich terminal UI helpers
│   │   ├── retry.py             # Exponential backoff + JSON fallback
│   │   ├── logger.py            # Per-SKU JSONL audit trail
│   │   ├── validator.py         # Assembly validation suite
│   │   └── http_client.py       # Shared HTTP client with 429 handling
│   └── cli/
│       └── app.py               # Typer CLI commands
│
├── data/
│   ├── sample/                  # Generated sample data
│   └── category_templates/      # YAML templates per tool category
│       ├── crimp.yaml
│       ├── press.yaml
│       └── cutter.yaml
│
├── output/                      # Pipeline outputs (gitignored)
├── logs/                        # Pipeline logs (gitignored)
└── .github/workflows/           # CI/CD
    └── pipeline.yml             # GitHub Actions workflows
```

---

## Pipeline Architecture

```
┌─────────────┐  ┌──────────────┐  ┌─────────────┐
│  SKU CSV    │  │  Keywords    │  │  Spec JSON  │
│  Manifest   │  │  Table       │  │  Data       │
└──────┬──────┘  └──────┬───────┘  └──────┬──────┘
       │                │                 │
       ▼                ▼                 ▼
┌────────────────────────────────────────────────────────┐
│              NORMALIZATION & ROUTING                     │
│         SKU.json → category→ template selection          │
└───────────────────────┬────────────────────────────────┘
                        │
                        ▼
    ┌─────────────┐   ┌────────────┐   ┌────────────┐
    │  M1 DeepSeek│──▶│  M2 GPT    │──▶│  M3 Claude │
    │  Clustering │   │  Feature/  │   │  Blog      │
    │             │   │  Listing   │   │  Structure │
    └─────────────┘   └────────────┘   └──────┬─────┘
                                              │
                                              ▼
                                     ┌──────────────┐
                                     │  M4 YouTube  │
                                     │  Retrieval   │
                                     └──────┬───────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────┐
│           ASSEMBLY & VALIDATION                          │
│   merge → master.json   validate → coverage ✅/❌       │
└────────────────────────────────────────────────────────┘
```

### State Machine

Each SKU progresses through: `PENDING → M1 → M2 → M3 → M4 → ASSEMBLED → (QA_HOLD) → PUBLISH_READY → PUBLISHED`

---

## Key Design Rules

1. **No full blog content** — Claude produces only structure (heading trees + section briefs)
2. **No generated videos** — YouTube module searches real existing videos only
3. **Validation is mandatory** — invalid module output retries once with `"OUTPUT JSON ONLY"` then fails the SKU
4. **Idempotent** — state machine saves to disk; re-running a completed SKU resumes from last state
5. **Keyword coverage ≥ 90%** — all clusters must be mapped to blog sections or the assembly fails

---

## GitHub Tools Used

This project integrates several excellent open-source libraries:

| Tool | GitHub | Version | Purpose |
|------|--------|---------|---------|
| **Rich** | [Textualize/rich](https://github.com/Textualize/rich) | 15.0+ | Beautiful terminal output with tables, panels, trees |
| **Typer** | [fastapi/typer](https://github.com/fastapi/typer) | 0.12+ | Modern CLI framework (built on Click) |
| **TQDM** | [tqdm/tqdm](https://github.com/tqdm/tqdm) | 4.60+ | Progress bars for batch processing |
| **Tenacity** | [jd/tenacity](https://github.com/jd/tenacity) | 9.0+ | Retry/backoff for API calls |
| **Pydantic** | [pydantic/pydantic](https://github.com/pydantic/pydantic) | 2.0+ | Schema validation with strict type checking |
| **HTTPX** | [encode/httpx](https://github.com/encode/httpx) | 0.27+ | Async-capable HTTP client |
| **Loguru** | [Delgan/loguru](https://github.com/Delgan/loguru) | 0.7+ | Structured logging with zero boilerplate |
| **Google API Client** | [googleapis/google-api-python-client](https://github.com/googleapis/google-api-python-client) | 2.0+ | YouTube Data API v3 integration |

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DEEPSEEK_API_KEY` | Live mode | — | DeepSeek API key |
| `OPENAI_API_KEY` | Live mode | — | OpenAI API key |
| `ANTHROPIC_API_KEY` | Live mode | — | Anthropic API key |
| `YOUTUBE_API_KEY` | Live mode | — | YouTube Data API v3 key |
| `PIPELINE_MAX_WORKERS` | No | `3` | Parallel SKU workers |
| `KEYWORD_COVERAGE_PCT` | No | `0.90` | Minimum keyword cluster coverage |
| `YT_SCORE_THRESHOLD` | No | `0.55` | Minimum video match score |

---

## License

MIT — see [LICENSE](LICENSE).

---

## About KF CPTEC

KF CPTEC manufactures professional-grade plumbing tools for PEX, copper, and CPVC systems. This pipeline was built to automate SEO content production across an expanding product catalog.
