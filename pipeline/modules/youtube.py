"""M4 — YouTube Video Retrieval Module (RETRIEVAL ONLY).

Searches existing public YouTube videos for each how-to step.
NEVER generates, downloads, edits, or re-uploads video.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from loguru import logger as log
from pydantic import BaseModel, Field

from config import (
    YOUTUBE_API_KEY,
    YOUTUBE_BASE_URL,
    YT_CACHE_TTL_DAYS,
    YT_MAX_RESULTS,
    YT_SCORE_THRESHOLD,
)
from pipeline.schemas.video_schema import VideoLink, VideoLinks, VideoSlotMapping
from pipeline.utils.http_client import APIClient
from pipeline.utils.retry import api_retry_decorator


# ── Fallback query synonyms per step_intent ────────────────────
STEP_INTENT_SYNONYMS: dict[str, list[tuple[str, str]]] = {
    "overview": [
        ("how to use", ""),
        ("tutorial", ""),
        ("complete guide", ""),
    ],
    "prep": [
        ("cut pipe", "preparation"),
        ("measure and cut", "pipe prep"),
        ("deburr pipe", "clean pipe"),
    ],
    "position": [
        ("install ring", "position fitting"),
        ("place ring", "align fitting"),
        ("insert pipe", "assembly"),
    ],
    "crimp": [
        ("crimp connection", "press tool"),
        ("crimp ring", "use crimper"),
        ("make connection", "crimp pipe"),
    ],
    "inspect": [
        ("go no-go gauge", "check crimp"),
        ("verify connection", "inspect crimp"),
        ("test joint", "leak test"),
    ],
    "troubleshoot": [
        ("fix leak", "repair"),
        ("crimp problems", "troubleshooting"),
        ("common mistakes", "tips"),
    ],
}


class YouTubeVideo(BaseModel):
    """YouTube video data from API response."""
    video_id: str
    title: str = Field(default="")
    description: str = Field(default="")
    channel_title: str = Field(default="")
    published_at: str = Field(default="")
    view_count: int = Field(default=0)
    like_count: int = Field(default=0)
    comment_count: int = Field(default=0)
    duration_seconds: int = Field(default=0)
    embeddable: bool = Field(default=True)


class YouTubeModule:
    """M4 Video Retrieval module using YouTube Data API v3."""

    def __init__(self) -> None:
        if not YOUTUBE_API_KEY:
            raise ValueError("YOUTUBE_API_KEY is not set")
        self.client = APIClient(
            base_url=YOUTUBE_BASE_URL,
            api_key=YOUTUBE_API_KEY,
            timeout=30.0,
        )
        self._cache_dir = Path("pipeline/output/_yt_cache")
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._cached: dict[str, list[dict[str, Any]]] = {}

    def _cache_key(self, query: str) -> str:
        import hashlib
        return hashlib.md5(query.lower().encode()).hexdigest()

    def _load_cache(self, key: str) -> Optional[list[dict[str, Any]]]:
        cache_file = self._cache_dir / f"{key}.json"
        if cache_file.exists():
            with open(cache_file) as f:
                data = json.load(f)
            cached_at = data.get("cached_at", 0)
            age_days = (time.time() - cached_at) / 86400
            if age_days <= YT_CACHE_TTL_DAYS:
                log.debug("[M4] Cache hit for query key {}", key)
                return data.get("results")
        return None

    def _save_cache(self, key: str, results: list[dict[str, Any]]) -> None:
        cache_file = self._cache_dir / f"{key}.json"
        with open(cache_file, "w") as f:
            json.dump({
                "cached_at": time.time(),
                "results": results,
            }, f, ensure_ascii=False)

    def _parse_duration(self, duration_iso: str) -> int:
        """Parse ISO 8601 duration like PT4M23S to seconds."""
        match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration_iso)
        if not match:
            return 0
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        return hours * 3600 + minutes * 60 + seconds

    @api_retry_decorator()
    def search_videos(
        self,
        query: str,
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """Search YouTube for existing embeddable videos.

        Args:
            query: Search query string.
            max_results: Max results to return.

        Returns:
            List of video result dicts.
        """
        cache_key = self._cache_key(query)
        cached = self._load_cache(cache_key)
        if cached:
            return cached

        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "videoEmbeddable": "true",
            "relevanceLanguage": "en",
            "maxResults": min(max_results, 50),
            "videoDuration": "medium",
            "key": YOUTUBE_API_KEY,
        }

        response = self.client.get_sync("/search", params=params)
        items = response.get("items", [])

        # Get detailed info (duration, stats) for each video
        video_ids = [item["id"]["videoId"] for item in items if "videoId" in item.get("id", {})]
        results = []

        if video_ids:
            video_params = {
                "part": "contentDetails,statistics",
                "id": ",".join(video_ids),
                "key": YOUTUBE_API_KEY,
            }
            video_response = self.client.get_sync("/videos", params=video_params)
            video_details = {
                v["id"]: v for v in video_response.get("items", [])
            }
            for item in items:
                vid = item["id"]["videoId"]
                snippet = item["snippet"]
                details = video_details.get(vid, {})
                content_details = details.get("contentDetails", {})
                statistics = details.get("statistics", {})

                duration_sec = self._parse_duration(
                    content_details.get("duration", "PT0S")
                )

                results.append({
                    "video_id": vid,
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", ""),
                    "channel_title": snippet.get("channelTitle", ""),
                    "published_at": snippet.get("publishedAt", ""),
                    "view_count": int(statistics.get("viewCount", 0)),
                    "like_count": int(statistics.get("likeCount", 0)),
                    "comment_count": int(statistics.get("commentCount", 0)),
                    "duration_seconds": duration_sec,
                    "embeddable": True,
                })

        self._save_cache(cache_key, results)
        return results

    def _compute_match_score(
        self,
        video: dict[str, Any],
        step_intent: str,
        step_keywords: list[str],
    ) -> float:
        """Compute relevance score for a video against a step intent.

        Scoring:
        - keyword_match (title+description vs step_keywords): 0.40
        - normalized_view_count: 0.20
        - like_ratio: 0.15
        - recency_decay (half_life=3yr): 0.10
        - channel_trust: 0.15
        """
        title = video.get("title", "").lower()
        desc = video.get("description", "").lower()
        combined_text = f"{title} {desc}"

        # 1. Keyword match (0-1)
        kw_matches = sum(1 for kw in step_keywords if kw.lower() in combined_text)
        kw_score = min(kw_matches / max(len(step_keywords), 1), 1.0)

        # 2. View count normalization (log scale)
        views = video.get("view_count", 0)
        view_score = min((views ** 0.3) / 100.0, 1.0)

        # 3. Like ratio
        likes = video.get("like_count", 0)
        view_count = max(views, 1)
        like_ratio = min(likes / view_count * 100, 1.0)  # cap at 100%

        # 4. Recency decay
        published = video.get("published_at", "")
        try:
            pub_time = datetime.fromisoformat(published.replace("Z", "+00:00"))
            age_years = (datetime.now(timezone.utc) - pub_time).days / 365.25
            recency_score = 2 ** (-age_years / 3.0)  # half-life = 3 years
        except Exception:
            recency_score = 0.5

        # 5. Channel trust — basic heuristic (prefer educational channels)
        channel = video.get("channel_title", "").lower()
        trust_bonus = 0.15 if any(
            word in channel for word in ["tool", "howto", "diy", "repair", "plumbing", "educational"]
        ) else 0.0

        score = (
            0.40 * kw_score
            + 0.20 * view_score
            + 0.15 * like_ratio
            + 0.10 * recency_score
            + 0.15 * trust_bonus
        )
        return min(score, 1.0)

    def match_step_to_video(
        self,
        step_intent: str,
        step_keywords: list[str],
        tool_type: str,
        pipe_material: str,
    ) -> tuple[Optional[dict[str, Any]], float, list[str]]:
        """Find the best video match for a single step.

        Returns:
            Tuple of (best_video_dict or None, score, fallback_chain_used).
        """
        fallback_chain: list[str] = []
        query = f"{tool_type} {step_intent} {pipe_material}"

        # Try primary query
        results = self.search_videos(query, YT_MAX_RESULTS)
        fallback_chain.append(f"primary:{query}")

        if not results:
            # Try synonym fallback
            synonyms = STEP_INTENT_SYNONYMS.get(step_intent, [])
            for synonym_action, synonym_subject in synonyms:
                syn_query = f"{tool_type} {synonym_action} {pipe_material} {synonym_subject}".strip()
                results = self.search_videos(syn_query, YT_MAX_RESULTS)
                fallback_chain.append(f"synonym:{syn_query}")
                if results:
                    break

        if not results:
            # Try relaxed filter (remove duration constraint)
            relaxed_query = f"{tool_type} {step_intent}"
            results = self.search_videos(relaxed_query, YT_MAX_RESULTS)
            fallback_chain.append(f"relaxed:{relaxed_query}")

        # Score candidates
        scored = []
        for video in results:
            # Duration sanity check: >= 60 seconds
            if video.get("duration_seconds", 0) < 60:
                continue
            score = self._compute_match_score(video, step_intent, step_keywords + [tool_type])
            scored.append((score, video))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        if not scored:
            return None, 0.0, fallback_chain

        best_score, best_video = scored[0]

        if best_score >= YT_SCORE_THRESHOLD:
            return best_video, best_score, fallback_chain

        return None, best_score, fallback_chain

    def run(
        self,
        sections: list[dict[str, Any]],
        keyword_clusters: dict[str, Any],
        tool_type: str,
        pipe_materials: list[str],
        sku_id: str,
    ) -> dict[str, Any]:
        """Execute M4: match YouTube videos to blog structure steps.

        Args:
            sections: Blog structure sections from M3.
            keyword_clusters: SEO keywords from M1 (for section keyword lookups).
            tool_type: Tool type string (e.g. "PEX Crimp Tool").
            pipe_materials: List of pipe materials.
            sku_id: SKU ID for dedup tracking.

        Returns:
            Validated VideoLinks dict.
        """
        log.info("[M4] Starting YouTube video retrieval...")

        pipe_material = pipe_materials[0] if pipe_materials else "pipe"
        used_video_ids: set[str] = set()
        mappings: list[VideoSlotMapping] = []
        total_slots = 0
        filled_slots = 0

        # Build a keyword lookup from clusters
        cluster_keyword_map: dict[str, list[str]] = {}
        for cluster in keyword_clusters.get("intent_clusters", []):
            cluster_keyword_map[cluster.get("cluster_name", "")] = cluster.get("keywords", [])

        for section in sections:
            step_intent = section.get("step_intent")
            if not step_intent or step_intent == "null" or step_intent == "":
                continue  # Only process how_to_step sections

            if section.get("section_type") != "how_to_step":
                continue

            total_slots += 1
            keywords = section.get("assigned_keywords", [])
            heading = section.get("heading_text", "unknown")

            video, score, fallback_chain = self.match_step_to_video(
                step_intent=step_intent,
                step_keywords=keywords,
                tool_type=tool_type,
                pipe_material=pipe_material,
            )

            slot_filled = False
            link: Optional[VideoLink] = None

            if video and video["video_id"] not in used_video_ids:
                used_video_ids.add(video["video_id"])
                embed_html = (
                    f'<iframe width="560" height="315" '
                    f'src="https://www.youtube.com/embed/{video["video_id"]}" '
                    f'frameborder="0" allowfullscreen></iframe>'
                )
                link = VideoLink(
                    video_id=video["video_id"],
                    url=f"https://www.youtube.com/watch?v={video['video_id']}",
                    channel=video.get("channel_title", ""),
                    matched_step=heading,
                    match_score=score,
                    embed_html=embed_html,
                    health_checked_at=datetime.now(timezone.utc).isoformat(),
                )
                slot_filled = True
                filled_slots += 1
                log.info("[M4] Matched {} -> {} (score={:.2f})", heading, video["video_id"], score)
            else:
                log.info("[M4] No match for {} (best score={:.2f})", heading, score)

            mapping = VideoSlotMapping(
                section_heading=heading,
                step_intent=step_intent,
                video=link.model_dump() if link else None,
                score=score,
                fallback_chain_used=fallback_chain,
                slot_filled=slot_filled,
            )
            mappings.append(mapping)

        result = VideoLinks(
            mappings=[m.model_dump() for m in mappings],
            total_slots=total_slots,
            filled_slots=filled_slots,
        )
        log.info(
            "[M4] YouTube complete: {}/{} slots filled",
            result.filled_slots, result.total_slots,
        )
        return result.model_dump()
