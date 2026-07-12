import base64
import hashlib
import os
from typing import Optional

from pypinyin import lazy_pinyin


class Base64Util:
    @staticmethod
    def encode(data: str) -> str:
        """对数据进行 Base64 编码"""
        byte_data = data.encode("utf-8")
        encoded_data = base64.b64encode(byte_data)
        return encoded_data.decode("utf-8")

    @staticmethod
    def decode(encoded_data: str) -> str:
        """对 Base64 编码的数据进行解码"""
        byte_data = encoded_data.encode("utf-8")
        decoded_data = base64.b64decode(byte_data)
        return decoded_data.decode("utf-8")


def get_hash(keyword: str) -> str:
    md5 = hashlib.md5()
    md5.update(keyword.encode("utf-8"))
    return md5.hexdigest()


def get_pinyin(name: str) -> str:
    py = lazy_pinyin(name)
    return py[0][0].lower() if py else "#"


def get_local_model_path(model_name: str, cache_folder: str) -> Optional[str]:
    """
    获取本地模型路径

    Args:
        model_name: HuggingFace模型名称
        cache_folder: 缓存文件夹路径

    Returns:
        本地模型路径（如果存在）或None
    """
    # HuggingFace将 '/' 转换为 '--'
    local_model_name = model_name.replace("/", "--")
    local_model_path = os.path.join(cache_folder, f"models--{local_model_name}")

    if os.path.exists(local_model_path):
        # 检查是否有snapshots目录
        snapshots_dir = os.path.join(local_model_path, "snapshots")
        if os.path.exists(snapshots_dir):
            # 获取最新的snapshot
            snapshots = [
                d
                for d in os.listdir(snapshots_dir)
                if os.path.isdir(os.path.join(snapshots_dir, d))
            ]
            if snapshots:
                latest_snapshot = os.path.join(snapshots_dir, snapshots[0])
                return latest_snapshot

        # 如果没有snapshots，直接返回模型目录
        return local_model_path

    return None
