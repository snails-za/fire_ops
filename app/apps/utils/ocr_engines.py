"""
免费开源OCR引擎适配器

支持两种免费开源OCR引擎：
1. PaddleOCR - 百度开源，中文优化，准确率高
2. EasyOCR - 简单易用，支持80+语言
"""

from typing import List

from PIL import Image


# 根据配置导入不同的OCR引擎
def _check_import(module_name, package_name=None):
    """检查模块是否可用"""
    try:
        if package_name:
            __import__(package_name)
        else:
            __import__(module_name)
        return True
    except ImportError:
        return False

# 检查OCR引擎可用性
PADDLEOCR_AVAILABLE = _check_import("paddleocr", "paddleocr")
EASYOCR_AVAILABLE = _check_import("easyocr")

from config import OCR_ENGINE


class OCREngineAdapter:
    """OCR引擎适配器"""
    
    def __init__(self, engine: str = None):
        self.engine = engine or OCR_ENGINE
        self._init_engine()
    
    def _init_engine(self):
        """初始化OCR引擎"""
        if self.engine == "paddleocr":
            self._init_paddleocr()
        elif self.engine == "easyocr":
            self._init_easyocr()
        else:
            raise ValueError(f"不支持的OCR引擎: {self.engine}。支持的引擎: paddleocr, easyocr")
    
    
    def _init_paddleocr(self):
        """初始化PaddleOCR"""
        try:
            from paddleocr import PaddleOCR
        except ImportError:
            self._show_install_guide("paddleocr")
            raise ImportError("PaddleOCR未安装")
        
        # 初始化PaddleOCR，尝试使用GPU加速
        import torch
        use_gpu = torch.cuda.is_available()  # 自动检测GPU
        print(f"🔧 PaddleOCR配置: GPU={'启用' if use_gpu else '禁用'}")
        # 使用基础配置避免兼容性问题
        self.paddle_ocr = PaddleOCR(
            use_angle_cls=True, 
            lang='ch', 
            use_gpu=use_gpu
        )
        print("✅ PaddleOCR引擎初始化完成")
    
    def _init_easyocr(self):
        """初始化EasyOCR"""
        try:
            import easyocr
        except ImportError:
            self._show_install_guide("easyocr")
            raise ImportError("EasyOCR未安装")
        
        # 初始化EasyOCR，支持中英文
        self.easy_reader = easyocr.Reader(['ch_sim', 'en'])
        print("✅ EasyOCR引擎初始化完成")
    
    
    def extract_text(self, image: Image.Image) -> str:
        """从图像中提取文本"""
        try:
            if self.engine == "paddleocr":
                return self._extract_with_paddleocr(image)
            elif self.engine == "easyocr":
                return self._extract_with_easyocr(image)
            else:
                raise ValueError(f"不支持的OCR引擎: {self.engine}")
        except Exception as e:
            print(f"❌ {self.engine} OCR处理失败: {str(e)}")
            return ""
    
    
    def _extract_with_paddleocr(self, image: Image.Image) -> str:
        """使用PaddleOCR提取文本"""
        # 转换PIL图像为numpy数组
        import numpy as np
        img_array = np.array(image)
        
        # 使用PaddleOCR识别
        result = self.paddle_ocr.ocr(img_array, cls=True)
        
        # 提取文本
        texts = []
        if result and result[0]:
            for line in result[0]:
                if line and len(line) >= 2:
                    text = line[1][0]  # 提取识别的文本
                    confidence = line[1][1]  # 提取置信度
                    if confidence > 0.5:  # 只保留高置信度的文本
                        texts.append(text)
        
        return '\n'.join(texts)
    
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
    
    def _show_install_guide(self, engine: str):
        """显示安装指导"""
        print(f"\n❌ {engine.upper()} 未安装")
        print("📦 安装命令:")
        
        if engine == "paddleocr":
            print("pip install paddlepaddle paddleocr")
        elif engine == "easyocr":
            print("pip install easyocr")
        
        print("\n💡 或者运行: uv sync")
    
    def _show_system_deps_guide(self, engine: str):
        """显示系统依赖安装指导"""
        import platform
        system = platform.system().lower()
        
        print(f"\n❌ {engine.upper()} 系统依赖未安装")
        print("🔧 系统依赖安装命令:")
        
        if system == "darwin":  # macOS
            print("brew install tesseract tesseract-lang poppler")
        elif system == "linux":
            print("sudo apt-get install tesseract-ocr tesseract-ocr-chi-sim poppler-utils")
        else:
            print("请根据你的操作系统安装相应的系统依赖")
        
        print("\n📋 详细安装指南请查看: OCR_INSTALL.md")


def get_ocr_engine(engine: str = None) -> OCREngineAdapter:
    """获取OCR引擎实例"""
    return OCREngineAdapter(engine)


def list_available_engines() -> List[str]:
    """列出可用的免费开源OCR引擎"""
    engines = []
    
    if PADDLEOCR_AVAILABLE:
        engines.append("paddleocr")
    
    if EASYOCR_AVAILABLE:
        engines.append("easyocr")
    
    return engines


def test_ocr_engine(engine: str) -> bool:
    """测试OCR引擎是否可用"""
    try:
        ocr = get_ocr_engine(engine)
        # 创建一个简单的测试图像
        test_image = Image.new('RGB', (100, 50), color='white')
        result = ocr.extract_text(test_image)
        print(f"✅ {engine} OCR引擎测试通过")
        return True
    except Exception as e:
        print(f"❌ {engine} OCR引擎测试失败: {str(e)}")
        return False


def check_and_install_dependencies():
    """检查并建议安装缺失的依赖"""
    print("🔍 检查OCR依赖...")
    
    missing_python = []
    missing_system = []
    
    # 检查Python包 - 使用动态导入
    if not _check_import("paddleocr", "paddleocr"):
        missing_python.append("paddlepaddle paddleocr")
    if not _check_import("easyocr"):
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
    # 测试所有可用的OCR引擎
    available_engines = list_available_engines()
    print(f"可用的OCR引擎: {available_engines}")
    
    for engine in available_engines:
        test_ocr_engine(engine)
