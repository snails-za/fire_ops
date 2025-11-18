import asyncio
import traceback

from tortoise import Tortoise

import config
from apps.utils.document_parser import DocumentProcessor
from celery_tasks.app import celery_

_document_processor = None

@celery_.task(bind=True, max_retries=3, default_retry_delay=60)
def process_document_task(self, document_id: int, file_path: str, file_type: str):
    """
    处理文档的Celery任务（使用现有的DocumentProcessor）

    Args:
        document_id: 文档ID
        file_path: 文件路径
        file_type: 文件类型

    Returns:
        dict: 处理结果
    """
    global _document_processor
    if _document_processor is None:
        _document_processor = DocumentProcessor()
    async def _process_document():
        # 初始化 Tortoise ORM 连接
        await Tortoise.init(config=config.TORTOISE_ORM)
        
        try:
            print(f"🔄 开始后台处理文档 {document_id} ({file_type})")
            
            # 更新任务状态
            self.update_state(
                state='PROGRESS',
                meta={
                    'status': '开始处理文档...',
                    'current': 0,
                    'total': 100,
                    'document_id': document_id
                }
            )

            # 调用现有的文档处理器
            success = await _document_processor.process_document(
                document_id,
                file_path,
                file_type
            )
            
            if success:
                print(f"✅ 文档 {document_id} 处理完成")
                # 返回可序列化的成功结果（不要手动置 SUCCESS，直接 return）
                return {
                    'status': '文档处理完成',
                    'current': 100,
                    'total': 100,
                    'document_id': document_id,
                    'result': 'success'
                }
            else:
                print(f"❌ 文档 {document_id} 处理失败")
                # 抛出异常让 Celery 正确标记为 FAILURE
                raise RuntimeError('文档处理失败')

        except Exception as e:
            traceback.print_exc()
            print(f"❌ 后台处理文档 {document_id} 时出错: {str(e)}")
            # 直接抛出异常，避免手动置 FAILURE 造成后端解码异常
            raise
        finally:
            # 关闭数据库连接
            await Tortoise.close_connections()
    
    # 运行异步任务
    try:
        return asyncio.run(_process_document())
    except Exception as e:
        print(f"❌ Celery任务执行失败: {str(e)}")
        # 抛出异常让 Celery 正确记录失败详情
        raise

