"""
文档处理器：解析全部交给 DP，fire_ops 只负责落库 + 向量化。

- Document.content：DP 全文 markdown（备份；预览走页图）
- Document.dp_document_id：DP 任务 ID（按页拉图，不存 bbox）
- DocumentChunk：DP 页级切分结果（RAG）
"""

import asyncio
import os
from datetime import datetime

from apps.models.document import Document as DocumentModel, DocumentChunk
from apps.utils.dp_client import DPClient, DPClientError, DPParseResult
from apps.utils.rag_helper import vector_search
from config import HF_HOME, HF_OFFLINE


class DocumentProcessor:
    """上传后：调用 DP 解析 → 写 document/document_chunk → 写入向量库。"""

    def __init__(self):
        try:
            os.environ["HF_HOME"] = HF_HOME
            os.environ["TRANSFORMERS_CACHE"] = HF_HOME
            os.environ["HF_HUB_CACHE"] = HF_HOME
            if HF_OFFLINE:
                os.environ["TRANSFORMERS_OFFLINE"] = "1"
                os.environ["HF_HUB_OFFLINE"] = "1"
        except Exception as e:
            raise Exception(f"DocumentProcessor初始化失败: {e}") from e

    async def process_document(
        self, document_id: int, file_path: str, file_type: str
    ) -> bool:
        document = None
        try:
            document = await DocumentModel.get(id=document_id)
            document.status = "processing"
            await document.save()

            if not os.path.exists(file_path):
                raise Exception(f"文件不存在: {file_path}")

            original_name = document.original_filename or document.filename
            print(f"🛰️ DP 解析 type={file_type} name={original_name}")

            client = DPClient()
            try:
                result: DPParseResult = await asyncio.to_thread(
                    client.parse_file,
                    file_path,
                    filename=original_name,
                )
            finally:
                client.close()

            content = (result.markdown or "").strip()
            chunk_specs = [
                {
                    "content": c.content,
                    "page_no": c.page_no,
                    "source": c.source,
                }
                for c in result.chunks
                if c.content and c.content.strip()
            ]
            if not content:
                raise Exception("DP 返回内容为空")
            if not chunk_specs:
                raise Exception("DP 未返回可用分块")

            print(
                f"📦 DP 切分块数={len(chunk_specs)} "
                f"pages={result.page_count} engine={result.engine}"
            )

            # 重新处理时先清旧分块，避免重复
            await DocumentChunk.filter(document_id=document_id).delete()
            await vector_search.delete_document(document_id)

            document.content = content
            document.dp_document_id = result.dp_document_id
            await document.save()

            chunk_objects = []
            chunk_texts = []
            for i, spec in enumerate(chunk_specs):
                chunk_text = spec["content"]
                meta = {
                    "chunk_index": i,
                    "source": spec.get("source") or "page",
                }
                if spec.get("page_no") is not None:
                    meta["page_no"] = spec["page_no"]
                chunk = await DocumentChunk.create(
                    document_id=document_id,
                    chunk_index=i,
                    content=chunk_text,
                    content_length=len(chunk_text),
                    metadata=meta,
                )
                chunk_objects.append(chunk)
                chunk_texts.append(chunk_text)

            await vector_search.add_documents_from_chunks(
                document_id=document_id,
                chunks=chunk_texts,
                chunk_objects=chunk_objects,
                metadata={
                    "filename": original_name,
                    "file_type": file_type,
                    "upload_time": document.upload_time.isoformat()
                    if document.upload_time
                    else None,
                    "dp_document_id": result.dp_document_id,
                },
            )

            document.status = "completed"
            document.process_time = datetime.now()
            await document.save()
            return True
        except DPClientError as e:
            return await self._fail(document, document_id, f"DP 解析失败：{e}")
        except Exception as e:
            return await self._fail(document, document_id, str(e))

    @staticmethod
    async def _fail(document, document_id: int, message: str) -> bool:
        if document is None:
            document = await DocumentModel.get(id=document_id)
        document.status = "failed"
        document.error_message = message
        await document.save()
        return False
