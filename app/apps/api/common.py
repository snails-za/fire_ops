from fastapi import APIRouter, Depends

from apps.dependencies.auth import get_current_user
from apps.utils import response

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

