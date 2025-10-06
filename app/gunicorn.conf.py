# Gunicorn 配置文件
# 用于生产环境的 WSGI 服务器配置

import multiprocessing
import os

# 服务器套接字
bind = "0.0.0.0:8000"
backlog = 2048

# Worker 进程
workers = int(os.environ.get('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
timeout = 30
keepalive = 2

# 重启
max_requests = 1000
max_requests_jitter = 50
preload_app = False  # 禁用预加载，避免异步问题

# 日志 - 统一输出到stdout/stderr，由supervisor汇总
accesslog = "-"  # 输出到stdout
errorlog = "-"   # 输出到stderr
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# 确保print输出被正确捕获
capture_output = True

# FastAPI/ASGI特定配置
forwarded_allow_ips = "*"
secure_scheme_headers = {"X-FORWARDED-PROTOCOL": "ssl", "X-FORWARDED-PROTO": "https", "X-FORWARDED-SSL": "on"}

# 进程管理
pidfile = "/app/logs/gunicorn.pid"
user = None
group = None
tmp_upload_dir = None

# SSL (如果需要)
# keyfile = "/path/to/keyfile"
# certfile = "/path/to/certfile"

# 安全
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# 性能优化
worker_tmp_dir = "/dev/shm"
