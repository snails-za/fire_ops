"""
设备信息查询助手

提供设备信息的智能查询功能，用于增强问答系统
"""

from typing import List, Dict, Any, Optional

from tortoise.expressions import Q

from apps.models.device import Device


async def search_devices(query: str, user_id: Optional[int] = None, is_admin: bool = False, original_query: str = None) -> List[Dict[str, Any]]:
    """
    智能设备搜索 - 多策略搜索设备信息，同时支持优化后和原始问题
    
    Args:
        query: 优化后的搜索关键词
        user_id: 用户ID（用于权限过滤）
        is_admin: 是否为管理员
        original_query: 原始问题（可选）
        
    Returns:
        设备信息列表
    """
    try:
        # 构建权限条件
        permission_conditions = []
        if not is_admin and user_id:
            permission_conditions.append(Q(created_by_user_id=user_id))
        
        print(f"搜索关键词: {query}, 原始问题: {original_query}, 用户ID: {user_id}, 是否管理员: {is_admin}")
        
        # 准备搜索查询列表（优化后 + 原始问题）
        search_queries = [query]
        if original_query and original_query != query:
            search_queries.append(original_query)
        
        all_devices = []
        
        # 对每个查询执行多策略搜索
        for search_query in search_queries:
            print(f"使用查询: {search_query}")
            
            # 策略1: 精确匹配搜索
            exact_devices = await _search_devices_exact(search_query, permission_conditions)
            print(f"精确匹配结果: {len(exact_devices)}")
            
            # 策略2: 模糊匹配搜索
            fuzzy_devices = await _search_devices_fuzzy(search_query, permission_conditions)
            print(f"模糊匹配结果: {len(fuzzy_devices)}")
            
            # 策略3: 关键词拆分搜索
            keyword_devices = await _search_devices_keywords(search_query, permission_conditions)
            print(f"关键词拆分结果: {len(keyword_devices)}")
            
            # 策略4: 状态/类型搜索
            status_devices = await _search_devices_by_status(search_query, permission_conditions)
            print(f"状态搜索结果: {len(status_devices)}")
            
            # 合并当前查询的结果
            current_query_devices = exact_devices + fuzzy_devices + keyword_devices + status_devices
            all_devices.extend(current_query_devices)
        
        # 去重合并所有结果
        unique_devices = []
        seen_ids = set()
        
        for device in all_devices:
            if device['id'] not in seen_ids:
                unique_devices.append(device)
                seen_ids.add(device['id'])
        
        print(f"合并去重后设备数量: {len(unique_devices)}")
        return unique_devices[:20]  # 限制返回数量
        
    except Exception as e:
        print(f"搜索设备失败: {e}")
        return []


async def _search_devices_exact(query: str, permission_conditions: List) -> List[Dict[str, Any]]:
    """精确匹配搜索"""
    try:
        conditions = permission_conditions.copy()
        if query:
            # 精确匹配设备名称
            conditions.append(Q(name__icontains=query))
        
        if conditions:
            devices = await Device.filter(*conditions).limit(10).all()
        else:
            devices = await Device.all().limit(10)
        
        return [_device_to_dict(device) for device in devices]
    except Exception as _:
        return []


async def _search_devices_fuzzy(query: str, permission_conditions: List) -> List[Dict[str, Any]]:
    """模糊匹配搜索"""
    try:
        conditions = permission_conditions.copy()
        if query:
            # 模糊匹配多个字段
            fuzzy_filter = (Q(name__icontains=query) | 
                           Q(address__icontains=query) | 
                           Q(status__icontains=query) | 
                           Q(installer__icontains=query) | 
                           Q(remark__icontains=query))
            conditions.append(fuzzy_filter)
        
        if conditions:
            devices = await Device.filter(*conditions).limit(10).all()
        else:
            devices = await Device.all().limit(10)
        
        return [_device_to_dict(device) for device in devices]
    except Exception as _:
        return []


async def _search_devices_keywords(query: str, permission_conditions: List) -> List[Dict[str, Any]]:
    """关键词拆分搜索"""
    try:
        if not query:
            return []
            
        conditions = permission_conditions.copy()
        keywords = query.split()
        
        # 使用OR逻辑，任意关键词匹配即可
        keyword_conditions = []
        for keyword in keywords:
            if keyword.strip():
                keyword_conditions.append(
                    Q(name__icontains=keyword) | 
                    Q(address__icontains=keyword) | 
                    Q(status__icontains=keyword) | 
                    Q(installer__icontains=keyword) | 
                    Q(remark__icontains=keyword)
                )
        
        if keyword_conditions:
            # 使用OR逻辑组合关键词条件

            combined_condition = keyword_conditions[0]
            for condition in keyword_conditions[1:]:
                combined_condition |= condition
            conditions.append(combined_condition)
        
        if conditions:
            devices = await Device.filter(*conditions).limit(10).all()
        else:
            devices = await Device.all().limit(10)
        
        return [_device_to_dict(device) for device in devices]
    except Exception as _:
        return []


async def _search_devices_by_status(query: str, permission_conditions: List) -> List[Dict[str, Any]]:
    """基于状态/类型的智能搜索"""
    try:
        conditions = permission_conditions.copy()
        
        # 状态关键词映射
        status_keywords = {
            '正常': ['正常', '运行', '工作', 'ok', 'good'],
            '离线': ['离线', '断线', '断开', 'offline'],
            '异常': ['异常', '故障', '错误', '问题', '坏', 'error'],
            '维修': ['维修', '维护', '保养', '修理', 'fix']
        }
        
        if query:
            # 检查是否包含状态相关关键词
            for status, keywords in status_keywords.items():
                if any(keyword in query.lower() for keyword in keywords):
                    conditions.append(Q(status=status))
                    break
        
        if conditions:
            devices = await Device.filter(*conditions).limit(10).all()
        else:
            devices = await Device.all().limit(10)
        
        return [_device_to_dict(device) for device in devices]
    except Exception as _:
        return []


def _device_to_dict(device) -> Dict[str, Any]:
    """将设备对象转换为字典"""
    return {
        "id": device.id,
        "name": device.name,
        "address": device.address,
        "location": device.location,
        "status": device.status,
        "install_date": str(device.install_date) if device.install_date else None,
        "installer": device.installer,
        "contact": device.contact,
        "remark": device.remark,
        "images": device.images,
    }


def should_search_devices(query: str, original_query: str = None) -> bool:
    """
    判断问题是否与设备相关，同时检查优化后和原始问题
    
    Args:
        query: 优化后的用户问题
        original_query: 原始用户问题（可选）
        
    Returns:
        是否需要搜索设备信息
    """
    # 设备相关关键词（更精确的匹配）
    device_keywords = [
        '设备', '监控设备', '报警设备', '传感器', '摄像头', '门禁',
        '设备状态', '设备位置', '设备地址', '设备安装', '设备维护', '设备故障', '设备异常',
        '离线设备', '在线设备', '正常设备', '维修设备', '保养设备', '检查设备',
        '设备名', '设备号', '设备ID', '设备状态', '设备位置'
    ]
    
    # 问题类型关键词
    question_keywords = [
        '什么', '哪些', '哪里', '如何', '怎么', '为什么', '什么时候',
        '有多少', '状态如何', '位置在哪', '谁安装的', '什么时候安装的'
    ]
    
    # 检查优化后的问题
    query_lower = query.lower()
    has_device_keyword = any(keyword in query_lower for keyword in device_keywords)
    has_question_keyword = any(keyword in query_lower for keyword in question_keywords)
    
    # 如果优化后的问题已经匹配，直接返回
    if has_device_keyword or has_question_keyword:
        return True
    
    # 如果提供了原始问题，也检查原始问题
    if original_query and original_query != query:
        original_lower = original_query.lower()
        has_original_device_keyword = any(keyword in original_lower for keyword in device_keywords)
        has_original_question_keyword = any(keyword in original_lower for keyword in question_keywords)
        
        if has_original_device_keyword or has_original_question_keyword:
            return True
    
    # 特殊处理：如果问题包含"消防"但不是设备相关，则不应该搜索设备
    # 例如："江西消防最新法规" 应该搜索文档，不是设备
    if '消防' in query_lower or (original_query and '消防' in original_query.lower()):
        # 检查是否包含设备相关的上下文
        device_context_keywords = ['设备', '监控', '报警', '传感器', '摄像头', '门禁', '状态', '位置', '安装', '维护', '故障', '异常', '离线', '在线', '正常', '维修', '保养', '检查']
        has_device_context = any(keyword in query_lower for keyword in device_context_keywords)
        if not has_device_context:
            return False
    
    return False


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


def format_device_context(devices: List[Dict[str, Any]]) -> str:
    """
    将设备信息格式化为RAG上下文
    
    Args:
        devices: 设备信息列表
        
    Returns:
        格式化的设备上下文字符串
    """
    print(f"format_device_context 接收到设备数量: {len(devices) if devices else 0}")
    
    if not devices:
        print("设备列表为空，返回空字符串")
        return ""
    
    context_parts = []
    for i, device in enumerate(devices, 1):
        print(f"格式化设备 {i}: {device}")
        device_info = f"""设备 {i}: {device.get('name', '未知设备')}
- 地址: {device.get('address', '未设置')}
- 状态: {device.get('status', '未知')}
- 安装日期: {device.get('install_date', '未设置')}
- 安装人: {device.get('installer', '未设置')}
- 联系方式: {device.get('contact', '未设置')}"""
        
        if device.get('remark'):
            device_info += f"\n- 备注: {device.get('remark')}"
        
        context_parts.append(device_info)
    
    result = "\n\n" + "=" * 50 + "\n\n".join(context_parts)
    print(f"格式化后的设备上下文长度: {len(result)}")
    return result


async def get_device_statistics(user_id: Optional[int] = None, is_admin: bool = False, query: str = None, original_query: str = None) -> Dict[str, Any]:
    """
    获取设备统计信息，支持根据问题内容进行筛选
    
    Args:
        user_id: 用户ID
        is_admin: 是否为管理员
        query: 优化后的查询关键词
        original_query: 原始查询关键词
        
    Returns:
        设备统计信息
    """
    try:
        # 构建权限条件
        permission_conditions = []
        if not is_admin and user_id:
            permission_conditions.append(Q(created_by_user_id=user_id))
        
        # 构建筛选条件（使用与设备搜索相同的多策略方法）
        all_conditions = permission_conditions.copy()
        
        # 检查是否为统计类问题，统计类问题需要更智能的筛选
        is_stats_question = False
        if query or original_query:
            stats_keywords = ['统计', '总数', '有多少', '分布', '比例', '率', '数量', '概览', '几']
            is_stats_question = any(keyword in (query or '').lower() for keyword in stats_keywords) or \
                               any(keyword in (original_query or '').lower() for keyword in stats_keywords)
        
        if query or original_query:
            # 准备搜索查询列表（优化后 + 原始问题）
            search_queries = [query] if query else []
            if original_query and original_query != query:
                search_queries.append(original_query)
            
            # 使用与设备搜索相同的多策略方法
            filter_conditions = []
            for search_query in search_queries:
                if search_query:
                    print(f"统计筛选使用查询: {search_query}")
                    
                    # 策略1: 精确匹配搜索
                    filter_conditions.append(Q(name__icontains=search_query))
                    
                    # 策略2: 模糊匹配搜索
                    fuzzy_filter = (Q(name__icontains=search_query) | 
                                   Q(address__icontains=search_query) | 
                                   Q(status__icontains=search_query) | 
                                   Q(installer__icontains=search_query) | 
                                   Q(remark__icontains=search_query))
                    filter_conditions.append(fuzzy_filter)
                    
                    # 策略3: 关键词拆分搜索
                    keywords = search_query.split()
                    keyword_conditions = []
                    for keyword in keywords:
                        if keyword.strip():
                            keyword_conditions.append(
                                Q(name__icontains=keyword) | 
                                Q(address__icontains=keyword) | 
                                Q(status__icontains=keyword) | 
                                Q(installer__icontains=keyword) | 
                                Q(remark__icontains=keyword)
                            )
                    
                    if keyword_conditions:
                        # 使用OR逻辑组合关键词条件
                        combined_keyword_condition = keyword_conditions[0]
                        for condition in keyword_conditions[1:]:
                            combined_keyword_condition |= condition
                        filter_conditions.append(combined_keyword_condition)
                    
                    # 策略4: 状态/类型搜索（只在明确询问特定状态时使用）
                    if is_stats_question:
                        # 统计类问题：只在明确询问特定状态设备时才筛选
                        status_keywords = {
                            '正常': ['正常设备', '正常状态', '运行设备', '工作设备'],
                            '离线': ['离线设备', '离线状态', '断线设备', '断开设备'],
                            '异常': ['异常设备', '异常状态', '故障设备', '错误设备', '问题设备'],
                            '维修': ['维修设备', '维修状态', '维护设备', '保养设备', '修理设备']
                        }
                        
                        # 只有明确询问特定状态设备时才添加状态筛选
                        for status, keywords in status_keywords.items():
                            if any(keyword in search_query.lower() for keyword in keywords):
                                filter_conditions.append(Q(status=status))
                                break
                    else:
                        # 非统计类问题：使用原有的状态搜索逻辑
                        status_keywords = {
                            '正常': ['正常', '运行', '工作', 'ok', 'good'],
                            '离线': ['离线', '断线', '断开', 'offline'],
                            '异常': ['异常', '故障', '错误', '问题', '坏', 'error'],
                            '维修': ['维修', '维护', '保养', '修理', 'fix']
                        }
                        
                        for status, keywords in status_keywords.items():
                            if any(keyword in search_query.lower() for keyword in keywords):
                                filter_conditions.append(Q(status=status))
                                break
            
            if filter_conditions:
                # 使用OR逻辑组合所有筛选条件
                combined_filter = filter_conditions[0]
                for condition in filter_conditions[1:]:
                    combined_filter |= condition
                all_conditions.append(combined_filter)
        
        print(f"统计筛选条件数量: {len(all_conditions)}, 查询: {query}, 原始查询: {original_query}")
        
        # 基础统计（根据筛选条件）
        if all_conditions:
            total_devices = await Device.filter(*all_conditions).count()
        else:
            total_devices = await Device.all().count()
        
        # 状态分布统计（提供完整的状态分布，不受筛选条件影响）
        # 这样用户可以看到所有状态的设备数量，即使他们问的是特定状态的问题
        status_distribution = {}
        for status in ["正常", "离线", "异常", "维修中"]:
            if permission_conditions:
                count = await Device.filter(*permission_conditions, status=status).count()
            else:
                count = await Device.filter(status=status).count()
            status_distribution[status] = count
        
        return {
            "total_devices": total_devices,
            "status_distribution": status_distribution
        }
        
    except Exception as e:
        print(f"获取设备统计失败: {e}")
        return {
            "total_devices": 0,
            "status_distribution": {}
        }

