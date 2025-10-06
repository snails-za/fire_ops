# 构建阶段
FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/ubuntu:22.04 AS builder

# 安装依赖
RUN set -ex && \
    echo "deb http://mirrors.tuna.tsinghua.edu.cn/ubuntu/ jammy main restricted universe multiverse" > /etc/apt/sources.list && \
    echo "deb http://mirrors.tuna.tsinghua.edu.cn/ubuntu/ jammy-updates main restricted universe multiverse" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.tuna.tsinghua.edu.cn/ubuntu/ jammy-backports main restricted universe multiverse" >> /etc/apt/sources.list && \
    # echo "deb http://security.ubuntu.com/ubuntu/ jammy-security main restricted universe multiverse" >> /etc/apt/sources.list && \
    apt-get update  && \
    apt-get install -y  ca-certificates curl \
      python3 python3-pip python3-venv python3-distutils \
      gcc make libffi-dev libssl-dev make libpq-dev libpq5 vim ncurses-bin  \
      libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev libgomp1 libglib2.0-0 \
      locales poppler-utils && \
    # 配置中文locale
    echo "zh_CN.UTF-8 UTF-8" >> /etc/locale.gen && \
    locale-gen && \
    update-locale LANG=zh_CN.UTF-8 && \
    pip3 install -i https://pypi.tuna.tsinghua.edu.cn/simple uv && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*


# 运行阶段
FROM builder

# 安装supervisor
RUN pip3 install -i https://pypi.tuna.tsinghua.edu.cn/simple supervisor

COPY ./app /app
WORKDIR /app

RUN uv sync

# 设置 venv 到 PATH
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# 设置中文环境变量
ENV LANG=C.UTF-8
ENV LANGUAGE=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONIOENCODING=utf-8

# 创建supervisor日志目录和应用日志目录
RUN mkdir -p /var/log/supervisor /app/logs /var/run

# 复制supervisor配置文件
COPY ./conf/supervisord.conf /etc/supervisor/supervisord.conf
COPY ./conf/supervisor-services.conf /etc/supervisor/conf.d/fire_ops.conf

# 暴露端口
EXPOSE 8000

# 使用supervisor启动服务
CMD ["supervisord", "-c", "/etc/supervisor/supervisord.conf", "-n"]
