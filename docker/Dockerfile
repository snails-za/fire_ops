# 使用 bitnami/python:3.10.11-debian-11-r22 作为基础镜像
FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/bitnami/python:3.10.11-debian-11-r22 as base

# 构建阶段
FROM base as builder

# 安装依赖
RUN set -ex && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bullseye main contrib non-free" > /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bullseye-updates main contrib non-free" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bullseye-backports main contrib non-free" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian-security bullseye-security main contrib non-free" >> /etc/apt/sources.list && \
    apt-get update  && \
    apt-get install -y gcc libffi-dev libssl-dev make libpq-dev  && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY ./app /app
WORKDIR /app
RUN python -m venv venv &&  \
    source venv/bin/activate && \
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 运行阶段
FROM base
RUN set -ex && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bullseye main contrib non-free" > /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bullseye-updates main contrib non-free" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bullseye-backports main contrib non-free" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian-security bullseye-security main contrib non-free" >> /etc/apt/sources.list && \
    apt-get update  && \
    apt-get install -y libpq5 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /app /app
WORKDIR /app
RUN venv/bin/pip freeze
CMD ["venv/bin/gunicorn", "asgi:app", "-b", "0.0.0.0:8000", "-k", "uvicorn.workers.UvicornWorker"]
