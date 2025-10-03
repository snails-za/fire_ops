"""
Celery任务定义

文档处理相关的任务
"""

from celery_tasks.app import celery_
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
        
        # 更新任务状态

        # 直接调用同步的文档处理方法
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


@celery_.task(bind=True)
def get_task_status(self, task_id: str):
    """
    获取任务状态
    
    Args:
        task_id: Celery任务ID
        
    Returns:
        dict: 任务状态信息
    """
    try:
        task = self.AsyncResult(task_id)
        
        if task.state == 'PENDING':
            return {
                'state': task.state,
                'status': '任务等待中...',
                'progress': 0
            }
        elif task.state == 'PROGRESS':
            return {
                'state': task.state,
                'status': task.info.get('status', '处理中...'),
                'progress': task.info.get('current', 0) / task.info.get('total', 100) * 100
            }
        elif task.state == 'SUCCESS':
            return {
                'state': task.state,
                'status': '处理完成',
                'progress': 100,
                'result': task.result
            }
        elif task.state == 'FAILURE':
            return {
                'state': task.state,
                'status': '处理失败',
                'progress': 0,
                'error': str(task.info)
            }
        else:
            return {
                'state': task.state,
                'status': '未知状态',
                'progress': 0
            }
            
    except Exception as e:
        return {
            'state': 'ERROR',
            'status': f'获取状态失败: {str(e)}',
            'progress': 0
        }
