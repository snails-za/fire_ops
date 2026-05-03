"""
设备信息查询助手

提供设备信息的智能查询功能，用于增强问答系统
"""

from typing import Dict, Any, Optional

from apps.models.device import Device
from config import MAX_DEVICES_FOR_LLM


async def get_all_devices_by_permission(user_id: Optional[int] = None, is_admin: bool = False) -> Dict[str, Any]:
    """
    根据权限获取设备数据（统计信息 + 设备列表摘要）
    
    一劳永逸的方案：
    - 统计信息：始终包含完整的统计信息（总数、状态分布等），不受设备数量限制
    - 设备列表：只返回部分设备详情（由MAX_DEVICES_FOR_LLM配置控制），用于LLM理解数据结构
    - 这样既能满足统计需求，又能控制上下文大小，不受设备数量增长影响
    
    Args:
        user_id: 用户ID
        is_admin: 是否为管理员
        
    Returns:
        包含统计信息和设备列表的字典
    """
    try:
        # 构建权限条件
        if is_admin:
            total_count = await Device.all().count()
            # 获取状态分布统计
            status_distribution = {}
            for status in ["正常", "离线", "异常", "维修中"]:
                count = await Device.filter(status=status).count()
                status_distribution[status] = count
            
            # 获取设备列表（限制数量，用于LLM理解数据结构）
            # 按ID倒序，获取最新的设备
            devices_query = Device.all().order_by("-id").limit(MAX_DEVICES_FOR_LLM)
        else:
            total_count = await Device.filter(created_by_user_id=user_id).count()
            # 获取状态分布统计
            status_distribution = {}
            for status in ["正常", "离线", "异常", "维修中"]:
                count = await Device.filter(created_by_user_id=user_id, status=status).count()
                status_distribution[status] = count
            
            # 获取设备列表（限制数量）
            devices_query = Device.filter(created_by_user_id=user_id).order_by("-id").limit(MAX_DEVICES_FOR_LLM)
        
        print(f"设备总数: {total_count} 台，将返回前 {MAX_DEVICES_FOR_LLM} 台设备详情")
        
        # 转换为字典格式
        device_list = []
        all_devices = await devices_query
        for device in all_devices:
            device_list.append({
                "id": device.id,
                "name": device.name,
                "address": device.address,
                "location": device.location,
                "status": device.status,
                "install_date": str(device.install_date) if device.install_date else None,
                "installer": device.installer,
                "installer_contact": device.installer_contact,
                "contact": device.contact,
                "remark": device.remark,
                "images": device.images,
            })
        
        result = {
            "total": total_count,
            "status_distribution": status_distribution,
            "devices": device_list,
            "is_partial": total_count > MAX_DEVICES_FOR_LLM  # 标记是否为部分数据
        }
        
        if result["is_partial"]:
            print(f"⚠️ 注意: 设备总数 {total_count} 台，仅返回前 {MAX_DEVICES_FOR_LLM} 台详情，但统计信息完整")
        
        return result
    except Exception as e:
        print(f"获取设备数据失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            "total": 0,
            "status_distribution": {},
            "devices": [],
            "is_partial": False
        }


async def get_all_devices_summary(user_id: Optional[int] = None, is_admin: bool = False) -> Dict[str, Any]:
    """
    获取所有设备的统计摘要信息
    
    Args:
        user_id: 用户ID
        is_admin: 是否为管理员
        
    Returns:
        设备统计信息
    """
    try:
        # 构建查询条件
        if is_admin:
            total_devices = await Device.all().count()
            devices_by_status = {}
            
            # 按状态统计
            for status in ["正常", "离线", "异常", "维修中"]:
                count = await Device.filter(status=status).count()
                devices_by_status[status] = count
            
            # 获取所有设备
            all_devices = await Device.all().limit(100)
        else:
            total_devices = await Device.filter(created_by_user_id=user_id).count()
            devices_by_status = {}
            
            for status in ["正常", "离线", "异常", "维修中"]:
                count = await Device.filter(created_by_user_id=user_id, status=status).count()
                devices_by_status[status] = count
            
            all_devices = await Device.filter(created_by_user_id=user_id).limit(100)
        
        # 转换为字典
        device_list = []
        for device in all_devices:
            device_dict = {
                "id": device.id,
                "name": device.name,
                "address": device.address,
                "status": device.status,
                "install_date": str(device.install_date) if device.install_date else None,
            }
            device_list.append(device_dict)
        
        return {
            "total": total_devices,
            "by_status": devices_by_status,
            "devices": device_list
        }
        
    except Exception as e:
        print(f"获取设备统计失败: {e}")
        return {
            "total": 0,
            "by_status": {},
            "devices": []
        }


def format_device_context(device_data: Dict[str, Any]) -> str:
    """
    将设备数据格式化为RAG上下文
    
    一劳永逸的方案：传递统计信息 + 设备列表摘要
    - 统计信息完整，不受设备数量限制
    - 设备列表只包含部分详情，控制上下文大小
    
    Args:
        device_data: 包含统计信息和设备列表的字典
        
    Returns:
        格式化的设备上下文字符串
    """
    if not device_data or device_data.get("total", 0) == 0:
        print("设备数据为空")
        return "当前没有设备数据。"
    
    total = device_data.get("total", 0)
    status_distribution = device_data.get("status_distribution", {})
    devices = device_data.get("devices", [])
    is_partial = device_data.get("is_partial", False)
    
    print(f"格式化设备上下文: 总数={total}, 详情数量={len(devices)}, 是否部分数据={is_partial}")
    
    # 构建统计信息部分
    result = f"""设备统计信息：
- 设备总数: {total} 台
- 状态分布:
  * 正常: {status_distribution.get('正常', 0)} 台
  * 离线: {status_distribution.get('离线', 0)} 台
  * 异常: {status_distribution.get('异常', 0)} 台
  * 维修中: {status_distribution.get('维修中', 0)} 台"""
    
    if is_partial:
        result += f"\n\n注意: 以下是前 {len(devices)} 台设备的详细信息（用于参考数据结构），完整统计信息见上方。"
    else:
        result += f"\n\n以下是所有 {len(devices)} 台设备的详细信息："
    
    result += "\n\n" + "=" * 50 + "\n\n"
    
    # 构建设备列表部分
    if devices:
        context_parts = []
        for i, device in enumerate(devices, 1):
            device_info = f"""设备 {i}: {device.get('name', '未知设备')}
- 地址: {device.get('address', '未设置')}
- 状态: {device.get('status', '未知')}
- 安装日期: {device.get('install_date', '未设置')}
- 安装人: {device.get('installer', '未设置')}
- 安装人联系方式: {device.get('installer_contact', '未设置')}
- 维护人联系方式: {device.get('contact', '未设置')}"""
            
            if device.get('remark'):
                device_info += f"\n- 备注: {device.get('remark')}"
            
            context_parts.append(device_info)
        
        result += "\n\n".join(context_parts)
    else:
        result += "暂无设备详情。"
    
    print(f"格式化后的设备上下文长度: {len(result)} 字符")
    return result


