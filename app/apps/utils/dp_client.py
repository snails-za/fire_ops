"""Document Process（DP）HTTP 客户端：提交解析并取回 markdown + 页级切分。"""

from __future__ import annotations

import mimetypes
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from config import (
    DP_API_KEY,
    DP_BASE_URL,
    DP_DEFAULT_BACKEND,
    DP_POLL_SECONDS,
    DP_TIMEOUT_SECONDS,
)


class DPClientError(RuntimeError):
    """调用 DP 失败。"""


@dataclass
class DPChunk:
    """DP 侧已切分好的一块内容（默认按页；超长页可再切）。"""

    content: str
    page_no: int | None = None
    source: str = "page"  # page | page_split | markdown_fallback


@dataclass
class DPParseResult:
    markdown: str
    chunks: list[DPChunk] = field(default_factory=list)
    dp_document_id: str | None = None
    page_count: int | None = None
    engine: str | None = None


class DPClient:
    # 单页过长时再按字符切，避免向量块过大；优先保留 DP 页边界
    MAX_CHUNK_CHARS = 3000
    CHUNK_OVERLAP = 200

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        backend: str | None = None,
        poll_seconds: float | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.base_url = (base_url or DP_BASE_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else DP_API_KEY
        self.backend = backend or DP_DEFAULT_BACKEND
        self.poll_seconds = (
            poll_seconds if poll_seconds is not None else DP_POLL_SECONDS
        )
        self.timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else DP_TIMEOUT_SECONDS
        )
        headers = {"X-API-Key": self.api_key} if self.api_key else {}
        self._client = httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=httpx.Timeout(60.0, connect=10.0),
        )

    def close(self) -> None:
        self._client.close()

    def parse_file(self, file_path: str, *, filename: str | None = None) -> DPParseResult:
        """上传文件到 DP，等待成功后返回全文 markdown + 页级切分块。"""
        path = Path(file_path)
        if not path.is_file():
            raise DPClientError(f"文件不存在：{file_path}")

        name = filename or path.name
        content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
        with path.open("rb") as source:
            response = self._client.post(
                "/v1/documents",
                data={"backend": self.backend},
                files={"file": (name, source, content_type)},
            )
        payload = self._envelope(response, expect_ok_statuses={200, 202})
        data = payload.get("data") or {}
        document_id = data.get("id")
        if not document_id:
            raise DPClientError(f"DP 未返回任务 id：{payload}")

        print(f"📄 已提交 DP 任务 document_id={document_id} backend={self.backend}")
        status = self._wait_succeeded(str(document_id))
        print(
            f"✅ DP 解析完成 document_id={document_id} "
            f"pages={status.get('page_count')} engine={status.get('engine')}"
        )
        result = self._fetch_result(str(document_id))
        return self._to_parse_result(
            result,
            dp_document_id=str(document_id),
            page_count=status.get("page_count"),
            engine=status.get("engine"),
        )

    def _wait_succeeded(self, document_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            response = self._client.get(f"/v1/documents/{document_id}")
            payload = self._envelope(response)
            data = payload.get("data") or {}
            status = str(data.get("status") or "")
            if status == "succeeded":
                return data
            if status == "failed":
                raise DPClientError(
                    f"DP 解析失败：{data.get('error') or 'unknown error'}"
                )
            if status in {"delete_requested", "retry_requested"}:
                raise DPClientError(f"DP 任务已中断：{status}")
            time.sleep(self.poll_seconds)
        raise DPClientError(
            f"等待 DP 解析超时（{self.timeout_seconds}s）document_id={document_id}"
        )

    def _fetch_result(self, document_id: str) -> dict[str, Any]:
        response = self._client.get(f"/v1/documents/{document_id}/result")
        payload = self._envelope(response)
        data = payload.get("data")
        if not isinstance(data, dict):
            raise DPClientError("DP 返回的 result 无效")
        return data

    def list_pages(self, document_id: str) -> dict[str, Any]:
        """获取 DP 文档页列表（含 page_count）。"""
        response = self._client.get(f"/v1/documents/{document_id}/pages")
        payload = self._envelope(response)
        data = payload.get("data")
        if not isinstance(data, dict):
            raise DPClientError("DP 返回的 pages 无效")
        return data

    def get_page_image(self, document_id: str, page_no: int) -> tuple[bytes, str]:
        """拉取单页渲染图，返回 (bytes, media_type)。"""
        response = self._client.get(
            f"/v1/documents/{document_id}/pages/{page_no}/image"
        )
        if response.status_code != 200:
            try:
                body = response.json()
                message = body.get("message") if isinstance(body, dict) else None
            except Exception:
                message = response.text[:300]
            raise DPClientError(
                f"DP 页图失败 HTTP {response.status_code}：{message or 'unknown'}"
            )
        media_type = response.headers.get("content-type") or "image/png"
        return response.content, media_type.split(";")[0].strip()

    def _to_parse_result(
        self,
        result: dict[str, Any],
        *,
        dp_document_id: str | None,
        page_count: Any,
        engine: Any,
    ) -> DPParseResult:
        markdown = str(result.get("markdown") or "").strip()
        pages = result.get("pages") or []
        chunks: list[DPChunk] = []

        if isinstance(pages, list):
            for page in pages:
                if not isinstance(page, dict):
                    continue
                text = str(page.get("markdown") or "").strip()
                if not text:
                    continue
                page_no = page.get("page_no")
                try:
                    page_no_int = int(page_no) if page_no is not None else None
                except (TypeError, ValueError):
                    page_no_int = None
                chunks.extend(self._split_if_needed(text, page_no=page_no_int))

        # 无页结果时退回全文 markdown 再切
        if not chunks and markdown:
            chunks.extend(
                self._split_if_needed(markdown, page_no=None, source="markdown_fallback")
            )

        if not markdown and chunks:
            markdown = "\n\n".join(c.content for c in chunks)

        if not markdown.strip():
            raise DPClientError("DP 返回内容为空")

        return DPParseResult(
            markdown=markdown,
            chunks=chunks,
            dp_document_id=dp_document_id,
            page_count=int(page_count) if page_count is not None else None,
            engine=str(engine) if engine else None,
        )

    def _split_if_needed(
        self,
        text: str,
        *,
        page_no: int | None,
        source: str = "page",
    ) -> list[DPChunk]:
        text = text.strip()
        if not text:
            return []
        if len(text) <= self.MAX_CHUNK_CHARS:
            return [DPChunk(content=text, page_no=page_no, source=source)]

        parts: list[DPChunk] = []
        start = 0
        size = self.MAX_CHUNK_CHARS
        overlap = self.CHUNK_OVERLAP
        while start < len(text):
            end = min(start + size, len(text))
            piece = text[start:end].strip()
            if piece:
                parts.append(
                    DPChunk(
                        content=piece,
                        page_no=page_no,
                        source="page_split" if source == "page" else source,
                    )
                )
            if end >= len(text):
                break
            start = max(end - overlap, start + 1)
        return parts

    @staticmethod
    def _envelope(
        response: httpx.Response,
        *,
        expect_ok_statuses: set[int] | None = None,
    ) -> dict[str, Any]:
        expect_ok_statuses = expect_ok_statuses or {200}
        try:
            body = response.json()
        except Exception as exc:
            raise DPClientError(
                f"DP 响应不是 JSON：HTTP {response.status_code} {response.text[:300]}"
            ) from exc
        if response.status_code not in expect_ok_statuses:
            message = body.get("message") if isinstance(body, dict) else response.text
            raise DPClientError(f"DP HTTP {response.status_code}：{message}")
        if not isinstance(body, dict):
            raise DPClientError(f"DP 响应格式无效：{body!r}")
        if body.get("code") != 1:
            raise DPClientError(body.get("message") or "DP 业务失败")
        return body
