#!/bin/sh
cd ..

TIME_NOW=`date +%Y%m%d%H%M`
# 生成镜像
#docker build --no-cache --progress=plain -f docker/Dockerfile -t snail97/fire-ops:${TIME_NOW} .
docker build -f docker/Dockerfile -t snail97/fire-ops:${TIME_NOW} .
# 打标签
docker tag snail97/fire-ops:${TIME_NOW} snail97/fire-ops:latest

