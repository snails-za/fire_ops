"""Document Process（DP）HTTP 客户端：提交解析任务并取回 Markdown。"""

from __future__ import annotations

import mimetypes
import time
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


class DPClient:
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

    def parse_file_to_markdown(self, file_path: str, *, filename: str | None = None) -> str:
        """上传本地文件到 DP，等待成功后返回 markdown 文本。"""
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
        return self._fetch_markdown(str(document_id))

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

    def _fetch_markdown(self, document_id: str) -> str:
        response = self._client.get(f"/v1/documents/{document_id}/markdown")
        payload = self._envelope(response)
        markdown = payload.get("data")
        if not isinstance(markdown, str) or not markdown.strip():
            raise DPClientError("DP 返回的 Markdown 为空")
        return markdown

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
