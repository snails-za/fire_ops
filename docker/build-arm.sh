#!/bin/sh
cd ..

TIME_NOW=`date +%Y%m%d%H%M`
# 生成镜像
#docker build --no-cache --progress=plain -f docker/Dockerfile -t snail97/fastapi_demo:${TIME_NOW} .
docker build --progress=plain -f docker/Dockerfile-arm -t snail97/fastapi_demo_arm:${TIME_NOW} .
# 打标签
docker tag snail97/fastapi_demo_arm:${TIME_NOW} snail97/fastapi_demo_arm:latest

