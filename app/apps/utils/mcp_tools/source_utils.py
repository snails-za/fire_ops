# -*- coding: utf-8 -*-
from typing import Any, Dict, List


def dedupe_sources(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按文档去重来源，避免同一文档多个 chunk 在附件区重复展示。"""
    seen: set[tuple[str, Any]] = set()
    deduped: List[Dict[str, Any]] = []
    for source in sources or []:
        document_id = source.get("document_id")
        if document_id is not None:
            key = ("document_id", document_id)
        else:
            key = (
                "filename",
                source.get("original_filename") or source.get("document_name"),
            )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(source)
    return deduped
