"""
文档解析器模块 - 专门负责文档内容提取和解析

该模块提供统一的文档解析接口，支持多种文件格式：
- PDF: PyMuPDFLoader（优先）→ PyPDFLoader → OCR（扫描版PDF）
- DOCX/DOC: Docx2txtLoader
- XLSX/XLS: SimpleExcelLoader（自定义，使用 openpyxl）
- TXT: TextLoader
- MD: UnstructuredMarkdownLoader

技术栈：
- LangChain文档加载器
- openpyxl Excel处理（离线，无网络依赖）
- OCR引擎（EasyOCR）
- 图像预处理和优化
"""

import asyncio
import os
import shutil
from datetime import datetime

import openpyxl
from PIL import Image
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    PyPDFLoader,
    PyMuPDFLoader,
    Docx2txtLoader,
    TextLoader,
    UnstructuredMarkdownLoader
)
from langchain_core.documents import Document
from pdf2image import convert_from_path

from apps.models.document import Document as DocumentModel, DocumentChunk
from apps.utils.ocr_engines import get_ocr_engine
from apps.utils.rag_helper import vector_search
from config import OCR_ENABLED, OCR_USE_GPU, HF_HOME, HF_OFFLINE


class SimpleExcelLoader:
    """
    简单的 Excel 加载器 - 避免 UnstructuredExcelLoader 的 NLTK 依赖
    
    使用 openpyxl 直接读取 Excel，兼容 LangChain 接口
    """

    def __init__(self, file_path: str):
        self.file_path = file_path

    def load(self):
        """加载 Excel 并返回 LangChain Document 列表"""

        try:
            wb = openpyxl.load_workbook(self.file_path, data_only=True, read_only=True)
            documents = []

            for sheet_name in wb.sheetnames:
                sheet = wb[sheet_name]
                rows = []

                for row in sheet.iter_rows(values_only=True):
                    row_values = [str(cell) if cell is not None else "" for cell in row]
                    if any(val.strip() for val in row_values):
                        rows.append("\t".join(row_values))

                if rows:
                    content = f"工作表: {sheet_name}\n\n" + "\n".join(rows)
                    doc = Document(
                        page_content=content,
                        metadata={"source": self.file_path, "sheet_name": sheet_name}
                    )
                    documents.append(doc)

            wb.close()
            return documents

        except Exception as e:
            raise Exception(f"Excel 读取失败: {str(e)}")


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
            except Exception as _:
                loaders.append(PyPDFLoader(file_path))
        elif file_type in ["docx", "doc"]:
            loaders.append(Docx2txtLoader(file_path))
        elif file_type in ["xlsx", "xls"]:
            # 使用自定义加载器，完全避开 UnstructuredExcelLoader 的 NLTK 依赖
            loaders.append(SimpleExcelLoader(file_path))
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

            # 将PDF转换为图片（异步处理，避免阻塞）
            print("🔄 正在将PDF转换为图片...")
            try:
                # 异步处理PDF转图片，避免阻塞
                images = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: convert_from_path(file_path, dpi=200)  # 降低DPI平衡质量和性能
                )
            except Exception as e:
                if "poppler" in str(e).lower():
                    raise Exception(
                        "缺少poppler依赖。请运行: brew install poppler (macOS) 或 apt-get install poppler-utils (Ubuntu)")
                raise Exception(f"PDF转图片失败: {str(e)}")

            if not images:
                raise Exception("PDF转换后未获得任何图片页面")

            content = ""
            total_pages = len(images)
            successful_pages = 0

            print(f"📄 开始OCR处理 {total_pages} 页...")

            # 使用异步处理，避免阻塞主进程
            # 限制并发数量，避免资源耗尽
            semaphore = asyncio.Semaphore(2)  # 最多同时处理2页

            # 添加超时控制，避免单个页面处理时间过长
            TIMEOUT_PER_PAGE = 60  # 每页最多60秒

            async def process_single_page(page_num, image):
                async with semaphore:
                    try:
                        # 显示处理进度
                        progress = (page_num - 1) / total_pages * 100
                        print(f"🔍 处理第 {page_num}/{total_pages} 页... ({progress:.1f}%)")

                        # 图像预处理（快速操作，不需要异步）
                        processed_image = self._preprocess_image_for_ocr(image)

                        # OCR识别 - 使用已初始化的OCR引擎
                        if self.ocr_engine is None:
                            raise Exception("OCR引擎未初始化")

                        # 异步处理OCR，避免阻塞主进程
                        # 使用线程池执行器，让OCR在独立线程中运行
                        # 添加超时控制
                        page_text = await asyncio.wait_for(
                            asyncio.get_event_loop().run_in_executor(
                                None,
                                self.ocr_engine.extract_text,
                                processed_image
                            ),
                            timeout=TIMEOUT_PER_PAGE
                        )

                        # 清理图像资源
                        del processed_image

                        return page_num, page_text, None

                    except asyncio.TimeoutError:
                        print(f"⚠️ 第 {page_num} 页OCR处理超时")
                        return page_num, None, "处理超时"
                    except Exception as page_error:
                        print(f"⚠️ 第 {page_num} 页OCR处理失败: {str(page_error)}")
                        return page_num, None, str(page_error)

            # 创建所有页面的处理任务
            tasks = [process_single_page(page_num, image) for page_num, image in enumerate(images, 1)]

            # 并发处理所有页面，但限制并发数量
            # 使用 as_completed 但保持顺序
            results = {}
            for task in asyncio.as_completed(tasks):
                page_num, page_text, error = await task
                results[page_num] = (page_text, error)

            # 按页面顺序处理结果
            for page_num in range(1, total_pages + 1):
                if page_num in results:
                    page_text, error = results[page_num]
                    if error is None and page_text and page_text.strip():
                        content += f"\n--- 第 {page_num} 页 (OCR) ---\n"
                        content += page_text.strip() + "\n"
                        successful_pages += 1

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
                raise Exception(
                    "缺少poppler工具，请安装: brew install poppler (macOS) 或 sudo apt-get install poppler-utils (Ubuntu)")
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


class DocumentProcessor:
    """
    文档处理器 - 负责文档分块和向量化
    
    主要功能：
    1. 智能文本分块，保持语义完整性
    2. 生成高质量向量嵌入
    3. 与数据库和向量存储同步
    4. 协调文档解析器和向量化流程
    
    处理流程：
    1. 使用DocumentParser提取文档内容
    2. 智能分块处理
    3. 生成向量嵌入
    4. 存储到LangChain向量数据库
    """

    def __init__(self):
        """
        初始化文档处理器
        
        配置组件：
        1. 文本分割器：1000字符块大小，200字符重叠
        2. 文档解析器：独立的DocumentParser实例
        3. LangChain向量存储：自动处理向量化
        """
        try:
            # 配置文本分割器 - 平衡块大小和语义完整性
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,  # 每个文本块的最大字符数
                chunk_overlap=200,  # 块之间的重叠字符数，保持上下文连续性
                length_function=len,  # 使用字符长度计算
            )

            # 配置HuggingFace环境变量
            os.environ["HF_HOME"] = HF_HOME
            os.environ["TRANSFORMERS_CACHE"] = HF_HOME
            os.environ["HF_HUB_CACHE"] = HF_HOME

            if HF_OFFLINE:
                # 离线模式配置
                os.environ["TRANSFORMERS_OFFLINE"] = "1"
                os.environ["HF_HUB_OFFLINE"] = "1"
        except Exception as e:
            raise Exception(f"DocumentProcessor初始化失败: {e}")

    async def process_document(self, document_id: int, file_path: str, file_type: str) -> bool:
        """
        处理文档并生成向量嵌入
        
        处理流程：
        1. 提取文档内容
        2. 智能分块处理
        3. 存储到ChromaDB
        4. 更新数据库状态
        
        Args:
            document_id: 文档ID
            file_path: 文件路径
            file_type: 文件类型
            
        Returns:
            bool: 处理是否成功
        """
        document = None
        try:
            # 1. 更新文档状态为处理中
            document = await DocumentModel.get(id=document_id)
            document.status = "processing"
            await document.save()

            # 2. 提取文档内容
            content = await document_parser.extract_content(file_path, file_type)
            if not content or not content.strip():
                raise Exception("文档内容为空或无法提取")

            # 更新文档内容到数据库
            document.content = content
            await document.save()

            # 3. 智能分块处理
            chunks = self.text_splitter.split_text(content)
            if not chunks:
                raise Exception("文档分块失败")

            # 4. 创建分块记录
            chunk_objects = []
            for i, chunk_text in enumerate(chunks):
                chunk = await DocumentChunk.create(
                    document_id=document_id,
                    chunk_index=i,
                    content=chunk_text,
                    content_length=len(chunk_text),
                    metadata={"chunk_index": i}
                )
                chunk_objects.append(chunk)

            # 5. 存储到向量库
            if len(chunk_objects) > 0:
                # 使用LangChain向量存储添加文档（直接使用已分块的文档）
                metadata = {
                    "filename": document.original_filename or document.filename,
                    "file_type": file_type,
                    "upload_time": document.upload_time.isoformat() if document.upload_time else None
                }

                await vector_search.add_documents_from_chunks(
                    document_id=document_id,
                    chunks=chunks,
                    chunk_objects=chunk_objects,
                    metadata=metadata
                )
            # 7. 更新文档状态为完成并设置处理时间
            document.status = "completed"
            document.process_time = datetime.now()
            await document.save()

            return True

        except Exception as e:
            # 更新文档状态为失败
            if document is None:
                document = await DocumentModel.get(id=document_id)
            document.status = "failed"
            document.error_message = str(e)
            await document.save()

            return False


# 全局实例 - 单例模式
try:
    document_parser = DocumentParser()
    document_processor = DocumentProcessor()
except Exception as e:
    raise Exception(f"文档处理系统初始化失败: {e}")
