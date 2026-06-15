"""Pipeline Orchestrator — runs the end-to-end SKU processing DAG.

Per-SKU state machine: PENDING → M1 → M2 → M3 → M4 → ASSEMBLED → FAILED
Supports parallel batch execution with configurable worker count.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from loguru import logger as log

from config import MAX_WORKERS, OUTPUT_DIR, REQUIRED_KEYWORD_COVERAGE
from pipeline.core.state_machine import SKUStateMachine
from pipeline.modules.deepseek import DeepSeekModule
from pipeline.modules.gpt import GPTModule
from pipeline.modules.claude import ClaudeModule
from pipeline.modules.youtube import YouTubeModule
from pipeline.schemas.blog_schema import BlogStructure
from pipeline.schemas.sku_schema import SKUCanonical
from pipeline.utils.logger import SKULogger
from pipeline.utils.validator import validate_assembly, validate_json_string


class Orchestrator:
    """Pipeline orchestrator — runs the full DAG for one or more SKUs.

    Idempotent: re-running an already-completed SKU skips completed stages.
    """

    def __init__(self, max_workers: int = MAX_WORKERS) -> None:
        self.max_workers = max_workers
        self.deepseek = DeepSeekModule()
        self.gpt = GPTModule()
        self.claude = ClaudeModule()
        self.youtube = YouTubeModule()
        self._setup_dirs()

    def _setup_dirs(self) -> None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def _build_master(
        self,
        sku_id: str,
        sku_json: dict[str, Any],
        seo_keywords: dict[str, Any],
        feature_blocks: list[dict[str, Any]],
        amazon_listing_blocks: dict[str, Any],
        blog_structure: dict[str, Any],
        video_links: dict[str, Any],
    ) -> dict[str, Any]:
        """Assemble all module outputs into master.json.

        Args:
            sku_id: SKU identifier.
            sku_json: Canonical SKU data.
            seo_keywords: M1 output.
            feature_blocks: M2 feature blocks (part of GPT output).
            amazon_listing_blocks: M2 listing blocks.
            blog_structure: M3 output.
            video_links: M4 output.

        Returns:
            Complete master.json dict.
        """
        # Build image_prompt_blocks from sections that need images
        sections = blog_structure.get("sections", [])
        image_prompt_blocks = []
        for sec in sections:
            img_slot = sec.get("image_slot")
            if img_slot and img_slot != "null":
                image_prompt_blocks.append({
                    "block_id": img_slot,
                    "placement_section": sec.get("heading_text", ""),
                    "priority": "high" if sec.get("video_slot") in (None, "null", "") else "normal",
                    "prompt": f"Product image for: {sec.get('heading_text', '')}",
                    "alt_text": sec.get("heading_text", ""),
                    "type": "step_diagram" if sec.get("section_type") == "how_to_step" else "hero",
                })

        # Build video_links list from M4 mappings
        video_links_list = []
        for mapping in video_links.get("mappings", []):
            if mapping.get("slot_filled") and mapping.get("video"):
                video_links_list.append(mapping["video"])

        # Update blog_structure sections with video_slot from M4
        section_map = {}
        for mapping in video_links.get("mappings", []):
            section_map[mapping["section_heading"]] = mapping

        for sec in sections:
            heading = sec.get("heading_text", "")
            if heading in section_map:
                mapping = section_map[heading]
                if mapping.get("slot_filled") and mapping.get("video"):
                    sec["video_slot"] = mapping["video"]["video_id"]
                else:
                    sec["video_slot"] = None

        # Build SEO keywords with mapped_sections
        cluster_to_section: dict[str, list[str]] = {}
        for sec in sections:
            for kw in sec.get("assigned_keywords", []):
                for cluster in seo_keywords.get("intent_clusters", []):
                    if kw.lower() == cluster.get("primary", "").lower() or kw.lower() in [
                        k.lower() for k in cluster.get("keywords", [])
                    ]:
                        section_heading = sec.get("heading_text", "")
                        cn = cluster["cluster_name"]
                        if cn not in cluster_to_section:
                            cluster_to_section[cn] = []
                        if section_heading not in cluster_to_section[cn]:
                            cluster_to_section[cn].append(section_heading)

        for cluster in seo_keywords.get("intent_clusters", []):
            cn = cluster["cluster_name"]
            cluster["mapped_sections"] = cluster_to_section.get(cn, [])

        master = {
            "sku_id": sku_id,
            "pipeline_version": "2.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "state": "ASSEMBLED",
            "sku_json": sku_json,
            "blog_structure": blog_structure,
            "seo_keywords": seo_keywords,
            "image_prompt_blocks": image_prompt_blocks,
            "video_links": video_links_list,
            "amazon_listing_blocks": amazon_listing_blocks,
        }
        return master

    def process_single_sku(
        self,
        sku_id: str,
        sku_csv_row: dict[str, str],
        keyword_csv: str,
        specs_json_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Process a single SKU through the full pipeline.

        Steps:
        1. Normalize SKU → canonical SKU.json
        2. M1: DeepSeek keyword clustering
        3. M2: GPT feature extraction + listing blocks
        4. M3: Claude blog structure
        5. M4: YouTube video retrieval
        6. Assemble master.json
        7. Validate

        Args:
            sku_id: SKU identifier.
            sku_csv_row: Raw SKU manifest row as dict.
            keyword_csv: Keyword table as CSV string.
            specs_json_data: Feature/spec data as dict.

        Returns:
            Master.json dict for this SKU.
        """
        sku_logger = SKULogger(sku_id)
        state_machine = SKUStateMachine(sku_id)

        # Reload saved state if exists (idempotency)
        saved = state_machine.load_from_disk()
        if saved:
            log.info("[{}] Resuming from state: {}", sku_id, state_machine.state)

        # ── Step 0: Normalize SKU ──────────────────────────────
        if state_machine.state == "PENDING":
            sku_logger.log_started("ingest")
            try:
                sku_json = self._normalize_sku(sku_id, sku_csv_row, specs_json_data)
                state_machine.save_module_output("sku_canonical", sku_json)
                sku_logger.log_completed("ingest")
                state_machine.transition_to("M1")
            except Exception as e:
                sku_logger.log_failure("ingest", str(e), retryable=False)
                state_machine.fail()
                raise
        else:
            sku_json = state_machine.load_module_output("sku_canonical") or {}
            log.info("[{}] SKU already ingested, skipping", sku_id)

        # ── Step 1: M1 DeepSeek ────────────────────────────────
        if state_machine.state == "M1":
            sku_logger.log_started("M1")
            try:
                sku_context = {
                    "sku_id": sku_id,
                    "category": sku_json.get("category", ""),
                    "tool_type": sku_json.get("tool_type", ""),
                    "pipe_materials": sku_json.get("pipe_materials", []),
                    "product_name": sku_json.get("product_name", ""),
                }
                seo_keywords = self.deepseek.run(keyword_csv, sku_context)
                state_machine.save_module_output("M1", seo_keywords)
                sku_logger.log_completed("M1")
                state_machine.transition_to("M2")
            except Exception as e:
                sku_logger.log_failure("M1", str(e), retryable=False)
                state_machine.fail()
                raise
        else:
            seo_keywords = state_machine.load_module_output("M1") or {}
            log.info("[{}] M1 already complete, skipping", sku_id)

        # ── Step 2: M2 GPT ─────────────────────────────────────
        if state_machine.state == "M2":
            sku_logger.log_started("M2")
            try:
                tx_clusters = [
                    c for c in seo_keywords.get("intent_clusters", [])
                    if c.get("intent") in ("transactional", "comparison")
                ]
                gpt_output = self.gpt.run(sku_json, tx_clusters)
                state_machine.save_module_output("M2", gpt_output)
                sku_logger.log_completed("M2")
                state_machine.transition_to("M3")
            except Exception as e:
                sku_logger.log_failure("M2", str(e), retryable=False)
                state_machine.fail()
                raise
        else:
            gpt_output = state_machine.load_module_output("M2") or {}
            log.info("[{}] M2 already complete, skipping", sku_id)

        feature_blocks = gpt_output.get("feature_blocks", [])
        amazon_listing_blocks = gpt_output.get("amazon_listing_blocks", {})

        # ── Step 3: M3 Claude ──────────────────────────────────
        if state_machine.state == "M3":
            sku_logger.log_started("M3")
            try:
                blog_structure = self.claude.run(
                    sku_json=sku_json,
                    keyword_clusters=seo_keywords,
                    feature_blocks=feature_blocks,
                )
                # Validate blog structure schema
                validate_json_string(
                    json.dumps(blog_structure),
                    BlogStructure,
                )
                state_machine.save_module_output("M3", blog_structure)
                sku_logger.log_completed("M3")
                state_machine.transition_to("M4")
            except Exception as e:
                sku_logger.log_failure("M3", str(e), retryable=False)
                state_machine.fail()
                raise
        else:
            blog_structure = state_machine.load_module_output("M3") or {}
            log.info("[{}] M3 already complete, skipping", sku_id)

        # ── Step 4: M4 YouTube ─────────────────────────────────
        if state_machine.state == "M4":
            sku_logger.log_started("M4")
            try:
                video_links = self.youtube.run(
                    sections=blog_structure.get("sections", []),
                    keyword_clusters=seo_keywords,
                    tool_type=sku_json.get("tool_type", ""),
                    pipe_materials=sku_json.get("pipe_materials", []),
                    sku_id=sku_id,
                )
                state_machine.save_module_output("M4", video_links)
                sku_logger.log_completed("M4")
                state_machine.transition_to("ASSEMBLED")
            except Exception as e:
                sku_logger.log_failure("M4", str(e), retryable=True)
                state_machine.fail()
                raise
        else:
            video_links = state_machine.load_module_output("M4") or {}
            log.info("[{}] M4 already complete, skipping", sku_id)

        # ── Step 5: Assembly + Validation ──────────────────────
        if state_machine.state == "ASSEMBLED":
            sku_logger.log_started("assembly")
            try:
                master = self._build_master(
                    sku_id=sku_id,
                    sku_json=sku_json,
                    seo_keywords=seo_keywords,
                    feature_blocks=feature_blocks,
                    amazon_listing_blocks=amazon_listing_blocks,
                    blog_structure=blog_structure,
                    video_links=video_links,
                )

                # Validate the assembled master
                validation_passed, validation_errors = validate_assembly(master)
                if not validation_passed:
                    sku_logger.log_failure(
                        "assembly",
                        f"Validation failed: {'; '.join(validation_errors)}",
                        retryable=False,
                    )
                    raise ValueError(f"Assembly validation failed: {'; '.join(validation_errors)}")

                # Write outputs
                output_paths = state_machine.get_output_paths()
                with open(output_paths["master"], "w") as f:
                    json.dump(master, f, indent=2, ensure_ascii=False, default=str)
                with open(output_paths["blog_structure"], "w") as f:
                    json.dump(blog_structure, f, indent=2, ensure_ascii=False, default=str)
                with open(output_paths["amazon_listing"], "w") as f:
                    json.dump(amazon_listing_blocks, f, indent=2, ensure_ascii=False, default=str)

                sku_logger.log_completed("assembly")
                log.info("[{}] Master.json written to {}", sku_id, output_paths["master"])
            except Exception as e:
                sku_logger.log_failure("assembly", str(e), retryable=False)
                state_machine.fail()
                raise
        else:
            # Load from disk if already assembled
            output_paths = state_machine.get_output_paths()
            if output_paths["master"].exists():
                with open(output_paths["master"]) as f:
                    master = json.load(f)
                log.info("[{}] Already assembled, loading from {}", sku_id, output_paths["master"])
            else:
                raise RuntimeError(f"[{sku_id}] In state {state_machine.state} but no master.json found")

        return master

    def _normalize_sku(
        self,
        sku_id: str,
        csv_row: dict[str, str],
        specs_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Normalize raw SKU data into canonical SKU JSON.

        Args:
            sku_id: SKU identifier.
            csv_row: Row from SKU manifest CSV.
            specs_data: Feature/spec data from JSON.

        Returns:
            Validated canonical SKU dict.
        """
        normalized = {
            "sku_id": sku_id,
            "product_name": csv_row.get("product_name", ""),
            "brand": csv_row.get("brand", "KF CPTEC"),
            "category": csv_row.get("category", ""),
            "tool_type": csv_row.get("tool_type", ""),
            "pipe_materials": csv_row.get("pipe_materials", "").split(";") if csv_row.get("pipe_materials") else [],
            "specs": specs_data.get("specs", []),
            "bundle_contents": specs_data.get("bundle_contents", []),
            "certifications": specs_data.get("certifications", []),
            "variants": specs_data.get("variants", []),
            "upc": csv_row.get("upc"),
            "weight_lbs": float(csv_row["weight_lbs"]) if csv_row.get("weight_lbs") else None,
            "dimensions": csv_row.get("dimensions"),
            "warranty": csv_row.get("warranty"),
            "price_msrp": float(csv_row["price_msrp"]) if csv_row.get("price_msrp") else None,
            "color": csv_row.get("color"),
            "material": csv_row.get("material"),
        }
        # Remove None keys
        normalized = {k: v for k, v in normalized.items() if v is not None and v != "" and v != []}
        # Validate against schema
        validated = SKUCanonical(**normalized)
        return validated.model_dump()

    def run_batch(
        self,
        sku_manifest: list[dict[str, str]],
        keyword_csv: str,
        specs_dict: dict[str, dict[str, Any]],
        callback: Optional[Callable[[str, dict[str, Any], Optional[str]], None]] = None,
    ) -> dict[str, dict[str, Any]]:
        """Run the pipeline for multiple SKUs in parallel.

        Args:
            sku_manifest: List of SKU manifest rows (from CSV).
            keyword_csv: Keyword table as CSV string.
            specs_dict: Dict mapping sku_id (or key) to spec JSON data.
            callback: Optional callback (sku_id, result or None, error or None).

        Returns:
            Dict mapping sku_id to master.json result.
        """
        results: dict[str, dict[str, Any]] = {}
        failures: dict[str, str] = {}

        log.info("Starting batch pipeline with {} workers", self.max_workers)

        def _run_one(sku_row: dict[str, str]) -> tuple[str, Optional[dict[str, Any]], Optional[str]]:
            sku_id = sku_row.get("sku_id", "")
            sku_key = sku_row.get("sku_key", sku_id)
            try:
                specs = specs_dict.get(sku_key, specs_dict.get(sku_id, {}))
                master = self.process_single_sku(sku_id, sku_row, keyword_csv, specs)
                return sku_id, master, None
            except Exception as e:
                log.error("[{}] Pipeline failed: {}", sku_id, e)
                return sku_id, None, str(e)

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(_run_one, row): row for row in sku_manifest}
            for future in as_completed(futures):
                sku_id, result, error = future.result()
                if error:
                    failures[sku_id] = error
                    if callback:
                        callback(sku_id, None, error)
                else:
                    results[sku_id] = result
                    if callback:
                        callback(sku_id, result, None)

        failed_ct = len(failures)
        success_ct = len(results)
        log.info(
            "Batch complete: {} succeeded, {} failed out of {}",
            success_ct, failed_ct, len(sku_manifest),
        )
        if failures:
            log.warning("Failed SKUs: {}", failures)

        return results
