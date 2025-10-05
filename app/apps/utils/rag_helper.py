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
"""

import os
import traceback
import numpy as np
from typing import List, Dict, Any

import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from sentence_transformers import SentenceTransformer

from apps.models.document import DocumentChunk
from apps.utils.common import get_local_model_path
from config import (
    CHROMA_PERSIST_DIRECTORY, CHROMA_COLLECTION, EMBEDDING_MODEL,
    HF_HOME, HF_OFFLINE, OPENAI_API_KEY, OPENAI_BASE_URL, SIMILARITY_THRESHOLD
)


class VectorSearch:
    """
    向量搜索引擎 - 基于ChromaDB的语义相似度搜索
    
    主要功能：
    1. 语义相似度搜索
    2. 向量数据管理
    3. 搜索结果排序和过滤
    4. 与数据库数据关联
    """
    
    def __init__(self):
        """
        初始化向量搜索引擎
        
        配置组件：
        1. 向量嵌入模型（与DocumentProcessor保持一致）
        2. ChromaDB客户端和集合
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
                self.embedding_model = SentenceTransformer(local_model_path)
            else:
                self.embedding_model = SentenceTransformer(
                    EMBEDDING_MODEL, 
                    cache_folder=HF_HOME
                )
            
            # 初始化ChromaDB客户端
            self.chroma_client = chromadb.PersistentClient(
                path=CHROMA_PERSIST_DIRECTORY, 
                settings=ChromaSettings(anonymized_telemetry=False)
            )
            self.collection = self.chroma_client.get_or_create_collection(
                name=CHROMA_COLLECTION, 
                metadata={"hnsw:space": "cosine"}
            )
            
        except Exception as e:
            raise Exception(f"VectorSearch初始化失败: {e}")
    
    async def search_similar_chunks(self, query: str, top_k: int = 5, use_threshold: bool = True) -> List[Dict[str, Any]]:
        """
        搜索语义相似的文档块
        
        搜索流程：
        1. 将查询文本转换为向量
        2. 在ChromaDB中进行相似度搜索
        3. 从数据库获取完整的文档和块信息
        4. 计算相似度分数并排序
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            use_threshold: 是否使用相似度阈值过滤
            
        Returns:
            List[Dict]: 相似文档块列表，包含文档、块和相似度信息
        """
        try:
            if not query or not query.strip():
                return []
            
            # 1. 生成查询向量
            query_embedding = self.embedding_model.encode([query.strip()])[0]
            
            # 2. 在ChromaDB中搜索相似向量
            results = self.collection.query(
                query_embeddings=[query_embedding.tolist()], 
                n_results=min(top_k, 20)  # 限制最大搜索数量
            )
            
            # 3. 解析搜索结果
            ids = results.get('ids', [[]])[0]
            metadatas = results.get('metadatas', [[]])[0]
            distances = results.get('distances', [[]])[0] or []
            
            # 4. 从数据库获取完整信息并构建结果
            all_similarities = []  # 存储所有结果
            filtered_similarities = []  # 存储过滤后的结果
            
            for i, (vector_id, metadata) in enumerate(zip(ids, metadatas)):
                try:
                    # 获取文档块信息
                    chunk_id = metadata.get('chunk_id')
                    if not chunk_id:
                        continue
                    
                    chunk = await DocumentChunk.get_or_none(id=chunk_id)
                    if not chunk:
                        continue
                    
                    # 获取关联的文档
                    document = await chunk.document
                    if not document:
                        continue
                    
                    # 计算相似度分数（距离转换为相似度）
                    distance = distances[i] if i < len(distances) else 1.0
                    similarity = max(0.0, 1.0 - float(distance))
                    
                    result_item = {
                        'vector_id': vector_id,
                        'similarity': similarity,
                        'chunk': chunk,
                        'document': document,
                        'metadata': metadata,
                        'above_threshold': similarity >= SIMILARITY_THRESHOLD
                    }
                    
                    all_similarities.append(result_item)
                    
                    # 如果使用阈值过滤，只保留相似度大于阈值的结果
                    if not use_threshold or similarity >= SIMILARITY_THRESHOLD:
                        filtered_similarities.append(result_item)
                    
                except Exception as e:
                    print(f"处理搜索结果项失败 (chunk_id: {metadata.get('chunk_id', 'unknown')}): {e}")
                    continue
            
            # 5. 智能选择返回结果
            if use_threshold and filtered_similarities:
                # 有超过阈值的结果，返回过滤后的结果
                filtered_similarities.sort(key=lambda x: x['similarity'], reverse=True)
                return filtered_similarities[:top_k]
            elif use_threshold and not filtered_similarities and all_similarities:
                # 没有超过阈值的结果，但有搜索结果，返回最相似的几个并标记
                all_similarities.sort(key=lambda x: x['similarity'], reverse=True)
                # 取前几个最相似的结果，但标记为低相似度
                return all_similarities[:min(top_k, 3)]  # 最多返回3个低相似度结果
            else:
                # 不使用阈值过滤，返回所有结果
                all_similarities.sort(key=lambda x: x['similarity'], reverse=True)
                return all_similarities[:top_k]
            
        except Exception as e:
            print(f"搜索相似文档块失败: {e}")
            traceback.print_exc()
            return []

    async def delete_document_vectors(self, document_id: int):
        """
        删除指定文档的所有向量数据
        
        Args:
            document_id: 文档ID
        """
        try:
            # 通过metadata条件删除
            self.collection.delete(where={"document_id": document_id})
            
        except Exception as e:
            raise Exception(f"删除文档 {document_id} 向量数据失败: {e}")

    async def count_vectors(self) -> int:
        """
        统计向量数据库中的向量总数
        
        Returns:
            int: 向量总数
        """
        try:
            count = self.collection.count()
            return int(count) if isinstance(count, (int, float)) else 0
            
        except Exception:
            return 0

    def apply_mmr(self, results: List[Dict[str, Any]], query_embedding: np.ndarray, 
                  lambda_param: float = 0.7, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        应用最大边界算法(MMR)来优化搜索结果
        
        MMR算法在保持相关性的同时增加结果的多样性，避免返回过于相似的文档片段。
        
        Args:
            results: 原始搜索结果列表
            query_embedding: 查询向量
            lambda_param: MMR参数，控制相关性和多样性的平衡 (0-1)
                         0.0: 只考虑多样性
                         1.0: 只考虑相关性
            top_k: 返回结果数量
            
        Returns:
            List[Dict]: 经过MMR优化的结果列表
        """
        try:
            if not results or len(results) <= 1:
                return results[:top_k]
            
            # 提取所有文档的向量
            doc_embeddings = []
            for result in results:
                # 从metadata中获取向量ID，然后从ChromaDB获取向量
                vector_id = result.get('vector_id')
                if vector_id:
                    try:
                        # 从ChromaDB获取向量
                        vector_data = self.collection.get(ids=[vector_id])
                        if vector_data and 'embeddings' in vector_data and vector_data['embeddings']:
                            doc_embeddings.append(np.array(vector_data['embeddings'][0]))
                        else:
                            # 如果无法获取向量，使用零向量
                            doc_embeddings.append(np.zeros_like(query_embedding))
                    except:
                        doc_embeddings.append(np.zeros_like(query_embedding))
                else:
                    doc_embeddings.append(np.zeros_like(query_embedding))
            
            # 转换为numpy数组
            doc_embeddings = np.array(doc_embeddings)
            
            # 计算查询与所有文档的相似度
            query_similarities = np.dot(doc_embeddings, query_embedding)
            
            # MMR算法
            selected_indices = []
            remaining_indices = list(range(len(results)))
            
            # 选择第一个最相关的文档
            first_idx = np.argmax(query_similarities)
            selected_indices.append(first_idx)
            remaining_indices.remove(first_idx)
            
            # 迭代选择剩余文档
            while len(selected_indices) < min(top_k, len(results)) and remaining_indices:
                best_score = -float('inf')
                best_idx = None
                
                for idx in remaining_indices:
                    # 计算相关性分数
                    relevance = query_similarities[idx]
                    
                    # 计算多样性分数（与已选择文档的最大相似度）
                    max_similarity = 0
                    if selected_indices:
                        selected_embeddings = doc_embeddings[selected_indices]
                        similarities = np.dot(doc_embeddings[idx], selected_embeddings.T)
                        max_similarity = np.max(similarities)
                    
                    # MMR分数 = λ * 相关性 - (1-λ) * 多样性
                    mmr_score = lambda_param * relevance - (1 - lambda_param) * max_similarity
                    
                    if mmr_score > best_score:
                        best_score = mmr_score
                        best_idx = idx
                
                if best_idx is not None:
                    selected_indices.append(best_idx)
                    remaining_indices.remove(best_idx)
                else:
                    break
            
            # 返回按MMR算法选择的结果
            mmr_results = [results[i] for i in selected_indices]
            return mmr_results
            
        except Exception as e:
            print(f"MMR算法应用失败: {e}")
            # 如果MMR失败，返回原始结果
            return results[:top_k]

    async def search_similar_chunks_with_mmr(self, query: str, top_k: int = 5, 
                                           use_threshold: bool = True, 
                                           lambda_param: float = 0.7) -> List[Dict[str, Any]]:
        """
        使用MMR算法搜索语义相似的文档块
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            use_threshold: 是否使用相似度阈值过滤
            lambda_param: MMR参数，控制相关性和多样性的平衡
            
        Returns:
            List[Dict]: 经过MMR优化的相似文档块列表
        """
        try:
            if not query or not query.strip():
                return []
            
            # 1. 生成查询向量
            query_embedding = self.embedding_model.encode([query.strip()])[0]
            
            # 2. 在ChromaDB中搜索更多相似向量（用于MMR算法）
            search_k = min(top_k * 3, 20)  # 搜索更多结果用于MMR选择
            results = self.collection.query(
                query_embeddings=[query_embedding.tolist()], 
                n_results=search_k
            )
            
            if not results or not results.get('ids') or not results['ids'][0]:
                return []
            
            # 3. 处理搜索结果
            all_similarities = []
            filtered_similarities = []
            
            ids = results['ids'][0]
            distances = results['distances'][0] if results.get('distances') else []
            metadatas = results['metadatas'][0] if results.get('metadatas') else []
            
            for i, (vector_id, metadata) in enumerate(zip(ids, metadatas)):
                try:
                    # 获取文档块信息
                    chunk_id = metadata.get('chunk_id')
                    if not chunk_id:
                        continue
                    
                    chunk = await DocumentChunk.get_or_none(id=chunk_id)
                    if not chunk:
                        continue
                    
                    # 获取关联的文档
                    document = await chunk.document
                    if not document:
                        continue
                    
                    # 计算相似度分数
                    distance = distances[i] if i < len(distances) else 1.0
                    similarity = max(0.0, 1.0 - float(distance))
                    
                    result_item = {
                        'vector_id': vector_id,
                        'similarity': similarity,
                        'chunk': chunk,
                        'document': document,
                        'metadata': metadata,
                        'above_threshold': similarity >= SIMILARITY_THRESHOLD
                    }
                    
                    all_similarities.append(result_item)
                    
                    # 如果使用阈值过滤，只保留相似度大于阈值的结果
                    if not use_threshold or similarity >= SIMILARITY_THRESHOLD:
                        filtered_similarities.append(result_item)
                    
                except Exception as e:
                    print(f"处理搜索结果项失败 (chunk_id: {metadata.get('chunk_id', 'unknown')}): {e}")
                    continue
            
            # 4. 应用MMR算法
            if filtered_similarities:
                # 有超过阈值的结果，对过滤后的结果应用MMR
                mmr_results = self.apply_mmr(filtered_similarities, query_embedding, lambda_param, top_k)
                return mmr_results
            elif all_similarities:
                # 没有超过阈值的结果，对所有结果应用MMR
                mmr_results = self.apply_mmr(all_similarities, query_embedding, lambda_param, min(top_k, 3))
                return mmr_results
            else:
                return []
            
        except Exception as e:
            print(f"MMR搜索相似文档块失败: {e}")
            traceback.print_exc()
            return []

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
        1. VectorSearch: 向量搜索引擎
        2. LangChain + OpenAI: 智能问答链（可选）
        3. 备用简单回答模式
        """
        try:
            # 初始化向量搜索引擎
            self.vector_search = VectorSearch()
            
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
                doc_name = chunk['document'].original_filename or chunk['document'].filename
                content = chunk['chunk'].content
                similarity = chunk['similarity']
                
                # 格式化文档片段
                context_part = f"""文档 {i}: {doc_name}
相似度: {similarity:.2f}
内容: {content}"""
                context_parts.append(context_part)
            
            context = "\n\n" + "="*50 + "\n\n".join(context_parts)
            
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
                doc_name = chunk.get('document_name', '未知文档')
                # 尝试获取chunk_text字段，如果没有则使用content字段
                content = chunk.get('chunk_text', chunk.get('content', ''))
                context_parts.append(f"文档{i}: {doc_name}\n内容: {content}")
            
            context = "\n\n" + "="*50 + "\n\n".join(context_parts)
            
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
    # 向量搜索实例
    vector_search = VectorSearch()
    
    # RAG生成器实例
    rag_generator = RAGGenerator()
    
except Exception as e:
    raise Exception(f"RAG系统初始化失败: {e}")
