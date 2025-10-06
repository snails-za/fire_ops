# Fire Ops Docker Supervisor 部署指南

## 概述

本项目已配置为使用 Supervisor 在 Docker 容器中管理多个服务：
- **fire_ops_webapp**: FastAPI Web 应用服务
- **fire_ops_celery_worker**: Celery 异步任务处理服务
- **fire_ops_celery_beat**: Celery 定时任务调度服务

## Dockerfile 修改说明

### 主要改动

1. **安装 Supervisor**:
   ```dockerfile
   RUN pip3 install -i https://pypi.tuna.tsinghua.edu.cn/simple supervisor
   ```

2. **创建日志目录**:
   ```dockerfile
   RUN mkdir -p /var/log/supervisor
   ```

3. **复制配置文件**:
   ```dockerfile
   COPY ./app/supervisor.conf /etc/supervisor/conf.d/fire_ops.conf
   ```

4. **修改启动命令**:
   ```dockerfile
   CMD ["supervisord", "-c", "/etc/supervisor/conf.d/fire_ops.conf", "-n"]
   ```

### 配置文件适配

- 工作目录改为 `/app`（Docker容器内路径）
- 移除用户配置（Docker容器内运行）
- 环境变量PATH指向虚拟环境 `/app/.venv/bin`
- 使用Gunicorn作为WSGI服务器，提供更好的性能和稳定性
- 日志输出到 `/app/logs/` 目录，便于容器内管理

## 构建镜像

### x86_64 架构
```bash
cd /Users/wangju/Desktop/code/fire_ops
docker build -f docker/Dockerfile -t fire_ops:latest .
```

### ARM64 架构
```bash
cd /Users/wangju/Desktop/code/fire_ops
docker build -f docker/Dockerfile-arm -t fire_ops:latest-arm .
```

## 运行容器

### 基本运行
```bash
docker run -d \
  --name fire_ops \
  -p 8000:8000 \
  -e POSTGRES_HOST=your_db_host \
  -e POSTGRES_PORT=15432 \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=your_password \
  -e POSTGRES_DB=fire_ops \
  -e REDIS_HOST=your_redis_host \
  -e REDIS_PORT=16379 \
  fire_ops:latest
```

### 带数据卷运行
```bash
docker run -d \
  --name fire_ops \
  -p 8000:8000 \
  -v /host/logs:/var/log/supervisor \
  -v /host/data:/app/data \
  -e POSTGRES_HOST=your_db_host \
  -e POSTGRES_PORT=15432 \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=your_password \
  -e POSTGRES_DB=fire_ops \
  -e REDIS_HOST=your_redis_host \
  -e REDIS_PORT=16379 \
  fire_ops:latest
```

## 服务管理

### 查看服务状态
```bash
docker exec -it fire_ops supervisorctl status
```

### 重启特定服务
```bash
docker exec -it fire_ops supervisorctl restart fire_ops_webapp
docker exec -it fire_ops supervisorctl restart fire_ops_celery_worker
docker exec -it fire_ops supervisorctl restart fire_ops_celery_beat
```

### 重启所有服务
```bash
docker exec -it fire_ops supervisorctl restart all
```

### 停止特定服务
```bash
docker exec -it fire_ops supervisorctl stop fire_ops_webapp
```

### 启动特定服务
```bash
docker exec -it fire_ops supervisorctl start fire_ops_webapp
```

## 日志查看

### 查看所有服务日志
```bash
docker logs fire_ops
```

### 查看特定服务日志
```bash
# 查看 Web 应用日志
docker exec -it fire_ops tail -f /app/logs/fire_ops_webapp.log

# 查看 Gunicorn 访问日志
docker exec -it fire_ops tail -f /app/logs/gunicorn_access.log

# 查看 Celery Worker 日志
docker exec -it fire_ops tail -f /app/logs/fire_ops_celery_worker.log

# 查看 Celery Beat 日志
docker exec -it fire_ops tail -f /app/logs/fire_ops_celery_beat.log
```

### 查看错误日志
```bash
# 查看 Web 应用错误日志
docker exec -it fire_ops tail -f /app/logs/fire_ops_webapp_error.log

# 查看 Gunicorn 错误日志
docker exec -it fire_ops tail -f /app/logs/gunicorn_error.log

# 查看 Celery Worker 错误日志
docker exec -it fire_ops tail -f /app/logs/fire_ops_celery_worker_error.log

# 查看 Celery Beat 错误日志
docker exec -it fire_ops tail -f /app/logs/fire_ops_celery_beat_error.log
```

## Gunicorn 配置

### 配置文件说明
项目使用 `gunicorn.conf.py` 配置文件，主要配置项：

- **Workers**: 自动根据CPU核心数设置 (CPU核心数 × 2 + 1)
- **Worker Class**: 使用 `uvicorn.workers.UvicornWorker` 支持异步
- **超时设置**: 30秒超时，2秒keepalive
- **日志**: 访问日志和错误日志分别输出
- **性能优化**: 使用 `/dev/shm` 作为临时目录

### 自定义配置
可以通过环境变量调整：
```bash
docker run -e GUNICORN_WORKERS=8 fire_ops:latest
```

## 环境变量配置

### 必需的环境变量
- `POSTGRES_HOST`: PostgreSQL 数据库主机
- `POSTGRES_PORT`: PostgreSQL 数据库端口
- `POSTGRES_USER`: PostgreSQL 用户名
- `POSTGRES_PASSWORD`: PostgreSQL 密码
- `POSTGRES_DB`: PostgreSQL 数据库名
- `REDIS_HOST`: Redis 主机
- `REDIS_PORT`: Redis 端口

### 可选的环境变量
- `DEBUG`: 调试模式 (默认: False)
- `SECRET_KEY`: 应用密钥
- `AES_KEY`: AES 加密密钥
- `OPENAI_API_KEY`: OpenAI API 密钥
- `OPENAI_BASE_URL`: OpenAI API 基础URL
- `EMBEDDING_MODEL`: 嵌入模型名称
- `VECTOR_DB_TYPE`: 向量数据库类型
- `QDRANT_HOST`: Qdrant 主机
- `QDRANT_PORT`: Qdrant 端口

## Docker Compose 示例

```yaml
version: '3.8'

services:
  fire_ops:
    build:
      context: .
      dockerfile: docker/Dockerfile
    ports:
      - "8000:8000"
    environment:
      - POSTGRES_HOST=postgres
      - POSTGRES_PORT=5432
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=fire_ops
      - REDIS_HOST=redis
      - REDIS_PORT=6379
    volumes:
      - ./logs:/var/log/supervisor
      - ./data:/app/data
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=fire_ops
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

## 故障排除

### 1. 服务启动失败
- 检查环境变量是否正确设置
- 检查数据库和 Redis 连接
- 查看容器日志: `docker logs fire_ops`

### 2. 权限问题
- 确保日志目录权限正确
- 检查数据卷挂载权限

### 3. 端口冲突
- 检查 8000 端口是否被占用
- 修改端口映射: `-p 8001:8000`

### 4. 内存不足
- 增加容器内存限制
- 优化 Celery 并发设置

## 生产环境建议

1. **使用 Docker Compose**: 便于管理多个服务
2. **配置健康检查**: 监控服务状态
3. **设置资源限制**: 防止资源耗尽
4. **配置日志轮转**: 避免日志文件过大
5. **使用外部数据库**: 避免数据丢失
6. **配置反向代理**: 使用 Nginx 或 Traefik
7. **设置监控告警**: 集成 Prometheus 和 Grafana
