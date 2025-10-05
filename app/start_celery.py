#!/usr/bin/env python3
"""
Celery启动脚本
用于启动Celery Worker和Beat调度器
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

def start_worker(pool='solo', concurrency=1, loglevel='info'):
    """启动Celery Worker"""
    cmd = [
        'celery', '-A', 'celery_tasks.app', 'worker',
        '--loglevel', loglevel,
        '--pool', pool,
        '--concurrency', str(concurrency)
    ]
    
    if pool == 'solo':
        print("🚀 启动Celery Worker (单进程模式)")
    else:
        print(f"🚀 启动Celery Worker (池模式: {pool}, 并发数: {concurrency})")
    
    print(f"执行命令: {' '.join(cmd)}")
    subprocess.run(cmd)

def start_beat(loglevel='info'):
    """启动Celery Beat调度器"""
    cmd = [
        'celery', '-A', 'celery_tasks.app', 'beat',
        '--loglevel', loglevel
    ]
    
    print("⏰ 启动Celery Beat调度器")
    print(f"执行命令: {' '.join(cmd)}")
    subprocess.run(cmd)

def start_flower(port=5555):
    """启动Flower监控界面"""
    cmd = [
        'celery', '-A', 'celery_tasks.app', 'flower',
        '--port', str(port)
    ]
    
    print(f"🌸 启动Flower监控界面 (端口: {port})")
    print(f"访问地址: http://localhost:{port}")
    print(f"执行命令: {' '.join(cmd)}")
    subprocess.run(cmd)

def main():
    parser = argparse.ArgumentParser(description='Celery启动脚本')
    parser.add_argument('command', choices=['worker', 'beat', 'flower', 'all'], 
                       help='要启动的服务')
    parser.add_argument('--pool', default='solo', choices=['solo', 'prefork', 'threads'],
                       help='Worker池类型 (默认: solo)')
    parser.add_argument('--concurrency', type=int, default=1,
                       help='并发数 (默认: 1)')
    parser.add_argument('--loglevel', default='info', 
                       choices=['debug', 'info', 'warning', 'error'],
                       help='日志级别 (默认: info)')
    parser.add_argument('--port', type=int, default=5555,
                       help='Flower端口 (默认: 5555)')
    
    args = parser.parse_args()
    
    # 切换到项目目录
    project_dir = Path(__file__).parent
    os.chdir(project_dir)
    
    try:
        if args.command == 'worker':
            start_worker(args.pool, args.concurrency, args.loglevel)
        elif args.command == 'beat':
            start_beat(args.loglevel)
        elif args.command == 'flower':
            start_flower(args.port)
        elif args.command == 'all':
            print("🚀 启动所有Celery服务")
            print("注意: 这将启动Worker、Beat和Flower")
            print("建议在不同终端窗口中分别启动各个服务")
            print("\n启动命令示例:")
            print("python start_celery.py worker --pool solo")
            print("python start_celery.py beat")
            print("python start_celery.py flower")
    
    except KeyboardInterrupt:
        print("\n⏹️  服务已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
