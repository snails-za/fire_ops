#!/usr/bin/env python3
"""
NLTK 数据下载脚本

用于下载 unstructured 库所需的 NLTK 数据包到本地目录，
避免在容器中因网络问题导致的下载失败。

使用方法：
1. 在有网络的环境下运行此脚本
2. 将生成的 nltk_data 目录复制到容器挂载点
3. 在容器启动时挂载该目录到 /app/data/nltk_data
"""

import os
import nltk
from pathlib import Path

# 设置 NLTK 数据下载路径
nltk.set_proxy('http://127.0.0.1:7890')
NLTK_DATA_PATH = "app/nltk_data"
os.environ["NLTK_DATA"] = NLTK_DATA_PATH
nltk.data.path.append(NLTK_DATA_PATH)

# 确保目录存在
Path(NLTK_DATA_PATH).mkdir(parents=True, exist_ok=True)

def download_nltk_data():
    """下载 unstructured 库所需的 NLTK 数据包"""
    
    print("🚀 开始下载 NLTK 数据包...")
    
    # unstructured 库需要的数据包列表
    required_packages = [
        'punkt',           # 句子分割
        'averaged_perceptron_tagger',  # 词性标注
        'maxent_ne_chunker',          # 命名实体识别
        'words',           # 词汇表
        'stopwords',       # 停用词
    ]
    
    downloaded_packages = []
    failed_packages = []
    
    for package in required_packages:
        try:
            print(f"📦 正在下载 {package}...")
            nltk.download(package, download_dir=NLTK_DATA_PATH, quiet=False)
            downloaded_packages.append(package)
            print(f"✅ {package} 下载成功")
        except Exception as e:
            print(f"❌ {package} 下载失败: {str(e)}")
            failed_packages.append(package)
    
    print("\n" + "="*50)
    print("📊 下载结果汇总:")
    print(f"✅ 成功下载: {len(downloaded_packages)} 个包")
    for package in downloaded_packages:
        print(f"   - {package}")
    
    if failed_packages:
        print(f"❌ 下载失败: {len(failed_packages)} 个包")
        for package in failed_packages:
            print(f"   - {package}")
    else:
        print("🎉 所有数据包下载完成！")
    
    print(f"\n📁 数据包位置: {os.path.abspath(NLTK_DATA_PATH)}")
    print("\n📋 下一步操作:")
    print("1. 将 nltk_data 目录复制到你的容器挂载目录")
    print("2. 在 docker-compose.yml 或启动命令中添加挂载:")
    print("   volumes:")
    print("     - ./nltk_data:/app/data/nltk_data")
    print("3. 重启容器")

if __name__ == "__main__":
    download_nltk_data()
