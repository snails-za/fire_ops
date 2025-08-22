# 构建阶段
FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/ubuntu:22.04 AS builder

# 安装依赖
RUN set -ex && \
    echo "deb http://mirrors.tuna.tsinghua.edu.cn/ubuntu-ports/ jammy main restricted universe multiverse" > /etc/apt/sources.list && \
    echo "deb http://mirrors.tuna.tsinghua.edu.cn/ubuntu-ports/ jammy-updates main restricted universe multiverse" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.tuna.tsinghua.edu.cn/ubuntu-ports/ jammy-backports main restricted universe multiverse" >> /etc/apt/sources.list && \
    # echo "deb http://security.ubuntu.com/ubuntu-ports/ jammy-security main restricted universe multiverse" >> /etc/apt/sources.list && \
    apt-get update  && \
    apt-get install -y  ca-certificates curl \
      python3 python3-pip python3-venv python3-distutils \
      gcc make libffi-dev libssl-dev make libpq-dev libpq5 vim ncurses-bin  && \
    pip3 install -i https://pypi.tuna.tsinghua.edu.cn/simple uv && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*


# 运行阶段
FROM builder

COPY ./app /app
WORKDIR /app

RUN uv sync

# 设置 venv 到 PATH
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# 暴露端口
EXPOSE 8000
CMD ["gunicorn", "asgi:app", "-b", "0.0.0.0:8000", "-k", "uvicorn.workers.UvicornWorker"]
