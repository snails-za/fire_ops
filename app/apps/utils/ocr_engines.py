"""
EasyOCR引擎适配器

使用EasyOCR进行OCR文本识别，支持中英文等多种语言
"""

from typing import List
from PIL import Image


class OCREngineAdapter:
    """EasyOCR引擎适配器"""
    
    def __init__(self):
        self._init_easyocr()
    
    def _init_easyocr(self):
        """初始化EasyOCR"""
        try:
            import easyocr
        except ImportError:
            self._show_install_guide()
            raise ImportError("EasyOCR未安装")
        
        # 初始化EasyOCR，支持中英文
        self.easy_reader = easyocr.Reader(['ch_sim', 'en'])
        print("✅ EasyOCR引擎初始化完成")
    
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
        import numpy as np
        img_array = np.array(image)
        
        # 使用EasyOCR识别
        results = self.easy_reader.readtext(img_array)
        
        # 提取文本
        texts = []
        for (bbox, text, confidence) in results:
            if confidence > 0.5:  # 只保留高置信度的文本
                texts.append(text)
        
        return '\n'.join(texts)
    
    def _show_install_guide(self):
        """显示安装指导"""
        print("\n❌ EasyOCR 未安装")
        print("📦 安装命令:")
        print("pip install easyocr")
        print("\n💡 或者运行: uv sync")


def get_ocr_engine() -> OCREngineAdapter:
    """获取OCR引擎实例"""
    return OCREngineAdapter()


def test_ocr_engine() -> bool:
    """测试OCR引擎是否可用"""
    try:
        ocr = get_ocr_engine()
        # 创建一个简单的测试图像
        test_image = Image.new('RGB', (100, 50), color='white')
        result = ocr.extract_text(test_image)
        print("✅ EasyOCR引擎测试通过")
        return True
    except Exception as e:
        print(f"❌ EasyOCR引擎测试失败: {str(e)}")
        return False


def check_and_install_dependencies():
    """检查并建议安装缺失的依赖"""
    print("🔍 检查OCR依赖...")
    
    missing_python = []
    missing_system = []
    
    # 检查Python包
    try:
        import easyocr
    except ImportError:
        missing_python.append("easyocr")
    
    # 检查系统依赖
    import shutil
    if not shutil.which('pdftoppm'):  # poppler工具
        missing_system.append("poppler")
    
    # 显示缺失的依赖
    if missing_python:
        print(f"\n❌ 缺失Python包: {', '.join(missing_python)}")
        print("📦 安装命令:")
        for pkg in missing_python:
            print(f"pip install {pkg}")
        print("\n💡 或者运行: uv sync")
    
    if missing_system:
        import platform
        system = platform.system().lower()
        print(f"\n❌ 缺失系统依赖: {', '.join(missing_system)}")
        print("🔧 系统依赖安装命令:")
        
        if system == "darwin":  # macOS
            if "poppler" in missing_system:
                print("brew install poppler")
        elif system == "linux":
            if "poppler" in missing_system:
                print("sudo apt-get install poppler-utils")
        else:
            print("请根据你的操作系统安装相应的系统依赖")
    
    if not missing_python and not missing_system:
        print("✅ 所有OCR依赖都已安装")
        return True
    
    return False


if __name__ == "__main__":
    # 测试EasyOCR引擎
    test_ocr_engine()