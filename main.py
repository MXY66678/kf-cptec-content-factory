#!/usr/bin/env python3
"""
KF CPTEC Multi-AI Content Factory — Pipeline Entry Point.

Usage:
    # Sample run (mock data, no API keys needed)
    python main.py sample

    # Run full pipeline with real data
    python main.py run --manifest data/sample/sku_manifest.csv \\
                       --keywords data/sample/keywords.csv \\
                       --specs data/sample/specs.json

    # Single SKU
    python main.py run --sku KF-CPTEC-CRIMP-001

    # Check API config
    python main.py check

    # CLI installed package mode
    pip install -e .
    kf-content-factory check
"""

from __future__ import annotations

import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger as log

from pipeline.cli.app import app


def generate_mock_master(sku_id: str, sku_row: dict[str, str]) -> dict[str, Any]:
    """Generate a mock master.json for dry-run / demo purposes.

    Includes all output sections: blog_structure, seo_keywords, image_prompt_blocks,
    video_links, amazon_listing_blocks — matching the v2.0 schema.
    """
    sections = [
        {
            "heading_level": "h2",
            "heading_text": (
                "Why PEX Connections Fail — and What the Right Tool Prevents"
            ),
            "section_type": "intro",
            "step_intent": None,
            "content_brief": (
                "Problem framing for PEX connection leaks and tool solution. "
                "Hook from informational cluster."
            ),
            "target_word_count": 150,
            "assigned_keywords": ["how to crimp pex pipe", "pex crimp tool"],
            "video_slot": None,
            "image_slot": "img_hero_001",
        },
        {
            "heading_level": "h2",
            "heading_text": (
                f"{sku_row.get('product_name', 'PEX Crimp Tool')} Overview: "
                "Specs, Sizes, and Compatibility"
            ),
            "section_type": "tool_overview",
            "step_intent": None,
            "content_brief": (
                "Spec table from SKU JSON: jaw sizes, material, calibration, "
                "certifications. Map GPT feature blocks."
            ),
            "target_word_count": 250,
            "assigned_keywords": [
                "pex crimp tool", "1/2 inch pex crimp tool",
            ],
            "video_slot": None,
            "image_slot": "img_spec_002",
        },
        {
            "heading_level": "h2",
            "heading_text": "How to Use a PEX Crimp Tool: Step-by-Step",
            "section_type": "how_to_step",
            "step_intent": "overview",
            "content_brief": (
                "Intro line + numbered step list container. "
                "Tools/materials needed list."
            ),
            "target_word_count": 100,
            "assigned_keywords": [
                "how to use pex crimp tool", "pex crimp tool instructions",
            ],
            "video_slot": None,
            "image_slot": None,
        },
        {
            "heading_level": "h3",
            "heading_text": "Step 1: Cut and Prep the PEX Pipe",
            "section_type": "how_to_step",
            "step_intent": "prep",
            "content_brief": (
                "Square cut requirement, deburring, ring placement "
                "distance from pipe end."
            ),
            "target_word_count": 120,
            "assigned_keywords": [
                "how to cut pex pipe", "pex pipe cutting tool",
            ],
            "video_slot": None,
            "image_slot": "img_step_003",
        },
        {
            "heading_level": "h3",
            "heading_text": "Step 2: Position the Ring and Fitting",
            "section_type": "how_to_step",
            "step_intent": "position",
            "content_brief": (
                "Ring orientation, fitting insertion depth, alignment check. "
                "Common mistake callout box."
            ),
            "target_word_count": 120,
            "assigned_keywords": [
                "crimp pex ring tool", "pex fitting installation tool",
            ],
            "video_slot": None,
            "image_slot": "img_step_004",
        },
        {
            "heading_level": "h3",
            "heading_text": "Step 3: Crimp the Connection",
            "section_type": "how_to_step",
            "step_intent": "crimp",
            "content_brief": (
                "Jaw perpendicularity, full handle closure, single-action "
                "requirement. Tool-specific leverage feature from GPT block."
            ),
            "target_word_count": 130,
            "assigned_keywords": [
                "how to crimp pex pipe", "crimp pex pipe without tool",
            ],
            "video_slot": None,
            "image_slot": "img_step_005",
        },
        {
            "heading_level": "h3",
            "heading_text": "Step 4: Verify with the Go/No-Go Gauge",
            "section_type": "how_to_step",
            "step_intent": "inspect",
            "content_brief": (
                "Gauge usage, pass/fail criteria, what to do on fail "
                "(cut out and redo)."
            ),
            "target_word_count": 120,
            "assigned_keywords": [
                "go no-go gauge pex", "how to use go no-go gauge crimp",
            ],
            "video_slot": None,
            "image_slot": "img_step_006",
        },
        {
            "heading_level": "h2",
            "heading_text": (
                "Troubleshooting: Incomplete Crimps, Leaks, and Calibration"
            ),
            "section_type": "how_to_step",
            "step_intent": "troubleshoot",
            "content_brief": (
                "3-4 symptom -> cause -> fix rows. Calibration adjustment "
                "procedure pointer."
            ),
            "target_word_count": 200,
            "assigned_keywords": [
                "pex crimp tool not crimping fully",
                "pex crimp tool won't close",
            ],
            "video_slot": None,
            "image_slot": None,
        },
        {
            "heading_level": "h2",
            "heading_text": (
                "PEX Crimp Tool vs. Cinch Clamp: Which Do You Need?"
            ),
            "section_type": "comparison",
            "step_intent": None,
            "content_brief": (
                "Comparison table: cost, speed, fitting compatibility, "
                "skill level, code acceptance."
            ),
            "target_word_count": 250,
            "assigned_keywords": [
                "pex crimp tool vs cinch clamp",
                "pex crimp tool vs clamp tool",
            ],
            "video_slot": None,
            "image_slot": "img_comparison_007",
        },
        {
            "heading_level": "h2",
            "heading_text": (
                "Choosing the Right Size and Kit Configuration"
            ),
            "section_type": "tool_overview",
            "step_intent": None,
            "content_brief": (
                "Decision guide: 1/2 vs 3/4 vs combo jaw, kit contents "
                "from SKU JSON variants."
            ),
            "target_word_count": 180,
            "assigned_keywords": [
                "pex crimp tool kit", "best pex crimp tool for DIY",
            ],
            "video_slot": None,
            "image_slot": "img_kit_008",
        },
        {
            "heading_level": "h2",
            "heading_text": "Frequently Asked Questions",
            "section_type": "faq",
            "step_intent": None,
            "content_brief": (
                "6-8 Q&A pairs from long-tail question keywords. "
                "FAQPage schema."
            ),
            "target_word_count": 400,
            "assigned_keywords": [
                "what is a pex crimp tool", "do i need a go no-go gauge",
            ],
            "video_slot": None,
            "image_slot": None,
        },
        {
            "heading_level": "h2",
            "heading_text": (
                f"Get the {sku_row.get('product_name', 'PEX Crimp Tool')}"
            ),
            "section_type": "cta",
            "step_intent": None,
            "content_brief": (
                "Short benefit recap, Amazon + Walmart buy buttons, "
                "warranty/support line."
            ),
            "target_word_count": 80,
            "assigned_keywords": ["pex crimp tool"],
            "video_slot": None,
            "image_slot": "img_cta_009",
        },
    ]

    seo_keywords = {
        "intent_clusters": [
            {
                "cluster_name": "how_to_use",
                "intent": "informational",
                "primary": "how to use pex crimp tool",
                "keywords": [
                    "how to use pex crimp tool",
                    "pex crimp tool instructions",
                    "how to use pex crimp ring tool",
                ],
                "long_tail": [
                    "how to crimp pex pipe step by step",
                    "pex crimp tool tutorial for beginners",
                ],
                "merge_candidate": False,
                "mapped_section_type": "how_to_step",
            },
            {
                "cluster_name": "crimp_process",
                "intent": "informational",
                "primary": "how to crimp pex pipe",
                "keywords": [
                    "how to crimp pex pipe",
                    "crimp pex ring tool",
                    "pex crimp tool for copper rings",
                ],
                "long_tail": [
                    "how to crimp pex pipe without tool",
                    "crimp pex pipe with crimp ring tool",
                ],
                "merge_candidate": False,
                "mapped_section_type": "how_to_step",
            },
            {
                "cluster_name": "buying_guide",
                "intent": "transactional",
                "primary": "pex crimp tool",
                "keywords": [
                    "pex crimp tool",
                    f"best pex crimp tool {datetime.now().year}",
                    "pex crimp tool kit",
                    "pex crimp tool for sale",
                ],
                "long_tail": [
                    "best pex crimp tool for DIY",
                    "pex crimp tool for 1/2 and 3/4",
                ],
                "merge_candidate": False,
                "mapped_section_type": "tool_overview",
            },
            {
                "cluster_name": "comparison_guide",
                "intent": "comparison",
                "primary": "pex crimp tool vs clamp tool",
                "keywords": [
                    "pex crimp tool vs clamp tool",
                    "pex crimp tool vs cinch clamp",
                    "pex tool vs propress",
                ],
                "long_tail": [
                    "crimp vs clamp for AquaPEX",
                    "pex crimp vs push fit",
                ],
                "merge_candidate": False,
                "mapped_section_type": "comparison",
            },
            {
                "cluster_name": "troubleshooting",
                "intent": "informational",
                "primary": "pex crimp tool not crimping fully",
                "keywords": [
                    "pex crimp tool not crimping fully",
                    "pex crimp tool won't close",
                    "pex crimp tool leaking",
                ],
                "long_tail": [
                    "pex crimp tool won't release",
                    "how to fix pex crimp leak",
                ],
                "merge_candidate": False,
                "mapped_section_type": "how_to_step",
            },
            {
                "cluster_name": "inspection_gauge",
                "intent": "informational",
                "primary": "go no-go gauge pex",
                "keywords": [
                    "go no-go gauge pex",
                    "how to use go no-go gauge crimp",
                ],
                "long_tail": [
                    "do i need a go no-go gauge",
                    "pex crimp tool with gauge",
                ],
                "merge_candidate": False,
                "mapped_section_type": "how_to_step",
            },
        ],
        "density_targets": {"primary": "1-2%", "secondary": "0.5-1%"},
        "excluded_navigational": [
            "pex crimp tool home depot",
            "pex crimp tool harbor freight",
        ],
    }

    feature_blocks = [
        {
            "feature": "Jaw Material",
            "spec_value": "Forged steel heat-treated jaws",
            "user_benefit": (
                "Delivers consistent crimp force without jaw deformation"
            ),
            "proof_point": "Heat-treated to HRC 45-50 hardness",
            "target_keyword": "pex crimp tool",
            "claim_risk": "none",
        },
        {
            "feature": "Go/No-Go Gauge",
            "spec_value": "Included with tool",
            "user_benefit": (
                "Eliminates guesswork — instantly verify each crimp "
                "meets ASTM F1807 standards"
            ),
            "proof_point": "Included in package",
            "target_keyword": "go no-go gauge pex",
            "claim_risk": "none",
        },
        {
            "feature": "Ergonomic Handle",
            "spec_value": "TPR dual-material grip",
            "user_benefit": "Reduces hand fatigue during multiple crimp installations",
            "proof_point": "TPR over-molded handle design",
            "target_keyword": "best pex crimp tool for DIY",
            "claim_risk": "none",
        },
        {
            "feature": "Compatible Sizes",
            "spec_value": "1/2-inch PEX (ASTM F1807)",
            "user_benefit": (
                "Works with standard 1/2-inch PEX pipe and fittings "
                "from any brand"
            ),
            "proof_point": "ASTM F1807 certified",
            "target_keyword": "1/2 inch pex crimp tool",
            "claim_risk": "none",
        },
        {
            "feature": "Certification",
            "spec_value": "ASTM F1807 + NSF/ANSI 61",
            "user_benefit": (
                "Code-compliant for potable water systems — passes "
                "inspection every time"
            ),
            "proof_point": "NSF/ANSI 61 certified for drinking water",
            "target_keyword": "pex crimp tool",
            "claim_risk": "needs_cert_citation",
        },
    ]

    amazon_listing_blocks = {
        "title_slot": {
            "brief": (
                "KF CPTEC 1/2-Inch PEX Crimp Tool with Go/No-Go Gauge, "
                "Forged Steel, ASTM F1807"
            ),
            "keyword": "pex crimp tool",
            "max_chars": 200,
        },
        "bullet_slots": [
            {
                "feature_block_ref": "Jaw Material",
                "keyword": "pex crimp tool",
                "max_chars": 250,
            },
            {
                "feature_block_ref": "Go/No-Go Gauge",
                "keyword": "go no-go gauge pex",
                "max_chars": 250,
            },
            {
                "feature_block_ref": "Ergonomic Handle",
                "keyword": "best pex crimp tool for DIY",
                "max_chars": 250,
            },
            {
                "feature_block_ref": "Compatible Sizes",
                "keyword": "1/2 inch pex crimp tool",
                "max_chars": 250,
            },
            {
                "feature_block_ref": "Certification",
                "keyword": "pex crimp tool",
                "max_chars": 250,
            },
        ],
        "backend_keywords": [
            "pex crimp tool home depot",
            "pex crimp tool harbor freight",
            "pex crimping pliers",
            "pex ring crimper",
            "pex clamp tool",
            "crimp tool for pex",
            "pex pipe tool",
            "pex cinch tool",
        ],
        "a_plus_modules": [
            {
                "module_type": "comparison_chart",
                "brief": "Comparison table vs other crimp tools",
                "image_slot": "img_comparison_007",
            },
        ],
        "claim_flags": [
            {
                "field": "bullet_slots[4]",
                "claim_risk": "needs_cert_citation",
            },
        ],
        "walmart_blocks": {
            "title_slot": {
                "brief": "KF CPTEC 1/2\" PEX Crimp Tool with Gauge",
                "max_chars": 80,
            },
            "rich_attributes": {
                "Jaw Size": "1/2 inch",
                "Material": "Forged Steel",
                "Includes Gauge": "Yes",
            },
            "shelf_description_brief": (
                "PEX crimp tool with go/no-go gauge for "
                "1/2-inch PEX pipe."
            ),
        },
        "ad_copy_variants": [
            {
                "channel": "ppc",
                "headline_brief": "Professional PEX Crimp Tool",
                "body_brief": "ASTM F1807, includes Go/No-Go gauge",
            },
            {
                "channel": "walmart_sp",
                "headline_brief": "Get the Perfect Crimp Every Time",
                "body_brief": "KF CPTEC crimp tool with gauge",
            },
            {
                "channel": "social",
                "headline_brief": "DIY PEX Plumbing Made Easy",
                "body_brief": "Step-by-step crimp tool guide",
            },
        ],
    }

    video_links_list = [
        {
            "video_id": "dQw4w9WgXcQ",
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "channel": "Plumbing Tutorials",
            "matched_step": (
                "How to Use a PEX Crimp Tool: Step-by-Step"
            ),
            "match_score": 0.82,
            "embed_html": (
                '<iframe width="560" height="315" '
                'src="https://www.youtube.com/embed/dQw4w9WgXcQ" '
                'frameborder="0" allowfullscreen></iframe>'
            ),
            "health_checked_at": "2026-06-15T00:00:00+00:00",
        },
    ]

    master = {
        "sku_id": sku_id,
        "pipeline_version": "2.0",
        "generated_at": "2026-06-15T00:00:00+00:00",
        "state": "ASSEMBLED",
        "sku_json": {
            "sku_id": sku_id,
            "product_name": sku_row.get("product_name", ""),
            "brand": sku_row.get("brand", "KF CPTEC"),
            "category": sku_row.get("category", ""),
            "tool_type": sku_row.get("tool_type", ""),
            "pipe_materials": (
                sku_row.get("pipe_materials", "").split(";")
                if sku_row.get("pipe_materials") else []
            ),
        },
        "blog_structure": {
            "title": (
                f"{sku_row.get('product_name', 'PEX Crimp Tool')}: "
                f"Complete Guide ({datetime.now().year})"
            ),
            "meta_description": (
                "Complete guide to choosing and using a PEX crimp tool. "
                "Step-by-step instructions, troubleshooting, and buying advice."
            ),
            "url_slug": "pex-crimp-tool-guide",
            "schema_markup": ["HowTo", "FAQPage", "Product"],
            "sections": sections,
            "internal_links": [
                "/blog/pex-crimp-tool-vs-clamp",
                "/blog/pex-pipe-cutting-guide",
                "/category/plumbing-tools",
            ],
            "step_intent_vocabulary": [
                "overview", "prep", "position",
                "crimp", "inspect", "troubleshoot",
            ],
        },
        "seo_keywords": seo_keywords,
        "image_prompt_blocks": [
            {
                "block_id": "img_hero_001",
                "placement_section": sections[0]["heading_text"],
                "priority": "high",
                "prompt": "PEX crimp tool hero image",
                "alt_text": sections[0]["heading_text"],
                "type": "hero",
            },
            {
                "block_id": "img_spec_002",
                "placement_section": sections[1]["heading_text"],
                "priority": "normal",
                "prompt": "Tool specs overview",
                "alt_text": sections[1]["heading_text"],
                "type": "step_diagram",
            },
        ],
        "video_links": video_links_list,
        "amazon_listing_blocks": amazon_listing_blocks,
    }

    return master


def generate_sample_data(
) -> tuple[list[dict[str, str]], str, dict[str, dict[str, Any]]]:
    """Generate sample input data for testing the pipeline."""
    sku_manifest = [
        {
            "sku_id": "KF-CPTEC-CRIMP-001",
            "sku_key": "crimp-001",
            "product_name": (
                "KF CPTEC 1/2-Inch PEX Crimp Tool with Go/No-Go Gauge"
            ),
            "brand": "KF CPTEC",
            "category": "crimp",
            "tool_type": "PEX Crimp Tool",
            "pipe_materials": "PEX;PEX-A;PEX-B",
            "upc": "850045678912",
            "weight_lbs": "1.8",
            "dimensions": "10.5 x 4.0 x 1.5 inches",
            "warranty": "Limited Lifetime Warranty",
            "price_msrp": "34.99",
            "color": "Red/Black",
            "material": "Forged steel with TPR grip",
        },
        {
            "sku_id": "KF-CPTEC-CRIMP-002",
            "sku_key": "crimp-002",
            "product_name": "KF CPTEC 3/4-Inch PEX Crimp Tool Kit with Rings",
            "brand": "KF CPTEC",
            "category": "crimp",
            "tool_type": "PEX Crimp Tool",
            "pipe_materials": "PEX;PEX-B",
            "upc": "850045678929",
            "weight_lbs": "2.1",
            "dimensions": "11.0 x 4.5 x 2.0 inches",
            "warranty": "Limited Lifetime Warranty",
            "price_msrp": "42.99",
            "color": "Red/Black",
            "material": "Forged steel",
        },
    ]

    keyword_csv = (
        "keyword,monthly_volume,freq_tier,source,intent\n"
        "pex crimp tool,5400,high,google,transactional\n"
        "how to use pex crimp tool,3200,high,google,informational\n"
        "pex crimp tool vs clamp tool,1800,medium,google,comparison\n"
        f"best pex crimp tool {datetime.now().year},2100,medium,google,transactional\n"
        "pex crimp tool kit,1600,medium,amazon,transactional\n"
        "crimp pex ring tool,1200,medium,google,transactional\n"
        "how to crimp pex pipe,2800,high,google,informational\n"
        "pex crimp tool for sale,900,medium,google,transactional\n"
        "crimp pex pipe without tool,750,low,google,informational\n"
        "pex crimp tool instructions,1100,medium,google,informational\n"
        "pex crimp tool not crimping fully,650,low,google,informational\n"
        "go no-go gauge pex,850,medium,google,informational\n"
        "how to fix pex crimp leak,920,medium,google,informational\n"
        "pex crimp tool won't close,580,low,google,informational\n"
        "pex crimp ring sizes,780,medium,google,informational\n"
        "1/2 inch pex crimp tool,1900,medium,google,transactional\n"
        "3/4 inch pex crimp tool,1400,medium,google,transactional\n"
        "pex crimp tool home depot,1100,medium,google,navigational\n"
        "pex crimp tool harbor freight,950,medium,google,navigational\n"
        "pex tool vs propress,880,medium,google,comparison\n"
        "pex crimp tool PEX-A,720,low,google,transactional\n"
        "pex crimp tool for PEX-B,680,low,google,transactional\n"
        "what is a pex crimp tool,540,low,google,informational\n"
        "pex crimp tool accessories,490,low,google,transactional\n"
        "pex crimp tool maintenance,380,low,google,informational\n"
        "how to use pex crimp ring tool,2100,medium,google,informational\n"
        "pex crimp tool for copper rings,1700,medium,google,transactional\n"
        "crimp tool for pex pipe fittings,1500,medium,amazon,transactional\n"
        "pex crimp tool with gauge,1300,medium,amazon,transactional\n"
        "best pex crimp tool for DIY,1100,medium,google,informational\n"
        "pex crimp tool repair,450,low,google,informational\n"
        "pex crimp tool won't release,350,low,google,informational\n"
    )

    specs_dict = {
        "crimp-001": {
            "specs": [
                {"name": "Jaw Size", "value": "1/2 inch", "unit": "in"},
                {"name": "Material", "value": "Forged Steel", "unit": ""},
                {"name": "Handle Type", "value": "Ergonomic TPR Grip", "unit": ""},
                {"name": "Weight", "value": "1.8", "unit": "lbs"},
                {"name": "Length", "value": "10.5", "unit": "inches"},
                {"name": "Includes Gauge", "value": "Yes (Go/No-Go)", "unit": ""},
                {"name": "Calibration", "value": "Factory calibrated", "unit": ""},
                {"name": "Compatible Pipe Sizes", "value": "1/2-inch PEX", "unit": ""},
            ],
            "bundle_contents": [
                {"name": "Crimp Tool", "quantity": 1, "sku": "CT-12"},
                {"name": "Go/No-Go Gauge", "quantity": 1, "sku": "GNG-12"},
            ],
            "certifications": [
                {
                    "standard": "ASTM F1807",
                    "body": "ASTM",
                    "description": "Standard for PEX fittings",
                },
                {
                    "standard": "NSF/ANSI 61",
                    "body": "NSF",
                    "description": "Drinking water safety",
                },
            ],
            "variants": [
                {
                    "sku_id": "KF-CPTEC-CRIMP-001A",
                    "description": "1/2-inch only variant",
                    "specs": [
                        {"name": "Jaw Size", "value": "1/2 inch", "unit": "in"},
                    ],
                },
            ],
        },
    }

    return sku_manifest, keyword_csv, specs_dict


def save_sample_data(
    manifest: list[dict[str, str]],
    keyword_csv: str,
    specs: dict[str, Any],
) -> None:
    """Write sample data files to disk."""
    data_dir = Path("data") / "sample"
    data_dir.mkdir(parents=True, exist_ok=True)

    with open(data_dir / "sku_manifest.csv", "w", newline="") as f:
        if manifest:
            writer = csv.DictWriter(f, fieldnames=list(manifest[0].keys()))
            writer.writeheader()
            writer.writerows(manifest)

    with open(data_dir / "keywords.csv", "w") as f:
        f.write(keyword_csv)

    with open(data_dir / "specs.json", "w") as f:
        json.dump(specs, f, indent=2, ensure_ascii=False)

    log.info("Sample data written to {}", data_dir.resolve())


def run_sample_pipeline(dry_run: bool = False) -> None:
    """Run the pipeline with sample data (mock mode)."""
    from config import OUTPUT_DIR
    from pipeline.utils.console import (
        print_header,
        print_sku_header,
        print_results_table,
    )

    print_header()
    sku_manifest, keyword_csv, specs_dict = generate_sample_data()
    save_sample_data(sku_manifest, keyword_csv, specs_dict)

    for sku_row in sku_manifest:
        sku_id = sku_row["sku_id"]
        sku_output_dir = OUTPUT_DIR / sku_id
        sku_output_dir.mkdir(parents=True, exist_ok=True)

        print_sku_header(sku_id)
        master = generate_mock_master(sku_id, sku_row)
        blog_structure = master["blog_structure"]
        amazon_listing = master["amazon_listing_blocks"]

        with open(sku_output_dir / "master.json", "w") as f:
            json.dump(master, f, indent=2, ensure_ascii=False)
        with open(sku_output_dir / "blog_structure.json", "w") as f:
            json.dump(blog_structure, f, indent=2, ensure_ascii=False)
        with open(sku_output_dir / "amazon_listing.json", "w") as f:
            json.dump(amazon_listing, f, indent=2, ensure_ascii=False)

        # Calculate & print stats
        sections = len(blog_structure.get("sections", []))
        clusters = len(master.get("seo_keywords", {}).get("intent_clusters", []))
        videos = master.get("video_links", [])
        print_results_table(
            sku_id=sku_id,
            sections=sections,
            clusters=clusters,
            coverage_pct=1.0,
            videos_filled=len(videos),
            videos_total=6,
            state="ASSEMBLED",
        )

    log.info("Sample pipeline complete. Output in {}", OUTPUT_DIR)


if __name__ == "__main__":
    app()
