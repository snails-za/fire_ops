"""
Celery任务定义

文档处理相关的任务
"""

from apps.celery_tasks.app import celery_
from apps.utils.document_parser import document_processor


@celery_.task(bind=True, max_retries=3, default_retry_delay=60)
def process_document_task(self, document_id: int, file_path: str, file_type: str):
    """
    处理文档的Celery任务
    
    Args:
        document_id: 文档ID
        file_path: 文件路径
        file_type: 文件类型
        
    Returns:
        dict: 处理结果
    """
    try:
        print(f"🔄 Celery开始处理文档 {document_id} ({file_type})")
        
        # 更新任务状态为开始处理
        self.update_state(
            state='PROGRESS',
            meta={
                'status': '开始处理文档...',
                'current': 0,
                'total': 100,
                'document_id': document_id
            }
        )
        
        # 调用文档处理方法
        result = document_processor.process_document(document_id, file_path, file_type)
        
        if result:
            print(f"✅ Celery文档 {document_id} 处理完成")
            return {
                'status': 'success',
                'document_id': document_id,
                'message': '文档处理完成'
            }
        else:
            print(f"❌ Celery文档 {document_id} 处理失败")
            return {
                'status': 'failed',
                'document_id': document_id,
                'message': '文档处理失败'
            }
            
    except Exception as exc:
        print(f"❌ Celery处理文档 {document_id} 时出错: {str(exc)}")
        
        # 重试机制
        if self.request.retries < self.max_retries:
            print(f"🔄 重试处理文档 {document_id}，第 {self.request.retries + 1} 次重试")
            raise self.retry(exc=exc, countdown=60)
        else:
            print(f"❌ 文档 {document_id} 处理失败，已达到最大重试次数")
            return {
                'status': 'failed',
                'document_id': document_id,
                'message': f'处理失败: {str(exc)}',
                'error': str(exc)
            }