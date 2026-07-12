"""
EasyOCR引擎适配器

使用EasyOCR进行OCR文本识别，支持中英文等多种语言，支持GPU加速
"""

import easyocr
import numpy as np
import torch
from PIL import Image
import os
from config import OCR_MODEL_PATH


class OCREngineAdapter:
    """EasyOCR引擎适配器"""

    def __init__(self, use_gpu: bool = True):
        self.use_gpu = use_gpu
        self._init_easyocr()

    def _init_easyocr(self):
        """初始化EasyOCR"""
        # 确保OCR模型目录存在
        os.makedirs(OCR_MODEL_PATH, exist_ok=True)

        # 检测GPU可用性
        gpu_available = self._check_gpu_availability()
        actual_use_gpu = self.use_gpu and gpu_available

        # 尝试初始化，如果GPU失败则自动降级到CPU
        if actual_use_gpu:
            try:
                print("🚀 尝试启用GPU加速模式")
                print(f"📁 OCR模型路径: {OCR_MODEL_PATH}")
                self.easy_reader = easyocr.Reader(
                    ["ch_sim", "en"], gpu=True, model_storage_directory=OCR_MODEL_PATH
                )
                print("✅ GPU模式初始化成功")
            except Exception as gpu_error:
                print(f"⚠️ GPU模式初始化失败: {str(gpu_error)}")
                print("🔄 自动降级到CPU模式")
                self.easy_reader = easyocr.Reader(
                    ["ch_sim", "en"], gpu=False, model_storage_directory=OCR_MODEL_PATH
                )
                print("✅ CPU模式初始化成功")
        else:
            print("💻 使用CPU模式")
            print(f"📁 OCR模型路径: {OCR_MODEL_PATH}")
            self.easy_reader = easyocr.Reader(
                ["ch_sim", "en"], gpu=False, model_storage_directory=OCR_MODEL_PATH
            )
            print("✅ CPU模式初始化成功")

        print("✅ EasyOCR引擎初始化完成")

    def _check_gpu_availability(self) -> bool:
        """检查GPU是否可用"""
        try:
            if torch.cuda.is_available():
                gpu_count = torch.cuda.device_count()
                gpu_name = torch.cuda.get_device_name(0) if gpu_count > 0 else "Unknown"
                print(f"🎮 检测到 {gpu_count} 个GPU: {gpu_name}")
                return True
            else:
                print("💻 未检测到CUDA GPU，将使用CPU模式")
                return False
        except Exception as e:
            print(f"⚠️ GPU检测失败: {str(e)}，将使用CPU模式")
            return False

    def extract_text(self, image: Image.Image) -> str:
        """从图像中提取文本"""
        try:
            return self._extract_with_easyocr(image)
        except Exception as e:
            print(f"❌ EasyOCR处理失败: {str(e)}")
            return ""

    def _extract_with_easyocr(self, image: Image.Image) -> str:
        """使用EasyOCR提取文本"""
        # 转换PIL图像为numpy数组
        img_array = np.array(image)

        # 使用EasyOCR识别
        results = self.easy_reader.readtext(img_array)

        # 提取文本
        texts = []
        for bbox, text, confidence in results:
            if confidence > 0.5:  # 只保留高置信度的文本
                texts.append(text)

        return "\n".join(texts)


def get_ocr_engine(use_gpu: bool = True) -> OCREngineAdapter:
    """获取OCR引擎实例"""
    return OCREngineAdapter(use_gpu=use_gpu)
