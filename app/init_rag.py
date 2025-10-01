#!/usr/bin/env python3
"""
RAG系统初始化脚本
创建必要的目录和文件
"""

import os
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import STATIC_PATH, VECTOR_DB_PATH, CHROMA_PERSIST_DIRECTORY


def create_directories():
    """创建必要的目录"""
    directories = [
        os.path.join(STATIC_PATH, "documents"),
        os.path.join(STATIC_PATH, "images", "device"),
        VECTOR_DB_PATH,
        CHROMA_PERSIST_DIRECTORY,
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✅ 创建目录: {directory}")


def create_sample_user():
    """创建示例用户"""
    try:
        from apps.models.user import User
        from apps.utils.common import get_hash
        
        # 检查是否已存在用户
        existing_user = User.filter(username="admin").first()
        if existing_user:
            print("✅ 管理员用户已存在")
            return
        
        # 创建管理员用户
        admin_user = User.create(
            username="admin",
            password=get_hash("123456"),  # 密码: 123456
            email="admin@example.com"
        )
        print("✅ 创建管理员用户: admin / 123456")
        
    except Exception as e:
        print(f"❌ 创建用户失败: {e}")


def main():
    """主函数"""
    print("🚀 初始化RAG系统...")
    
    # 创建目录
    create_directories()
    
    # 创建示例用户
    create_sample_user()
    
    print("✅ RAG系统初始化完成!")
    print("\n📝 使用说明:")
    print("1. 运行数据库迁移: aerich upgrade")
    print("2. 启动服务: fastapi dev asgi.py")
    print("3. 访问: http://localhost:8000")
    print("4. 登录: admin / 123456")


if __name__ == "__main__":
    main()
