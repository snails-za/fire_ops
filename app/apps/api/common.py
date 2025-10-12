import time

from fastapi import APIRouter, Depends
from tortoise import connections

from apps.dependencies.auth import get_current_user
from apps.utils import response
from celery_tasks.app import celery_

router = APIRouter(prefix="/common", tags=["公共接口"])



@router.get("/swiper", summary="轮播图", description="获取轮播图", dependencies=[Depends(get_current_user)])
async def swiper_data():
    """
    获取设备列表
    :return:
    """
    data = [
        {"id": 3, "title": "设备3", "image": "/static/images/device/image3.jpeg"},
        {"id": 2, "title": "设备2", "image": "/static/images/device/image2.jpeg"},
        {"id": 4, "title": "设备4", "image": "/static/images/device/image4.jpeg"},
        {"id": 1, "title": "设备1", "image": "/static/images/device/image1.jpeg"},
        {"id": 5, "title": "设备5", "image": "/static/images/device/image5.jpeg"},
        {"id": 6, "title": "设备6", "image": "/static/images/device/image6.jpeg"},
        {"id": 7, "title": "设备7", "image": "/static/images/device/image7.jpeg"},

    ]
    return response(data=data)


@router.get("/notice", summary="公告", description="获取公告", dependencies=[Depends(get_current_user)])
async def get_notice():
    """
    获取设备列表
    :return:
    """
    data = "即将于【2026年5月11日】发布最新版本！敬请期待！"
    return response(data=data)


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

