import os
import uuid
from typing import List, Dict, Any

import chromadb
import openpyxl
import pypdf
from chromadb.config import Settings as ChromaSettings
from docx import Document as DocxDocument
from langchain.text_splitter import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

from apps.models.document import Document as DocumentModel, DocumentChunk
from config import CHROMA_PERSIST_DIRECTORY, CHROMA_COLLECTION, EMBEDDING_MODEL, HF_HOME, HF_OFFLINE


class DocumentProcessor:
    """文档处理器"""
    
    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
        os.environ.setdefault("HF_HOME", HF_HOME)
        if HF_OFFLINE:
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
        # 关闭 Chroma 遥测（避免 ClientCreateCollectionEvent 报错）
        os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")
        os.environ.setdefault("CHROMA_TELEMETRY", "false")
        # 优先本地缓存的 HuggingFace 模型
        self.embedding_model = SentenceTransformer(EMBEDDING_MODEL, cache_folder=HF_HOME)
        # 初始化 Chroma 客户端
        os.makedirs(CHROMA_PERSIST_DIRECTORY, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIRECTORY, settings=ChromaSettings(anonymized_telemetry=False))
        self.collection = self.chroma_client.get_or_create_collection(name=CHROMA_COLLECTION, metadata={"hnsw:space": "cosine"})
        
    async def process_document(self, document_id: int, file_path: str, file_type: str) -> bool:
        """处理文档并生成向量"""
        try:
            # 更新文档状态为处理中
            document = await DocumentModel.get(id=document_id)
            document.status = "processing"
            await document.save()
            
            # 提取文档内容
            content = await self._extract_content(file_path, file_type)
            if not content:
                raise Exception("无法提取文档内容")
            
            # 更新文档内容
            document.content = content
            await document.save()
            
            # 分割文档
            chunks = self.text_splitter.split_text(content)
            
            # 创建分块记录
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
            
            # 生成向量嵌入
            embeddings = self.embedding_model.encode(chunks)
            
            # 存储向量至 Chroma（作为唯一事实来源）
            ids = []
            metadatas = []
            vectors = []
            for i, (chunk, embedding) in enumerate(zip(chunk_objects, embeddings)):
                vector_id = f"doc_{document_id}_chunk_{i}_{uuid.uuid4().hex[:8]}"
                ids.append(vector_id)
                metadatas.append({
                    "document_id": document_id,
                    "chunk_id": chunk.id,
                    "chunk_index": i,
                })
                vectors.append(embedding.tolist())
            if ids:
                self.collection.add(ids=ids, embeddings=vectors, metadatas=metadatas)
            
            # 更新文档状态为完成
            document.status = "completed"
            document.process_time = document.process_time
            await document.save()
            
            return True
            
        except Exception as e:
            # 更新文档状态为失败
            document = await DocumentModel.get(id=document_id)
            document.status = "failed"
            document.error_message = str(e)
            await document.save()
            return False
    
    async def _extract_content(self, file_path: str, file_type: str) -> str:
        """根据文件类型提取内容"""
        try:
            if file_type == "pdf":
                return await self._extract_pdf_content(file_path)
            elif file_type in ["docx", "doc"]:
                return await self._extract_docx_content(file_path)
            elif file_type in ["xlsx", "xls"]:
                return await self._extract_excel_content(file_path)
            elif file_type == "txt":
                return await self._extract_txt_content(file_path)
            else:
                raise Exception(f"不支持的文件类型: {file_type}")
        except Exception as e:
            raise Exception(f"提取文档内容失败: {str(e)}")
    
    async def _extract_pdf_content(self, file_path: str) -> str:
        """提取PDF内容"""
        content = ""
        with open(file_path, 'rb') as file:
            pdf_reader = pypdf.PdfReader(file)
            for page in pdf_reader.pages:
                content += page.extract_text() + "\n"
        return content
    
    async def _extract_docx_content(self, file_path: str) -> str:
        """提取DOCX内容"""
        doc = DocxDocument(file_path)
        content = ""
        for paragraph in doc.paragraphs:
            content += paragraph.text + "\n"
        return content
    
    async def _extract_excel_content(self, file_path: str) -> str:
        """提取Excel内容"""
        workbook = openpyxl.load_workbook(file_path)
        content = ""
        for sheet_name in workbook.sheetnames:
            sheet = workbook[sheet_name]
            content += f"工作表: {sheet_name}\n"
            for row in sheet.iter_rows(values_only=True):
                row_text = "\t".join([str(cell) if cell is not None else "" for cell in row])
                content += row_text + "\n"
        return content
    
    async def _extract_txt_content(self, file_path: str) -> str:
        """提取TXT内容"""
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()


class VectorSearch:
    """向量搜索（Chroma 优先）"""
    
    def __init__(self):
        os.environ.setdefault("HF_HOME", HF_HOME)
        if HF_OFFLINE:
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
        # 关闭 Chroma 遥测（避免 ClientCreateCollectionEvent 报错）
        os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")
        os.environ.setdefault("CHROMA_TELEMETRY", "false")
        self.embedding_model = SentenceTransformer(EMBEDDING_MODEL, cache_folder=HF_HOME)
        self.chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIRECTORY, settings=ChromaSettings(anonymized_telemetry=False))
        self.collection = self.chroma_client.get_or_create_collection(name=CHROMA_COLLECTION, metadata={"hnsw:space": "cosine"})
    
    async def search_similar_chunks(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """搜索相似文档块"""
        # 生成查询向量
        query_embedding = self.embedding_model.encode([query])[0]
        
        # 优先从 Chroma 检索
        results = self.collection.query(query_embeddings=[query_embedding.tolist()], n_results=top_k)
        similarities = []
        ids = results.get('ids', [[]])[0]
        metadatas = results.get('metadatas', [[]])[0]
        distances = results.get('distances', [[]])[0] or []
        for idx, meta in zip(ids, metadatas):
            # 从数据库补齐 chunk 与 document 信息
            chunk = await DocumentChunk.get_or_none(id=meta.get('chunk_id')).prefetch_related('document')
            if not chunk:
                continue
            similarity = 1 - float(distances[ids.index(idx)]) if distances else 0.0
            similarities.append({
                'vector': None,
                'similarity': similarity,
                'chunk': chunk,
                'document': chunk.document
            })
        return similarities

    async def delete_document_vectors(self, document_id: int):
        """删除某文档在 Chroma 中的所有向量"""
        # 通过 metadata 删除
        self.collection.delete(where={"document_id": document_id})

    async def count_vectors(self) -> int:
        """统计向量总量（Chroma 集合）"""
        try:
            info = self.collection.count()
            return int(info) if isinstance(info, (int, float)) else 0
        except Exception:
            return 0


class RAGGenerator:
    """RAG生成器"""
    
    def __init__(self):
        self.vector_search = VectorSearch()
    
    async def generate_answer(self, query: str, context_chunks: List[Dict[str, Any]]) -> str:
        """基于上下文生成答案"""
        # 构建上下文
        context = "\n\n".join([
            f"文档: {chunk['document'].filename}\n内容: {chunk['chunk'].content}"
            for chunk in context_chunks
        ])
        
        # 构建提示词
        prompt = f"""
基于以下文档内容回答问题：

文档内容：
{context}

问题：{query}

请基于上述文档内容提供准确、详细的回答。如果文档中没有相关信息，请说明无法找到相关信息。
"""
        
        # 这里可以集成OpenAI或其他LLM
        # 暂时返回简单的基于关键词的回答
        return self._simple_answer(query, context_chunks)
    
    def _simple_answer(self, query: str, context_chunks: List[Dict[str, Any]]) -> str:
        """简单的基于关键词的回答"""
        if not context_chunks:
            return "抱歉，没有找到相关的文档内容来回答您的问题。"
        
        # 提取最相关的文档信息
        best_chunk = context_chunks[0]
        document_name = best_chunk['document'].filename
        content = best_chunk['chunk'].content
        
        return f"根据文档《{document_name}》中的相关内容：\n\n{content}\n\n这个回答基于相似度 {best_chunk['similarity']:.2f} 的相关文档片段。"


# 全局实例
document_processor = DocumentProcessor()
vector_search = VectorSearch()
rag_generator = RAGGenerator()
