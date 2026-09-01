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


# 全局实例
celery_task_manager = CeleryTaskManager()
