"""Reference Adapter implementation for Architecture Studio's SuggestionCatalogPort.

This adapter satisfies the hexagonal SuggestionCatalogPort interface of Architecture Studio:
- Receives detected architectural issues (e.g. SPOF, LATENCY_RISK).
- Resolves matching resilience and integration patterns from Knowledge Hub.
- Returns suggestions with typed ExternalRefs (e.g. 'KH:PAT-006@v1.0.0').
- Pure read-only operation: NEVER performs writes to project models or requirement registries.
"""

import json
from pathlib import Path
from typing import Any

from mcp_server.core.envelope import ok_response
from mcp_server.knowledge.tools import list_assets, search_assets


class SuggestionCatalogAdapter:
    """Hexagonal adapter bridging Architecture Studio to Knowledge Hub patterns."""

    def __init__(self, snapshot_path: Path | str | None = None) -> None:
        self.snapshot_path = Path(snapshot_path or "fixtures/sealed_snapshot.json")

    def get_suggestions(
        self,
        issue_kind: str,
        domain: str = "",
        context_tags: list[str] | None = None,
        limit: int = 5,
        prefer_offline: bool = True,
    ) -> dict[str, Any]:
        """Resolves pattern suggestions for a detected issue context.

        Args:
            issue_kind: Category of detected issue (e.g. 'SPOF', 'LATENCY_RISK', 'SECURITY_ISOLATION').
            domain: Target architectural domain (e.g. 'MCX', 'CORE', 'RADIO', 'STORAGE').
            context_tags: Optional list of architectural keywords.
            limit: Maximum number of suggestions to return.
            prefer_offline: If True, uses the sealed snapshot file for sub-millisecond local resolution.

        Returns:
            Standard response envelope matching schemas/suggestion_catalog.schema.json.
        """
        tags = context_tags or []
        query_terms = [issue_kind]
        if domain:
            query_terms.append(domain)
        query_terms.extend(tags)

        suggestions: list[dict[str, Any]] = []

        # 1. Offline Snapshot Resolution (Default & Fast)
        if prefer_offline and self.snapshot_path.exists():
            try:
                snapshot_data = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
                assets = snapshot_data.get("assets", [])

                for asset in assets:
                    # Match pattern, decision, or principle assets
                    typed_id = asset.get("typed_id", "")
                    title = asset.get("title", "")
                    summary = asset.get("summary", "")
                    body = asset.get("body", "")

                    # Score relevance
                    matches = 0
                    if issue_kind.lower() in title.lower() or issue_kind.lower() in summary.lower() or issue_kind.lower() in body.lower():
                        matches += 2
                    if domain and (domain.lower() in title.lower() or domain.lower() in summary.lower() or domain.lower() in str(asset.get("domain", "")).lower()):
                        matches += 2
                    for tag in tags:
                        if tag.lower() in title.lower() or tag.lower() in summary.lower():
                            matches += 1

                    # If issue_kind is SPOF, match active-active / resilience / backup / redundancy patterns
                    if issue_kind.upper() == "SPOF" and any(k in (title + summary + body).lower() for k in ["active-active", "failover", "redundancy", "backup", "resilience", "isolation"]):
                        matches += 3

                    if matches > 0:
                        suggestions.append({
                            "pattern_id": asset.get("id"),
                            "typed_id": typed_id or f"asset:{asset.get('id')}",
                            "title": title,
                            "summary": summary or title,
                            "applicability": f"Recommended for {issue_kind} in domain {domain or 'General'}",
                            "confidence": asset.get("confidence", "designed"),
                            "external_ref": f"KH:{asset.get('id')}@v{asset.get('version', '1.0.0')}",
                            "trade_offs": ["Requires architectural review before baseline promotion"],
                        })

                    if len(suggestions) >= limit:
                        break
            except Exception:
                suggestions = []

        # 2. Online Graph Database Fallback (if offline yielded no results)
        if not suggestions:
            search_res = search_assets(query=issue_kind)
            if search_res.get("status") == "ok":
                for item in search_res.get("data", [])[:limit]:
                    doc_id = item.get("id", "")
                    suggestions.append({
                        "pattern_id": doc_id,
                        "typed_id": f"pattern:{doc_id}" if doc_id.startswith("PAT") else f"asset:{doc_id}",
                        "title": item.get("title", doc_id),
                        "summary": item.get("title", doc_id),
                        "applicability": f"Suggested for {issue_kind}",
                        "confidence": item.get("confidence", "designed"),
                        "external_ref": f"KH:{doc_id}@v1.0.0",
                        "trade_offs": ["Requires local project qualification"],
                    })

        # 3. Default fallback to top active patterns if still empty
        if not suggestions:
            list_res = list_assets(status="active")
            for item in list_res.get("data", [])[:limit]:
                doc_id = item.get("id", "")
                suggestions.append({
                    "pattern_id": doc_id,
                    "typed_id": f"pattern:{doc_id}" if doc_id.startswith("PAT") else f"asset:{doc_id}",
                    "title": item.get("title", doc_id),
                    "summary": item.get("title", doc_id),
                    "applicability": "General reference pattern",
                    "confidence": item.get("confidence", "designed"),
                    "external_ref": f"KH:{doc_id}@v1.0.0",
                    "trade_offs": [],
                })

        return ok_response({
            "context": {
                "issue_kind": issue_kind,
                "domain": domain,
                "context_tags": tags,
            },
            "suggestions": suggestions[:limit],
        }, count=len(suggestions[:limit]))
