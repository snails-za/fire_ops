# 简化的Gunicorn配置文件 - 用于调试
# 专门针对FastAPI应用优化

import multiprocessing
import os

# 服务器套接字
bind = "0.0.0.0:8000"

# Worker 进程 - 单worker模式，避免多进程问题
workers = 1
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120
keepalive = 2

# 禁用预加载，避免异步问题
preload_app = False

# 日志配置
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'
capture_output = True

# FastAPI/ASGI特定配置
forwarded_allow_ips = "*"

# 进程管理
pidfile = "/app/logs/gunicorn.pid"
