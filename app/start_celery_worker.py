#!/usr/bin/env python3
"""
启动Celery Worker脚本

用于启动文档处理的Celery worker进程
"""

import os
import sys
import subprocess
from pathlib import Path

def start_celery_worker():
    """启动Celery worker"""
    
    print("🚀 启动Celery Worker...")
    
    # 获取项目根目录
    project_root = Path(__file__).parent
    
    # 设置环境变量
    env = os.environ.copy()
    env['PYTHONPATH'] = str(project_root)
    
    # Celery worker命令
    cmd = [
        sys.executable, "-m", "celery",
        "-A", "apps.celery_tasks.app",
        "worker",
        "-l", "info",
        "--pool=solo",  # Windows兼容
        "--concurrency=1"  # 限制并发数，避免资源冲突
    ]
    
    print(f"📝 执行命令: {' '.join(cmd)}")
    print("💡 提示: 按 Ctrl+C 停止worker")
    print("=" * 50)
    
    try:
        # 启动Celery worker
        subprocess.run(cmd, env=env, cwd=project_root)
    except KeyboardInterrupt:
        print("\n🛑 收到停止信号，正在关闭Celery worker...")
    except Exception as e:
        print(f"❌ 启动Celery worker失败: {str(e)}")
        return False
    
    print("✅ Celery worker已停止")
    return True


if __name__ == "__main__":
    start_celery_worker()
