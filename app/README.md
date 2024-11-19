# FastApi-Demo
本项目是一个基于FastApi的后端项目，主要用于学习FastApi框架。

## 前言

- 环境： Python3.10+
- FastApi版本：0.115.5
- 数据库：Postgresql
- ORM：Tortoise-orm
- 数据库迁移工具： Aerich

## 项目结构

```
fastapi-demo
├── app
│   ├── apps
│   │   ├── __init__.py
│   │   ├── api
│   │   │   ├── __init__.py
│   │   │   form
│   │   │   ├── __init__.py
│   │   │   models
│   │   │   ├── __init__.py
│   │   │   utils
│   │   │   ├── __init__.py
│   static
│   __init__.py
│   config.py
│   asgi.py
│   requirements.txt
│   README.md
```

## 安装依赖并自行修改config配置信息
```shell
pip install -r requirements.txt
```

## 数据库迁移【需手动执行，自动迁移暂未开发】
```shell
# 初始化Aerich 配置
aerich init -t config.TORTOISE_ORM
# 首次迁移【初始化数据库，这一步只需要在第一次迁移时执行。】
aerich init-db
# 生成迁移文件
aerich migrate
# 更新数据库
aerich upgrade
```
![migrate.png](static/images/migrate.png)

## 启动项目
### 1. 使用FastApi自带的命令启动
```shell
# 测试环境
fastapi dev asgi.py
# 生产环境
fastapi run asgi.py
```
### 2. 使用uvicorn启动
```shell
uvicorn app.asgi:app --reload
```
### 3. 使用gunicorn启动
```shell
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.asgi:app
```

## 构建镜像
```shell
sh build.sh
```

## 部署
建议采用docker swarm部署，可以参考部署仓库：[docker-swarm-deploy](https://github.com/snails-za/fastapi_demo_deploy)




