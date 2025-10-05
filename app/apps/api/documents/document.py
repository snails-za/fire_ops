import os
import uuid
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Query
from tortoise.contrib.pydantic import pydantic_model_creator
from tortoise.expressions import Q

from apps.models.document import Document, DocumentChunk
from apps.utils import response
from apps.utils.celery_utils import celery_task_manager
from apps.utils.rag_helper import vector_search
from celery_tasks.task import *
from config import DOCUMENT_STORE_PATH

router = APIRouter(prefix="/documents", tags=["文档管理"])

# 创建Pydantic模型
Document_Pydantic = pydantic_model_creator(Document, name="Document")
DocumentChunk_Pydantic = pydantic_model_creator(DocumentChunk, name="DocumentChunk", exclude=("id",))


@router.post("/upload", summary="上传文档(匿名)", description="上传文档并自动解析向量化（无需登录）")
async def upload_document(
        file: UploadFile = File(...),
):
    """上传文档"""
    try:
        # 检查文件类型
        allowed_types = ['pdf', 'docx', 'doc', 'xlsx', 'xls', 'txt', 'md']
        file_extension = file.filename.split('.')[-1].lower()

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
            status="queued"  # 初始状态为排队中
        )

        # 使用Celery异步处理文档（非阻塞）
        task = process_document_task.delay(
            document.id,
            file_path,
            file_extension
        )

        # 保存任务ID到文档记录中，用于状态查询
        document.task_id = task.id
        await document.save()

        data = await Document_Pydantic.from_tortoise_orm(document)

        # 根据文件类型提供不同的处理提示
        if file_extension == 'pdf':
            message = "PDF文档上传成功！系统将自动识别文本内容，如果是扫描件将使用OCR技术处理..."
        else:
            message = "文档上传成功，正在处理中..."

        return response(data=data.model_dump(), message=message)

    except Exception as e:
        traceback.print_exc()
        return response(code=500, message=f"上传失败: {str(e)}")


@router.get("/list", summary="文档列表(匿名)", description="获取文档列表（无需登录）")
async def get_documents(
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(10, ge=1, le=100, description="每页数量"),
        status: Optional[str] = Query(None, description="文档状态"),
):
    """获取文档列表"""
    try:
        conditions = []
        if status:
            conditions.append(Q(status=status))

        query = Document.filter(*conditions).order_by("-upload_time")
        total = await query.count()

        documents = await query.offset((page - 1) * page_size).limit(page_size)

        data = []
        for doc in documents:
            doc_data = await Document_Pydantic.from_tortoise_orm(doc)
            data.append(doc_data.model_dump())

        return response(data={
            "documents": data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        })

    except Exception as e:
        return response(code=500, message=f"获取文档列表失败: {str(e)}")


@router.get("/{document_id}", summary="获取文档详情(匿名)", description="获取文档详细信息（无需登录）")
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

        return response(data={
            "document": doc_data.model_dump(),
            "chunks_count": chunks
        })

    except Exception as e:
        return response(code=500, message=f"获取文档详情失败: {str(e)}")


@router.get("/{document_id}/chunks", summary="获取文档分块(匿名)", description="获取文档的分块信息（无需登录）")
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

        return response(data={
            "chunks": data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        })

    except Exception as e:
        return response(code=500, message=f"获取文档分块失败: {str(e)}")


@router.delete("/{document_id}", summary="删除文档(匿名)", description="删除文档及其相关数据（无需登录）")
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


@router.post("/{document_id}/reprocess", summary="重新处理文档(匿名)", description="重新处理文档向量化（无需登录）")
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
        await document.save()

        # 使用Celery重新处理文档
        task = process_document_task.delay(
            document.id,
            document.file_path,
            document.file_type
        )

        # 保存新的任务ID
        document.task_id = task.id
        await document.save()

        return response(message="文档重新处理已开始")

    except Exception as e:
        return response(code=500, message=f"重新处理文档失败: {str(e)}")


@router.get("/stats/overview", summary="文档统计(匿名)", description="获取文档处理统计信息（无需登录）")
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

        return response(data={
            "documents": {
                "total": total_documents,
                "queued": queued_documents,
                "processing": processing_documents,
                "completed": completed_documents,
                "failed": failed_documents
            },
            "chunks": {
                "total": total_chunks
            },
            "vectors": {
                "total": total_vectors
            }
        })

    except Exception as e:
        return response(code=500, message=f"获取统计信息失败: {str(e)}")


@router.get("/{document_id}/download", summary="下载文档(匿名)", description="下载原始文档文件（无需登录）")
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
        safe_filename = urllib.parse.quote(document.original_filename, safe='')
        
        # 返回文件下载响应（强制下载）
        return FileResponse(
            path=document.file_path,
            filename=document.original_filename,
            media_type='application/octet-stream',
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{safe_filename}",
                "Cache-Control": "no-cache"
            }
        )

    except Exception as e:
        return response(code=500, message=f"下载文档失败: {str(e)}")


@router.get("/{document_id}/preview", summary="预览文档(匿名)", description="在浏览器中预览文档内容（无需登录）")
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
        safe_filename = urllib.parse.quote(document.original_filename, safe='')
        
        # 返回文件预览响应（在浏览器中直接显示）
        return FileResponse(
            path=document.file_path,
            filename=document.original_filename,
            media_type='application/pdf',
            headers={
                "Content-Disposition": f"inline; filename*=UTF-8''{safe_filename}",
                "Cache-Control": "no-cache"
            }
        )

    except Exception as e:
        return response(code=500, message=f"预览文档失败: {str(e)}")


@router.get("/{document_id}/view", summary="查看文档内容(匿名)", description="查看文档内容并支持高亮显示（无需登录）")
async def view_document_content(
        document_id: int,
        highlight: Optional[str] = Query(None, description="需要高亮的文本"),
        chunk_id: Optional[int] = Query(None, description="特定文档块ID")
):
    """查看文档内容"""
    try:
        document = await Document.get_or_none(id=document_id)
        if not document:
            return response(code=404, message="文档不存在")

        # 如果指定了chunk_id，返回特定块的内容
        if chunk_id:
            chunk = await DocumentChunk.get_or_none(id=chunk_id, document_id=document_id)
            if not chunk:
                return response(code=404, message="文档块不存在")

            content = chunk.content
            chunk_info = {
                "chunk_id": chunk.id,
                "chunk_index": chunk.chunk_index,
                "content_length": chunk.content_length
            }
        else:
            # 返回完整文档内容
            content = document.content
            chunk_info = None

        # 如果需要高亮，处理高亮文本
        highlighted_content = content
        if highlight and highlight.strip():
            import re

            # 分割多个关键词（支持空格分隔）
            keywords = [kw.strip() for kw in highlight.strip().split() if kw.strip()]

            # 对每个关键词进行高亮处理
            for keyword in keywords:
                if len(keyword) >= 1:  # 至少1个字符才高亮
                    # 使用正则表达式进行不区分大小写的高亮
                    pattern = re.compile(re.escape(keyword), re.IGNORECASE)
                    highlighted_content = pattern.sub(
                        lambda
                            m: f'<mark style="background-color: #ffeb3b; padding: 2px 4px; border-radius: 3px; font-weight: bold;">{m.group()}</mark>',
                        highlighted_content
                    )

        return response(data={
            "document": {
                "id": document.id,
                "filename": document.original_filename,
                "file_type": document.file_type,
                "upload_time": document.upload_time,
                "status": document.status
            },
            "content": content,
            "highlighted_content": highlighted_content,
            "highlight_text": highlight,
            "chunk_info": chunk_info,
            "has_highlight": bool(highlight and highlight.strip())
        })

    except Exception as e:
        return response(code=500, message=f"查看文档失败: {str(e)}")
