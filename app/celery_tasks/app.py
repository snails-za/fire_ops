"""
启动定时任务
celery -A celery_tasks.app beat -l info
启动worker
celery -A celery_tasks.app worker -l info
Windows启动worker
celery -A celery_tasks.app worker -l info --pool=solo
"""

from celery import Celery
import config

celery_ = Celery(__name__, include=["celery_tasks.task"])  # 设置需要导入的模块
# 引入配置文件
celery_.config_from_object(config)
