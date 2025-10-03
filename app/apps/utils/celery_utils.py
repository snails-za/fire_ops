"""
Celery任务管理工具

提供Celery任务的统一管理接口
"""

from celery_tasks.app import celery_


class CeleryTaskManager:
    """Celery任务管理器"""
    
    @staticmethod
    def revoke_task(task_id: str, terminate: bool = True):
        """
        撤销/停止Celery任务
        
        Args:
            task_id: 任务ID
            terminate: 是否强制终止任务
            
        Returns:
            bool: 是否成功停止任务
        """
        try:
            celery_.control.revoke(task_id, terminate=terminate)
            print(f"🛑 已停止任务: {task_id}")
            return True
        except Exception as e:
            print(f"⚠️ 停止任务失败: {str(e)}")
            return False
    
    @staticmethod
    def get_task_status(task_id: str):
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            dict: 任务状态信息
        """
        try:
            task = celery_.AsyncResult(task_id)
            
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
    
    @staticmethod
    def get_active_tasks():
        """
        获取所有活跃任务
        
        Returns:
            list: 活跃任务列表
        """
        try:
            inspect = celery_.control.inspect()
            active_tasks = inspect.active()
            return active_tasks
        except Exception as e:
            print(f"⚠️ 获取活跃任务失败: {str(e)}")
            return {}
    
    @staticmethod
    def purge_queue(queue_name: str = 'default'):
        """
        清空指定队列
        
        Args:
            queue_name: 队列名称
            
        Returns:
            int: 清空的任务数量
        """
        try:
            purged = celery_.control.purge()
            print(f"🧹 已清空队列 {queue_name}，清空了 {purged} 个任务")
            return purged
        except Exception as e:
            print(f"⚠️ 清空队列失败: {str(e)}")
            return 0


# 全局实例
celery_task_manager = CeleryTaskManager()
