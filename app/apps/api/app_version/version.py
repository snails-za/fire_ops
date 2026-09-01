"""
App 版本管理：后台发版 + 移动端检测更新。
"""

import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from apps.dependencies.auth import get_current_user
from apps.dependencies.permissions import check_admin_permission
from apps.models.app_version import AppVersion
from apps.models.user import User
from apps.utils import response
from config import APP_VERSION_STORE_PATH, BASE_PATH

router = APIRouter(prefix="/app/version", tags=["App版本管理"])

ALLOWED_PACKAGE_TYPES = {"apk", "wgt"}
ALLOWED_PLATFORMS = {"android"}
MAX_PACKAGE_SIZE = 300 * 1024 * 1024  # 300MB


def _public_file_url(file_path: str) -> str:
    if not file_path:
        return ""
    if file_path.startswith("http://") or file_path.startswith("https://"):
        return file_path
    return file_path if file_path.startswith("/") else f"/{file_path}"


def _serialize(item: AppVersion) -> dict:
    return {
        "id": item.id,
        "platform": item.platform,
        "version_name": item.version_name,
        "version_code": item.version_code,
        "package_type": item.package_type,
        "file_path": item.file_path,
        "download_url": _public_file_url(item.file_path),
        "file_size": item.file_size,
        "force_update": bool(item.force_update),
        "changelog": item.changelog or "",
        "status": item.status,
        "published_at": item.published_at,
        "created_by_user_id": item.created_by_user_id,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


@router.get("/check", summary="检测更新（App 启动调用，无需登录）")
async def check_update(
    platform: str = Query("android"),
    version_code: int = Query(..., ge=1, description="当前 App versionCode"),
):
    platform = (platform or "android").strip().lower()
    if platform not in ALLOWED_PLATFORMS:
        return response(code=400, message="暂不支持该平台")

    latest = (
        await AppVersion.filter(platform=platform, status="published")
        .order_by("-version_code", "-id")
        .first()
    )
    if not latest or latest.version_code <= version_code:
        return response(
            data={
                "has_update": False,
                "force_update": False,
                "version_name": latest.version_name if latest else None,
                "version_code": latest.version_code if latest else None,
                "package_type": latest.package_type if latest else None,
                "download_url": None,
                "changelog": "",
                "file_size": 0,
            },
            message="已是最新版本",
        )

    return response(
        data={
            "has_update": True,
            "force_update": bool(latest.force_update),
            "version_name": latest.version_name,
            "version_code": latest.version_code,
            "package_type": latest.package_type,
            "download_url": _public_file_url(latest.file_path),
            "changelog": latest.changelog or "",
            "file_size": latest.file_size,
        },
        message="发现新版本",
    )


@router.get(
    "/list",
    summary="版本列表（后台）",
    dependencies=[Depends(check_admin_permission)],
)
async def list_versions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    platform: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    query = AppVersion.all()
    if platform:
        query = query.filter(platform=platform)
    if status:
        query = query.filter(status=status)
    query = query.order_by("-version_code", "-id")
    total = await query.count()
    rows = await query.offset((page - 1) * page_size).limit(page_size)
    total_page = (total + page_size - 1) // page_size
    return response(
        data=[_serialize(row) for row in rows],
        total=total,
        total_page=total_page,
        message="获取版本列表成功",
    )


@router.post(
    "/publish",
    summary="上传并上线新版本（后台）",
    dependencies=[Depends(check_admin_permission)],
)
async def publish_version(
    file: UploadFile = File(...),
    platform: str = Form("android"),
    version_name: str = Form(...),
    version_code: int = Form(...),
    package_type: str = Form(...),
    force_update: str = Form("false"),
    changelog: str = Form(""),
    user: User = Depends(get_current_user),
):
    platform = (platform or "android").strip().lower()
    package_type = (package_type or "").strip().lower()
    version_name = (version_name or "").strip()
    force = str(force_update).strip().lower() in ("1", "true", "yes", "on")

    if platform not in ALLOWED_PLATFORMS:
        return response(code=400, message="暂不支持该平台")
    if package_type not in ALLOWED_PACKAGE_TYPES:
        return response(code=400, message="包类型仅支持 apk 或 wgt")
    if not version_name:
        return response(code=400, message="请填写版本名称")
    if version_code < 1:
        return response(code=400, message="version_code 必须大于 0")

    filename = (file.filename or "").lower()
    if package_type == "apk" and not filename.endswith(".apk"):
        return response(code=400, message="整包更新请上传 .apk 文件")
    if package_type == "wgt" and not filename.endswith(".wgt"):
        return response(code=400, message="热更新请上传 .wgt 文件")

    content = await file.read()
    if not content:
        return response(code=400, message="上传文件为空")
    if len(content) > MAX_PACKAGE_SIZE:
        return response(code=400, message="安装包过大，上限 300MB")

    os.makedirs(APP_VERSION_STORE_PATH, exist_ok=True)
    ext = ".apk" if package_type == "apk" else ".wgt"
    save_name = f"{platform}_{version_code}_{uuid.uuid4().hex[:10]}{ext}"
    abs_path = os.path.join(APP_VERSION_STORE_PATH, save_name)
    with open(abs_path, "wb") as f:
        f.write(content)

    rel_path = f"/data/app_versions/{save_name}"

    # 同平台旧已发布版本归档，保证检测只命中最新一条
    await AppVersion.filter(platform=platform, status="published").update(
        status="archived"
    )

    item = await AppVersion.create(
        platform=platform,
        version_name=version_name,
        version_code=version_code,
        package_type=package_type,
        file_path=rel_path,
        file_size=len(content),
        force_update=force,
        changelog=(changelog or "").strip() or None,
        status="published",
        published_at=datetime.now(),
        created_by_user_id=user.id,
    )
    return response(data=_serialize(item), message="版本已上线")


@router.put(
    "/{version_id}/force",
    summary="设置是否强制更新",
    dependencies=[Depends(check_admin_permission)],
)
async def set_force_update(version_id: int, force_update: bool = Query(...)):
    item = await AppVersion.get_or_none(id=version_id)
    if not item:
        return response(code=404, message="版本不存在")
    item.force_update = bool(force_update)
    await item.save()
    return response(data=_serialize(item), message="已更新强制更新设置")


@router.put(
    "/{version_id}/archive",
    summary="下线归档",
    dependencies=[Depends(check_admin_permission)],
)
async def archive_version(version_id: int):
    item = await AppVersion.get_or_none(id=version_id)
    if not item:
        return response(code=404, message="版本不存在")
    item.status = "archived"
    await item.save()
    return response(data=_serialize(item), message="已下线归档")


@router.delete(
    "/{version_id}",
    summary="删除版本记录",
    dependencies=[Depends(check_admin_permission)],
)
async def delete_version(version_id: int):
    item = await AppVersion.get_or_none(id=version_id)
    if not item:
        return response(code=404, message="版本不存在")

    file_path = item.file_path or ""
    if file_path.startswith("/data/"):
        abs_path = os.path.join(BASE_PATH, file_path.lstrip("/"))
        if os.path.isfile(abs_path):
            try:
                os.remove(abs_path)
            except OSError:
                pass

    await item.delete()
    return response(message="删除成功")
