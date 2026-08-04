"""
meeting_search.py — Full-Text Meeting Search Engine

Performs full-text keyword search across saved JSON meeting summaries in output directory.
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def search_past_meetings(output_dir: Path, query: str) -> List[Dict[str, Any]]:
    """
    Search saved meeting summaries in output_dir for query keyword.
    Returns list of matching result summary cards with match score.
    """
    if not query or not query.strip():
        return []

    q = query.lower().strip()
    results = []

    if not output_dir.exists():
        return []

    for path in output_dir.glob("*.json"):
        try:
            content = path.read_text(encoding="utf-8")
            data = json.loads(content)

            filename = data.get("filename", "")
            full_text = data.get("transcript", {}).get("full_text", "")
            action_items = data.get("action_items", [])
            decisions = data.get("decisions", [])

            # Compute simple term match relevance
            matches = 0
            matches += full_text.lower().count(q) * 1
            matches += filename.lower().count(q) * 5

            for ai in action_items:
                if q in ai.get("description", "").lower() or q in (ai.get("owner") or "").lower():
                    matches += 3

            for d in decisions:
                if q in d.get("description", "").lower():
                    matches += 3

            if matches > 0:
                results.append({
                    "id": data.get("id"),
                    "filename": filename,
                    "created_at": data.get("created_at"),
                    "match_score": matches,
                    "action_items_count": len(action_items),
                    "decisions_count": len(decisions),
                })
        except Exception as exc:
            logger.warning(f"Error reading {path} during search: {exc}")

    # Sort results by match score descending
    results.sort(key=lambda r: r["match_score"], reverse=True)
    return results
