import os
import traceback
import uuid
import asyncio
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Query
from fastapi.responses import Response
from tortoise.contrib.pydantic import pydantic_model_creator
from tortoise.expressions import Q

from apps.models.document import Document, DocumentChunk
from apps.utils import response
from apps.utils.celery_utils import celery_task_manager
from apps.utils.dp_client import DPClient, DPClientError
from apps.utils.rag_helper import vector_search
from celery_tasks.task import process_document_task
from config import DOCUMENT_STORE_PATH, DP_VIEWER_PUBLIC_PATH

router = APIRouter(prefix="/documents", tags=["文档管理"])

# 创建Pydantic模型
Document_Pydantic = pydantic_model_creator(Document, name="Document")
DocumentChunk_Pydantic = pydantic_model_creator(
    DocumentChunk, name="DocumentChunk", exclude=("id",)
)


@router.post(
    "/upload",
    summary="上传文档(匿名)",
    description="上传文档并自动解析向量化（无需登录）",
)
async def upload_document(
    file: UploadFile = File(...),
):
    """上传文档"""
    try:
        # 与 DP 支持的格式对齐（解析由 DP 完成）
        allowed_types = [
            "pdf",
            "docx",
            "doc",
            "pptx",
            "ppt",
            "xlsx",
            "xls",
            "png",
            "jpg",
            "jpeg",
            "webp",
            "bmp",
            "tif",
            "tiff",
            "txt",
            "md",
        ]
        file_extension = file.filename.split(".")[-1].lower()

        if file_extension not in allowed_types:
            return response(code=400, message=f"不支持的文件类型: {file_extension}")

        # 生成唯一文件名
        unique_filename = f"{uuid.uuid4().hex}.{file_extension}"
        file_path = os.path.join(DOCUMENT_STORE_PATH, unique_filename)

        # 确保目录存在
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # 保存文件
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # 创建文档记录
        document = await Document.create(
            filename=unique_filename,
            original_filename=file.filename,
            file_path=file_path,
            file_size=len(content),
            file_type=file_extension,
            content="",  # 稍后处理
            status="queued",  # 初始状态为排队中
        )

        # 使用Celery异步处理文档（非阻塞）
        task = process_document_task.delay(document.id, file_path, file_extension)

        # 保存任务ID到文档记录中，用于状态查询
        document.task_id = task.id
        await document.save()

        data = await Document_Pydantic.from_tortoise_orm(document)
        return response(data=data.model_dump(), message="文档上传成功，已提交 DP 解析…")

    except Exception as e:
        traceback.print_exc()
        return response(code=500, message=f"上传失败: {str(e)}")


@router.get("/list", summary="文档列表(匿名)", description="获取文档列表（无需登录）")
async def get_documents(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="文档状态"),
    keyword: Optional[str] = Query(None, description="搜索关键字（文件名或内容）"),
):
    """获取文档列表"""
    try:
        conditions = []
        if status:
            conditions.append(Q(status=status))

        # 添加关键字搜索条件
        if keyword:
            # 搜索文件名
            conditions.append(Q(original_filename__icontains=keyword))

        query = Document.filter(*conditions).order_by("-upload_time")
        total = await query.count()

        documents = await query.offset((page - 1) * page_size).limit(page_size)

        data = []
        for doc in documents:
            doc_data = await Document_Pydantic.from_tortoise_orm(doc)
            payload = doc_data.model_dump()
            payload.pop("content", None)  # 列表不回传全文 markdown
            data.append(payload)

        total_page = (total + page_size - 1) // page_size

        return response(
            data=data, total=total, total_page=total_page, message="获取文档列表成功"
        )

    except Exception as e:
        return response(code=500, message=f"获取文档列表失败: {str(e)}")


@router.get(
    "/{document_id}",
    summary="获取文档详情(匿名)",
    description="获取文档详细信息（无需登录）",
)
async def get_document(
    document_id: int,
):
    """获取文档详情"""
    try:
        document = await Document.get_or_none(id=document_id)
        if not document:
            return response(code=404, message="文档不存在")

        doc_data = await Document_Pydantic.from_tortoise_orm(document)

        # 获取文档分块信息
        chunks = await DocumentChunk.filter(document_id=document_id).count()

        return response(
            data={"document": doc_data.model_dump(), "chunks_count": chunks}
        )

    except Exception as e:
        return response(code=500, message=f"获取文档详情失败: {str(e)}")


@router.get(
    "/{document_id}/chunks",
    summary="获取文档分块(匿名)",
    description="获取文档的分块信息（无需登录）",
)
async def get_document_chunks(
    document_id: int,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
):
    """获取文档分块"""
    try:
        document = await Document.get_or_none(id=document_id)
        if not document:
            return response(code=404, message="文档不存在")

        query = DocumentChunk.filter(document_id=document_id).order_by("chunk_index")
        total = await query.count()

        chunks = await query.offset((page - 1) * page_size).limit(page_size)

        data = []
        for chunk in chunks:
            chunk_data = await DocumentChunk_Pydantic.from_tortoise_orm(chunk)
            data.append(chunk_data.model_dump())

        total_page = (total + page_size - 1) // page_size

        return response(
            data=data, total=total, total_page=total_page, message="获取文档分块成功"
        )

    except Exception as e:
        return response(code=500, message=f"获取文档分块失败: {str(e)}")


@router.delete(
    "/{document_id}",
    summary="删除文档(匿名)",
    description="删除文档及其相关数据（无需登录）",
)
async def delete_document(
    document_id: int,
):
    """删除文档"""
    try:
        document = await Document.get_or_none(id=document_id)
        if not document:
            return response(code=404, message="文档不存在")

        # 如果有正在进行的Celery任务，先停止它
        if document.task_id:
            celery_task_manager.revoke_task(document.task_id, terminate=True)

        # 删除文件
        if os.path.exists(document.file_path):
            os.remove(document.file_path)

        # 删除相关数据（级联删除）
        # 先删除 Chroma 中对应向量
        await vector_search.delete_document(document_id)
        await document.delete()

        return response(message="文档删除成功")

    except Exception as e:
        return response(code=500, message=f"删除文档失败: {str(e)}")


@router.post(
    "/{document_id}/reprocess",
    summary="重新处理文档(匿名)",
    description="重新处理文档向量化（无需登录）",
)
async def reprocess_document(
    document_id: int,
):
    """重新处理文档"""
    try:
        document = await Document.get_or_none(id=document_id)
        if not document:
            return response(code=404, message="文档不存在")

        # 如果有正在进行的任务，先停止它
        if document.task_id:
            celery_task_manager.revoke_task(document.task_id, terminate=True)

        # 删除现有的分块与 Chroma 向量数据
        await DocumentChunk.filter(document_id=document_id).delete()
        await vector_search.delete_document(document_id)

        # 更新文档状态
        document.status = "queued"
        document.task_id = None
        document.process_time = None
        document.error_message = None
        document.dp_document_id = None
        await document.save()

        # 使用Celery重新处理文档
        task = process_document_task.delay(
            document.id, document.file_path, document.file_type
        )

        # 保存新的任务ID
        document.task_id = task.id
        await document.save()

        return response(message="文档重新处理已开始")

    except Exception as e:
        return response(code=500, message=f"重新处理文档失败: {str(e)}")


@router.get(
    "/stats/overview",
    summary="文档统计(匿名)",
    description="获取文档处理统计信息（无需登录）",
)
async def get_document_stats():
    """获取文档统计信息"""
    try:
        total_documents = await Document.all().count()
        queued_documents = await Document.filter(status="queued").count()
        processing_documents = await Document.filter(status="processing").count()
        completed_documents = await Document.filter(status="completed").count()
        failed_documents = await Document.filter(status="failed").count()

        total_chunks = await DocumentChunk.all().count()
        total_vectors = await vector_search.count_vectors()

        return response(
            data={
                "documents": {
                    "total": total_documents,
                    "queued": queued_documents,
                    "processing": processing_documents,
                    "completed": completed_documents,
                    "failed": failed_documents,
                },
                "chunks": {"total": total_chunks},
                "vectors": {"total": total_vectors},
            }
        )

    except Exception as e:
        return response(code=500, message=f"获取统计信息失败: {str(e)}")


@router.get(
    "/{document_id}/download",
    summary="下载文档(匿名)",
    description="下载原始文档文件（无需登录）",
)
async def download_document(document_id: int):
    """下载文档"""
    try:
        from fastapi.responses import FileResponse

        document = await Document.get_or_none(id=document_id)
        if not document:
            return response(code=404, message="文档不存在")

        if not os.path.exists(document.file_path):
            return response(code=404, message="文档文件不存在")

        # 处理文件名编码问题
        import urllib.parse

        safe_filename = urllib.parse.quote(document.original_filename, safe="")

        # 返回文件下载响应（强制下载）
        return FileResponse(
            path=document.file_path,
            filename=document.original_filename,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{safe_filename}",
                "Cache-Control": "no-cache",
            },
        )

    except Exception as e:
        return response(code=500, message=f"下载文档失败: {str(e)}")


@router.get(
    "/{document_id}/preview",
    summary="预览文档(匿名)",
    description="在浏览器中预览文档内容（无需登录）",
)
async def preview_document(document_id: int):
    """预览文档"""
    try:
        from fastapi.responses import FileResponse

        document = await Document.get_or_none(id=document_id)
        if not document:
            return response(code=404, message="文档不存在")

        if not os.path.exists(document.file_path):
            return response(code=404, message="文档文件不存在")

        # 处理文件名编码问题
        import urllib.parse

        safe_filename = urllib.parse.quote(document.original_filename, safe="")

        # 返回文件预览响应（在浏览器中直接显示）
        return FileResponse(
            path=document.file_path,
            filename=document.original_filename,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"inline; filename*=UTF-8''{safe_filename}",
                "Cache-Control": "no-cache",
            },
        )

    except Exception as e:
        return response(code=500, message=f"预览文档失败: {str(e)}")


@router.get(
    "/{document_id}/dp-preview",
    summary="DP 嵌入预览地址(匿名)",
    description="签发短时 embed token，返回 fire-admin 同源 /dp/ iframe 地址",
)
async def dp_preview(document_id: int):
    """返回可嵌入兰台文档工作区的 URL。"""
    try:
        document = await Document.get_or_none(id=document_id)
        if not document:
            return response(code=404, message="文档不存在")
        if document.status != "completed":
            return response(code=400, message="文档尚未解析完成，请稍后再预览")
        if not document.dp_document_id:
            return response(
                code=404,
                message="该文档尚无 DP 任务（请重新解析后再预览）",
            )

        client = DPClient()
        try:
            minted = await asyncio.to_thread(
                client.mint_embed_token,
                document.dp_document_id,
            )
        finally:
            client.close()

        token = str(minted.get("token") or "")
        dp_id = str(minted.get("document_id") or document.dp_document_id)
        if not token:
            return response(code=500, message="DP 未返回嵌入令牌")

        base = (DP_VIEWER_PUBLIC_PATH or "/dp").rstrip("/") or "/dp"
        embed_url = f"{base}/#/embed/documents/{dp_id}?token={token}"
        return response(
            data={
                "embed_url": embed_url,
                "dp_document_id": dp_id,
                "expires_at": minted.get("expires_at"),
            },
            message="已生成预览地址",
        )
    except DPClientError as e:
        return response(code=500, message=f"签发预览令牌失败: {e}")
    except Exception as e:
        traceback.print_exc()
        return response(code=500, message=f"获取预览地址失败: {str(e)}")


@router.get(
    "/{document_id}/pages",
    summary="文档页列表(匿名)",
    description="获取 DP 解析后的页列表，供页图预览",
)
async def list_document_pages(document_id: int):
    """页图预览：返回页码列表与代理图片 URL。"""
    try:
        document = await Document.get_or_none(id=document_id)
        if not document:
            return response(code=404, message="文档不存在")
        if not document.dp_document_id:
            return response(
                code=404,
                message="该文档尚无 DP 页图（请重新处理后再预览）",
            )

        client = DPClient()
        try:
            data = await asyncio.to_thread(client.list_pages, document.dp_document_id)
        finally:
            client.close()

        page_count = int(data.get("page_count") or 0)
        pages = []
        for item in data.get("pages") or []:
            if not isinstance(item, dict):
                continue
            page_no = item.get("page_no")
            if page_no is None:
                continue
            try:
                page_no = int(page_no)
            except (TypeError, ValueError):
                continue
            pages.append(
                {
                    "page_no": page_no,
                    "width": item.get("width"),
                    "height": item.get("height"),
                    "image_available": bool(item.get("image_available", True)),
                    "image_url": f"/api/v1/documents/{document_id}/pages/{page_no}/image",
                }
            )
        if not pages and page_count > 0:
            pages = [
                {
                    "page_no": n,
                    "width": None,
                    "height": None,
                    "image_available": True,
                    "image_url": f"/api/v1/documents/{document_id}/pages/{n}/image",
                }
                for n in range(1, page_count + 1)
            ]

        return response(
            data={
                "document_id": document_id,
                "dp_document_id": document.dp_document_id,
                "page_count": page_count or len(pages),
                "pages": pages,
            }
        )
    except DPClientError as e:
        return response(code=502, message=f"获取页列表失败: {e}")
    except Exception as e:
        return response(code=500, message=f"获取页列表失败: {str(e)}")


@router.get(
    "/{document_id}/pages/{page_no}/image",
    summary="文档页图(匿名)",
    description="代理返回 DP 渲染的页面图片",
)
async def get_document_page_image(document_id: int, page_no: int):
    """代理 DP 页图，浏览器可直接 <img src>。"""
    try:
        if page_no < 1:
            return response(code=400, message="页码无效")

        document = await Document.get_or_none(id=document_id)
        if not document:
            return response(code=404, message="文档不存在")
        if not document.dp_document_id:
            return response(code=404, message="该文档尚无 DP 页图")

        client = DPClient()
        try:
            content, media_type = await asyncio.to_thread(
                client.get_page_image, document.dp_document_id, page_no
            )
        finally:
            client.close()

        return Response(
            content=content,
            media_type=media_type,
            headers={"Cache-Control": "private, max-age=3600"},
        )
    except DPClientError as e:
        return response(code=502, message=f"获取页图失败: {e}")
    except Exception as e:
        return response(code=500, message=f"获取页图失败: {str(e)}")
