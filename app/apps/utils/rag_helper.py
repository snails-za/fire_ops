"""
RAG (Retrieval-Augmented Generation) 系统核心模块

该模块包含三个主要组件：
1. DocumentProcessor: 文档处理器，负责文档分块和向量化
2. VectorSearch: 向量搜索引擎，基于Chroma数据库进行语义相似度搜索
3. RAGGenerator: RAG生成器，集成LangChain和OpenAI进行智能问答

技术栈：
- 文档解析: 独立的DocumentParser模块
- 文本分割: LangChain RecursiveCharacterTextSplitter
- 向量化: Sentence Transformers
- 向量存储: ChromaDB
- 智能问答: LangChain + OpenAI GPT

架构说明：
- 文档解析功能已拆分到独立的document_parser模块
- 本模块专注于向量化、搜索和生成功能
- 通过依赖注入的方式使用文档解析器
- 现在支持LangChain集成，提供更强大的文档处理能力
"""

import os
import traceback
from typing import List, Dict, Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document

from config import (
    OPENAI_API_KEY, OPENAI_BASE_URL, CHROMA_PERSIST_DIRECTORY,
    CHROMA_COLLECTION, EMBEDDING_MODEL, HF_HOME, HF_OFFLINE,
    SIMILARITY_THRESHOLD, CHUNK_SIZE, CHUNK_OVERLAP
)
from apps.utils.common import get_local_model_path
from apps.models.document import Document as DocumentModel, DocumentChunk


class VectorStore:
    """
    向量搜索引擎 - 基于ChromaDB的语义相似度搜索
    
    功能：
    1. 文档向量化和存储
    2. 语义相似度搜索
    3. 文档删除
    4. 自动向量化处理
    """

    def __init__(self):
        """
        初始化向量搜索引擎
        """
        try:
            # 配置HuggingFace环境
            os.environ["HF_HOME"] = HF_HOME
            os.environ["TRANSFORMERS_CACHE"] = HF_HOME
            os.environ["HF_HUB_CACHE"] = HF_HOME

            if HF_OFFLINE:
                os.environ["TRANSFORMERS_OFFLINE"] = "1"
                os.environ["HF_HUB_OFFLINE"] = "1"

            # 关闭Chroma遥测
            os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")
            os.environ.setdefault("CHROMA_TELEMETRY", "false")

            # 初始化向量嵌入模型（与DocumentProcessor使用相同模型）
            local_model_path = get_local_model_path(EMBEDDING_MODEL, HF_HOME)

            if local_model_path and HF_OFFLINE:
                self.embeddings = HuggingFaceEmbeddings(
                    model_name=local_model_path,
                    model_kwargs={'device': 'cpu'},
                    encode_kwargs={'normalize_embeddings': True}
                )
            else:
                self.embeddings = HuggingFaceEmbeddings(
                    model_name=EMBEDDING_MODEL,
                    cache_folder=HF_HOME,
                    model_kwargs={'device': 'cpu'},
                    encode_kwargs={'normalize_embeddings': True}
                )

            # 初始化ChromaDB向量存储
            self.vectorstore = Chroma(
                collection_name=CHROMA_COLLECTION,
                embedding_function=self.embeddings,
                persist_directory=CHROMA_PERSIST_DIRECTORY,
            )

        except Exception as e:
            raise Exception(f"VectorSearch初始化失败: {e}")

    async def add_documents_from_chunks(self, document_id: int, chunks: List[str], chunk_objects: List,
                                        metadata: Dict[str, Any] = None) -> List[str]:
        """
        从已分块的文档添加到向量存储
        
        Args:
            document_id: 文档ID
            chunks: 已分块的文本列表
            chunk_objects: 已创建的DocumentChunk对象列表
            metadata: 文档元数据
            
        Returns:
            List[str]: 添加的文档块ID列表
        """
        try:
            if not chunks or not chunk_objects:
                raise Exception("文档块为空")

            # 创建LangChain文档对象
            documents = []
            chunk_ids = []

            for i, (chunk_text, chunk_obj) in enumerate(zip(chunks, chunk_objects)):
                # 创建LangChain文档对象
                doc_metadata = {
                    "document_id": document_id,
                    "chunk_id": chunk_obj.id,
                    "chunk_index": i,
                    "source": metadata.get("filename",
                                           f"document_{document_id}") if metadata else f"document_{document_id}",
                }

                langchain_doc = Document(
                    page_content=chunk_text,
                    metadata=doc_metadata
                )

                documents.append(langchain_doc)
                chunk_ids.append(str(chunk_obj.id))

            # 批量添加到向量存储
            if documents:
                self.vectorstore.add_documents(documents)

            return chunk_ids

        except Exception as e:
            raise Exception(f"添加文档到向量存储失败: {e}")

    async def search_similar_documents(self, query: str, top_k: int = 5, use_threshold: bool = True) -> List[
        Dict[str, Any]]:
        """
        搜索语义相似的文档
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            use_threshold: 是否使用相似度阈值过滤
            
        Returns:
            List[Dict]: 相似文档列表
        """
        try:
            # 使用LangChain进行相似度搜索，获取更多结果以便过滤
            results = self.vectorstore.similarity_search_with_score(
                query, k=top_k  # 获取更多结果以便过滤
            )

            # 转换为标准格式
            all_results = []
            filtered_results = []
            
            for doc, distance in results:
                # 计算相似度，确保不为负
                similarity = max(0.0, 1.0 - distance)

                # 从metadata获取信息
                metadata = doc.metadata
                document_id = metadata.get('document_id')
                chunk_id = metadata.get('chunk_id')

                if document_id and chunk_id:
                    try:
                        # 获取数据库中的文档和块信息
                        document = await DocumentModel.get_or_none(id=document_id)
                        chunk = await DocumentChunk.get_or_none(id=chunk_id)

                        if document and chunk:
                            result_item = {
                                'document': document,
                                'chunk': chunk,
                                'similarity': similarity,
                                'metadata': metadata,
                                'above_threshold': similarity >= SIMILARITY_THRESHOLD
                            }
                            
                            all_results.append(result_item)
                            
                            # 如果使用阈值过滤，只保留相似度大于阈值的结果
                            if use_threshold and similarity >= SIMILARITY_THRESHOLD:
                                filtered_results.append(result_item)
                    except Exception as e:
                        print(f"处理搜索结果项失败 (chunk_id: {metadata.get('chunk_id', 'unknown')}): {e}")
                        continue

            # 选择返回结果
            if filtered_results:
                # 有超过阈值的结果，返回过滤后的结果
                filtered_results.sort(key=lambda x: x['similarity'], reverse=True)
                return filtered_results[:top_k]
            elif all_results:
                # 没有超过阈值的结果，返回所有结果（降级处理）
                all_results.sort(key=lambda x: x['similarity'], reverse=True)
                return all_results[:min(top_k, 3)]  # 最多返回3个结果
            else:
                return []

        except Exception as e:
            print(f"搜索相似文档失败: {e}")
            return []

    async def delete_document(self, document_id: int):
        """
        删除指定文档的所有向量数据
        
        Args:
            document_id: 文档ID
        """
        try:
            # 直接使用ChromaDB客户端删除，这是最可靠的方法
            # 通过metadata条件删除指定文档的所有向量
            self.vectorstore._collection.delete(where={"document_id": document_id})
            print(f"✅ 成功删除文档 {document_id} 的向量数据")

        except Exception as e:
            raise Exception(f"删除文档 {document_id} 向量数据失败: {e}")

    async def search_similar_chunks_with_mmr(self, query: str, top_k: int = 5,
                                              use_threshold: bool = True) -> List[Dict[str, Any]]:
        """
        使用MMR算法搜索语义相似的文档块（兼容性方法）
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            use_threshold: 是否使用相似度阈值过滤

        Returns:
            List[Dict]: 相似文档块列表
        """
        # 使用改进的搜索逻辑，确保总是有结果返回
        return await self.search_similar_documents(
            query=query,
            top_k=top_k,
            use_threshold=use_threshold
        )


class RAGGenerator:
    """
    RAG生成器 - 检索增强生成系统
    
    主要功能：
    1. 集成向量搜索和LLM生成
    2. 基于检索到的文档内容生成智能回答
    3. 支持多种回答模式（LLM智能回答 / 简单回答）
    4. 提供上下文感知的问答体验
    """

    def __init__(self):
        """
        初始化RAG生成器
        
        组件：
        1. LangChain向量存储: 向量搜索引擎
        2. LangChain + OpenAI: 智能问答链（可选）
        3. 备用简单回答模式
        """
        try:
            # 使用LangChain向量存储
            self.vector_search = VectorStore()

            # 初始化LLM组件
            self.llm = None
            self.chain = None
            self.llm_available = False

            # 检查OpenAI配置并初始化LLM
            if OPENAI_API_KEY and OPENAI_API_KEY.strip():
                try:
                    # 创建OpenAI客户端
                    self.llm = ChatOpenAI(
                        api_key=OPENAI_API_KEY,
                        base_url=OPENAI_BASE_URL,
                        temperature=0.1,  # 较低的温度确保回答的一致性
                        model="gpt-3.5-turbo",
                        max_tokens=2000  # 限制回答长度
                    )

                    # 创建系统提示模板
                    system_template = """你是一个专业的文档问答助手。请基于提供的文档内容准确回答用户的问题。

回答要求：
1. 严格基于提供的文档内容回答，不要添加文档中没有的信息
2. 如果文档中没有相关信息，请明确说明"根据提供的文档内容，无法找到相关信息"
3. 回答要准确、详细且有条理，使用清晰的段落结构：
   - 使用标题和子标题组织内容
   - 重要信息用**粗体**标记
   - 使用项目符号(•)或数字列表展示要点
   - 每个段落专注一个主题，段落间留空行
   - 复杂内容使用表格或结构化格式
4. 可以引用具体的文档名称和关键内容片段，格式：「文档名：具体内容」
5. 如果有多个文档提供了相关信息，请综合分析并标明信息来源
6. 用中文回答，语言要专业但易懂，适当使用emoji增强可读性

提供的文档内容：
{context}"""

                    human_template = "问题：{question}"

                    # 创建聊天提示模板
                    chat_prompt = ChatPromptTemplate([
                        ("system", system_template),
                        ("human", human_template),
                    ])

                    # 创建输出解析器
                    output_parser = StrOutputParser()

                    # 创建LangChain处理链
                    self.chain = chat_prompt | self.llm | output_parser
                    self.llm_available = True

                except Exception:
                    self.llm = None
                    self.chain = None
                    self.llm_available = False
            else:
                self.llm_available = False

        except Exception as e:
            raise Exception(f"RAGGenerator初始化失败: {e}")

    async def generate_answer(self, query: str, context_chunks: List[Dict[str, Any]]) -> str:
        """
        基于检索到的文档内容生成智能回答
        
        回答策略：
        1. 优先使用LLM智能回答（如果可用）
        2. 降级到简单回答模式（备用方案）
        3. 提供上下文信息和来源引用
        
        Args:
            query: 用户问题
            context_chunks: 检索到的相关文档块
            
        Returns:
            str: 生成的回答
        """
        try:
            # 检查是否有相关文档
            if not context_chunks:
                return "抱歉，没有找到相关的文档内容来回答您的问题。请确保已上传相关文档，或尝试使用不同的关键词重新提问。"

            # 构建上下文信息
            context_parts = []
            for i, chunk in enumerate(context_chunks, 1):
                # 处理不同的结果格式
                if chunk.get('document') and chunk.get('chunk'):
                    doc_name = chunk['document'].original_filename or chunk['document'].filename
                    content = chunk['chunk'].content
                else:
                    # 使用备用格式
                    doc_name = chunk.get('metadata', {}).get('source', '未知文档')
                    content = chunk.get('content', '无内容')
                
                similarity = chunk['similarity']

                # 格式化文档片段
                context_part = f"""文档 {i}: {doc_name}
相似度: {similarity:.2f}
内容: {content}"""
                context_parts.append(context_part)

            context = "\n\n" + "=" * 50 + "\n\n".join(context_parts)

            # 选择回答模式
            if self.llm_available and self.chain:
                try:
                    answer = await self._llm_answer(query, context)

                    # 不再自动添加来源信息，由前端决定是否显示
                    return answer

                except Exception:
                    return self._simple_answer(query, context_chunks)
            else:
                return self._simple_answer(query, context_chunks)

        except Exception as e:
            return f"抱歉，生成回答时出现错误: {str(e)}"

    async def generate_answer_stream(self, query: str, context_chunks: List[Dict[str, Any]]):
        """
        流式生成回答
        
        Args:
            query: 用户问题
            context_chunks: 文档上下文块列表
            
        Yields:
            str: 流式生成的文本块
        """
        try:
            # 构建上下文
            context_parts = []
            for i, chunk in enumerate(context_chunks, 1):
                # 直接使用数据结构
                doc_name = chunk['document'].original_filename or chunk['document'].filename
                content = chunk['chunk'].content
                context_parts.append(f"文档{i}: {doc_name}\n内容: {content}")

            context = "\n\n" + "=" * 50 + "\n\n".join(context_parts)

            # 选择回答模式
            if self.llm_available and self.chain:
                try:
                    async for chunk in self._llm_answer_stream(query, context):
                        yield chunk
                except Exception as e:
                    print(f"LLM流式生成失败: {e}")
                    # 降级到简单回答
                    simple_answer = self._simple_answer(query, context_chunks)
                    yield simple_answer
            else:
                # 非LLM模式，直接返回简单回答
                simple_answer = self._simple_answer(query, context_chunks)
                yield simple_answer

        except Exception as e:
            yield f"抱歉，生成回答时出现错误: {str(e)}"

    async def _llm_answer_stream(self, query: str, context: str):
        """
        使用LangChain链式流式生成智能回答
        
        Args:
            query: 用户问题
            context: 文档上下文
            
        Yields:
            str: 流式生成的文本块
        """
        try:
            # 使用已经创建好的chain进行流式调用
            if self.chain:
                async for chunk in self.chain.astream({
                    "question": query,
                    "context": context
                }):
                    if chunk:
                        yield chunk
            else:
                raise Exception("LangChain处理链未初始化")

        except Exception as e:
            traceback.print_exc()
            raise Exception(f"LLM链式流式调用失败: {str(e)}")

    async def _llm_answer(self, query: str, context: str) -> str:
        """
        使用LLM生成智能回答
        
        Args:
            query: 用户问题
            context: 文档上下文
            
        Returns:
            str: LLM生成的回答
        """
        try:
            # 调用LangChain处理链
            response = await self.chain.ainvoke({
                "question": query,
                "context": context
            })

            if not response or not response.strip():
                raise Exception("LLM返回空回答")

            return response.strip()

        except Exception as e:
            raise Exception(f"LLM调用失败: {str(e)}")

    def _simple_answer(self, query: str, context_chunks: List[Dict[str, Any]]) -> str:
        """
        简单回答模式 - 基于关键词匹配的备用方案
        
        Args:
            query: 用户问题
            context_chunks: 相关文档块
            
        Returns:
            str: 简单模式生成的回答
        """
        try:
            if not context_chunks:
                return "抱歉，没有找到相关的文档内容来回答您的问题。"

            # 获取最相关的文档片段
            best_chunk = context_chunks[0]
            document_name = best_chunk['document'].original_filename or best_chunk['document'].filename
            content = best_chunk['chunk'].content
            similarity = best_chunk['similarity']

            # 构建简单回答（不包含参考来源）
            answer = f"""基于文档《{document_name}》中的相关内容：

{content}

💡 **提示**：当前使用简单回答模式。配置OpenAI API Key后可获得更智能的回答。"""

            return answer

        except Exception:
            return "抱歉，生成回答时出现错误。"

    def _build_sources_info(self, context_chunks: List[Dict[str, Any]]) -> str:
        """
        构建来源信息
        
        Args:
            context_chunks: 文档块列表
            
        Returns:
            str: 格式化的来源信息
        """
        try:
            sources = []
            for i, chunk in enumerate(context_chunks, 1):
                doc_name = chunk['document'].original_filename or chunk['document'].filename
                similarity = chunk['similarity']
                sources.append(f"• {doc_name} (相似度: {similarity:.1%})")

            sources_text = "\n".join(sources)
            return f"""---
📋 **参考来源**：
{sources_text}

💡 基于 {len(context_chunks)} 个相关文档片段生成此回答"""

        except Exception:
            return "---\n📋 **参考来源**：信息获取失败"


# 全局实例 - 单例模式，确保整个应用使用相同的实例
try:
    # 使用LangChain向量存储
    vector_search = VectorStore()
    print("✅ 使用LangChain向量存储")

    # RAG生成器实例
    rag_generator = RAGGenerator()

except Exception as e:
    raise Exception(f"RAG系统初始化失败: {e}")
