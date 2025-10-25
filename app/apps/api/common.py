import shutil
import time

import psutil
from fastapi import APIRouter
from tortoise import connections

from apps.utils import response
from celery_tasks.app import celery_

router = APIRouter(prefix="/common", tags=["公共接口"])


@router.get("/health", summary="系统健康检查", description="检查系统各组件状态（无需登录）")
async def health_check():
    """
    系统健康检查接口
    :return:
    """
    start_time = time.time()
    health_data = {
        "timestamp": int(start_time * 1000),
        "status": "healthy",
        "components": {}
    }

    # 检查数据库
    try:
        db_start = time.time()
        # 执行一个简单的数据库查询
        await connections.get("default").execute_query("SELECT 1")
        db_time = (time.time() - db_start) * 1000

        health_data["components"]["database"] = {
            "status": "healthy",
            "response_time_ms": round(db_time, 2),
            "message": "数据库连接正常"
        }
    except Exception as e:
        health_data["components"]["database"] = {
            "status": "unhealthy",
            "message": f"数据库连接失败: {str(e)}"
        }
        health_data["status"] = "unhealthy"

    # 检查Celery任务队列
    celery_start = time.time()
    try:
        # 尝试获取工作进程统计信息
        inspect = celery_.control.inspect()
        stats = inspect.stats()

        if stats and len(stats) > 0:
            health_data["components"]["celery"] = {
                "status": "healthy",
                "response_time_ms": round((time.time() - celery_start) * 1000, 2),
                "message": f"任务队列正常 ({len(stats)}个工作进程)",
                "workers": len(stats)
            }
        else:
            # 没有工作进程，但Celery应用本身可以运行
            health_data["components"]["celery"] = {
                "status": "degraded",
                "response_time_ms": round((time.time() - celery_start) * 1000, 2),
                "message": "Celery应用正常，但无工作进程运行"
            }

    except Exception as e:
        # Celery应用不可用或获取统计信息失败
        health_data["components"]["celery"] = {
            "status": "unhealthy",
            "response_time_ms": round((time.time() - celery_start) * 1000, 2),
            "message": f"Celery检查失败: {str(e)}"
        }
        health_data["status"] = "unhealthy"

    # 检查API服务
    api_time = (time.time() - start_time) * 1000
    health_data["components"]["api"] = {
        "status": "healthy",
        "response_time_ms": round(api_time, 2),
        "message": "API服务正常"
    }

    # 计算总体响应时间
    health_data["response_time_ms"] = round(api_time, 2)

    return response(data=health_data)


@router.get("/system-resources", summary="系统资源监控", description="获取系统资源使用情况（无需登录）")
async def get_system_resources():
    """
    获取系统资源使用情况
    :return:
    """
    try:
        # CPU使用率
        cpu_percent = psutil.cpu_percent(interval=1)

        # 内存使用情况
        memory = psutil.virtual_memory()
        memory_percent = memory.percent

        # 磁盘使用情况
        disk = shutil.disk_usage('/')
        disk_percent = (disk.used / disk.total) * 100

        system_data = {
            "cpu": {
                "usage_percent": round(cpu_percent, 1)
            },
            "memory": {
                "usage_percent": round(memory_percent, 1)
            },
            "disk": {
                "usage_percent": round(disk_percent, 1)
            }
        }

        return response(data=system_data)

    except Exception as e:
        return response(code=500, message=f"获取系统资源信息失败: {str(e)}")
