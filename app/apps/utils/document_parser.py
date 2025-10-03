"""
文档解析器模块 - 专门负责文档内容提取和解析

该模块提供统一的文档解析接口，支持多种文件格式：
- PDF: PyMuPDFLoader（优先）→ PyPDFLoader → OCR（扫描版PDF）
- DOCX/DOC: Docx2txtLoader
- XLSX/XLS: UnstructuredExcelLoader
- TXT: TextLoader
- MD: UnstructuredMarkdownLoader

技术栈：
- LangChain文档加载器
- OCR引擎（EasyOCR）
- 图像预处理和优化
"""

import os
import shutil

from PIL import Image
# LangChain文档加载器
from langchain_community.document_loaders import (
    PyPDFLoader,
    PyMuPDFLoader,
    Docx2txtLoader,
    TextLoader,
    UnstructuredExcelLoader,
    UnstructuredMarkdownLoader
)
from pdf2image import convert_from_path

from apps.utils.ocr_engines import get_ocr_engine
from config import OCR_ENABLED, OCR_USE_GPU


class DocumentParser:
    """
    文档解析器 - 专门负责文档内容提取
    
    主要功能：
    1. 使用LangChain文档加载器处理多种格式
    2. OCR处理扫描版PDF
    3. 图像预处理和优化
    4. 统一的文档解析接口
    """
    
    def __init__(self):
        """
        初始化文档解析器
        
        配置组件：
        1. OCR引擎：EasyOCR实例（如果启用）
        2. 依赖检查工具
        """
        try:
            # 初始化OCR引擎（如果启用）
            self.ocr_engine = None
            if OCR_ENABLED:
                try:
                    self.ocr_engine = get_ocr_engine(use_gpu=OCR_USE_GPU)
                    print("✅ OCR引擎初始化完成")
                except Exception as e:
                    print(f"⚠️ OCR引擎初始化失败: {str(e)}")
                    self.ocr_engine = None
            
        except Exception as e:
            raise Exception(f"DocumentParser初始化失败: {e}")
    
    async def extract_content(self, file_path: str, file_type: str) -> str:
        """
        提取文档内容的主入口方法
        
        处理流程：
        1. 根据文件类型选择合适的加载器
        2. 使用LangChain加载器提取内容
        3. 如果失败且是PDF，尝试OCR处理
        4. 返回提取的文本内容
        
        Args:
            file_path: 文件路径
            file_type: 文件类型
            
        Returns:
            str: 提取的文本内容
        """
        try:
            if not os.path.exists(file_path):
                raise Exception(f"文件不存在: {file_path}")
            
            print(f"📄 开始解析 {file_type.upper()} 文档: {os.path.basename(file_path)}")
            
            # 根据文件类型选择合适的加载器
            loaders = self._get_loaders(file_path, file_type)
            
            # 加载文档并合并内容
            texts = []
            for loader in loaders:
                try:
                    documents = loader.load()
                    texts.extend(documents)
                except Exception as e:
                    print(f"⚠️ 加载器失败: {str(e)}")
                    continue
            
            if not texts:
                raise Exception("无法加载任何文档内容")
            
            # 合并所有文档内容
            content = "\n\n".join([doc.page_content for doc in texts if doc.page_content.strip()])
            
            if not content.strip():
                raise Exception("文档内容为空")
            
            print(f"✅ 文档解析成功，提取内容长度: {len(content)} 字符")
            return content.strip()
                
        except Exception as e:
            print(f"❌ 文档解析失败: {str(e)}")
            # 如果是PDF且失败，尝试OCR处理
            if file_type == "pdf":
                print("🔄 尝试OCR处理扫描版PDF...")
                try:
                    return await self._extract_pdf_with_ocr(file_path)
                except Exception as ocr_e:
                    raise Exception(f"所有PDF处理方法都失败: LangChain({str(e)}), OCR({str(ocr_e)})")
            else:
                raise Exception(f"文档内容提取失败: {str(e)}")
    
    def _get_loaders(self, file_path: str, file_type: str) -> list:
        """
        根据文件类型获取合适的LangChain加载器
        
        Args:
            file_path: 文件路径
            file_type: 文件类型
            
        Returns:
            list: 加载器列表
        """
        loaders = []
        
        if file_type == "pdf":
            # PDF优先使用PyMuPDFLoader（更快更准确）
            try:
                loaders.append(PyMuPDFLoader(file_path))
            except:
                loaders.append(PyPDFLoader(file_path))
        elif file_type in ["docx", "doc"]:
            loaders.append(Docx2txtLoader(file_path))
        elif file_type in ["xlsx", "xls"]:
            loaders.append(UnstructuredExcelLoader(file_path))
        elif file_type == "txt":
            loaders.append(TextLoader(file_path, encoding='utf-8'))
        elif file_type == "md":
            loaders.append(UnstructuredMarkdownLoader(file_path))
        else:
            raise Exception(f"不支持的文件类型: {file_type}")
        
        return loaders
    
    async def _extract_pdf_with_ocr(self, file_path: str) -> str:
        """
        使用OCR技术提取PDF中的图片文字
        
        包含完整的依赖检查和错误处理
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            str: OCR识别的文本内容
            
        Raises:
            Exception: 当OCR依赖缺失或处理失败时
        """
        try:
            # 检查OCR依赖
            self._check_ocr_dependencies()
            
            # 将PDF转换为图片
            print("🔄 正在将PDF转换为图片...")
            try:
                images = convert_from_path(file_path, dpi=200)  # 降低DPI平衡质量和性能
            except Exception as e:
                if "poppler" in str(e).lower():
                    raise Exception("缺少poppler依赖。请运行: brew install poppler (macOS) 或 apt-get install poppler-utils (Ubuntu)")
                raise Exception(f"PDF转图片失败: {str(e)}")
            
            if not images:
                raise Exception("PDF转换后未获得任何图片页面")
            
            content = ""
            total_pages = len(images)
            successful_pages = 0
            
            print(f"📄 开始OCR处理 {total_pages} 页...")
            
            for page_num, image in enumerate(images, 1):
                try:
                    # 显示处理进度
                    progress = (page_num - 1) / total_pages * 100
                    print(f"🔍 处理第 {page_num}/{total_pages} 页... ({progress:.1f}%)")
                    
                    # 图像预处理
                    processed_image = self._preprocess_image_for_ocr(image)
                    
                    # OCR识别 - 使用已初始化的OCR引擎
                    if self.ocr_engine is None:
                        raise Exception("OCR引擎未初始化")
                    page_text = self.ocr_engine.extract_text(processed_image)

                    if page_text.strip():
                        content += f"\n--- 第 {page_num} 页 (OCR) ---\n"
                        content += page_text.strip() + "\n"
                        successful_pages += 1
                        
                except Exception as page_error:
                    print(f"⚠️ 第 {page_num} 页OCR处理失败: {str(page_error)}")
                    continue
            
            if successful_pages == 0:
                raise Exception("所有页面的OCR处理均失败")
            
            print(f"✅ OCR处理完成，成功处理 {successful_pages}/{total_pages} 页")
            return content.strip()
            
        except Exception as e:
            error_msg = str(e)
            if "tesseract" in error_msg.lower():
                error_msg = "缺少Tesseract OCR引擎。请运行: brew install tesseract (macOS) 或 apt-get install tesseract-ocr (Ubuntu)"
            elif "chi_sim" in error_msg.lower():
                error_msg = "缺少中文语言包。请运行: brew install tesseract-lang (macOS) 或 apt-get install tesseract-ocr-chi-sim (Ubuntu)"
            
            print(f"❌ PDF OCR处理失败: {error_msg}")
            raise Exception(f"OCR处理失败: {error_msg}")
    
    def _check_ocr_dependencies(self):
        """
        检查OCR所需的依赖是否可用
        
        Raises:
            Exception: 当依赖缺失时
        """
        try:
            # 检查poppler工具（PDF转图片需要）
            poppler_path = shutil.which('pdftoppm')
            if not poppler_path:
                raise Exception("缺少poppler工具，请安装: brew install poppler (macOS) 或 sudo apt-get install poppler-utils (Ubuntu)")
            print("✅ OCR依赖检查通过")
        except Exception as e:
            raise e
    
    def _preprocess_image_for_ocr(self, pil_image: Image.Image) -> Image.Image:
        """
        简单的图像预处理，提高OCR识别准确性
        
        Args:
            pil_image: PIL图像对象
            
        Returns:
            Image.Image: 预处理后的图像
        """
        try:
            # 简单的灰度转换
            if pil_image.mode != 'L':
                gray_image = pil_image.convert('L')
            else:
                gray_image = pil_image
            
            # 如果图像太小，稍微放大
            width, height = gray_image.size
            if width < 800 or height < 800:
                scale_factor = max(800 / width, 800 / height)
                new_width = int(width * scale_factor)
                new_height = int(height * scale_factor)
                gray_image = gray_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            return gray_image
            
        except Exception as e:
            print(f"⚠️ 图像预处理出错: {str(e)}")
            # 如果预处理失败，返回原图
            return pil_image


# 全局实例 - 单例模式
try:
    document_parser = DocumentParser()
except Exception as e:
    raise Exception(f"文档解析器初始化失败: {e}")
