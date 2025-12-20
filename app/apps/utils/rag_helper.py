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

import traceback
from typing import List, Dict, Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from apps.utils.vector_db_selector import vector_search
from config import (
    OPENAI_API_KEY, OPENAI_BASE_URL
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
            self.vector_search = vector_search

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
                    system_template = """你是一个专业的文档和设备信息问答助手。请基于提供的文档内容和设备信息准确回答用户的问题。

回答要求：
1. 严格基于提供的文档内容和设备信息回答，不要添加这些信息中没有的内容
2. 如果文档和设备信息中都没有相关信息，请明确说明"根据提供的信息，无法找到相关内容"
3. 如果提供了设备信息，优先使用设备信息回答关于设备状态、位置、安装等的问题
4. 对于任何关于设备的问题，请基于提供的设备信息列表进行回答：
   - 如果询问设备数量，直接统计设备列表中的设备总数
   - 如果询问设备状态，统计各个状态的设备数量（正常、离线、异常、维修中等）
   - 如果询问具体设备，从设备列表中查找匹配的设备并列出详细信息
   - 可以按地址、安装日期等维度进行统计或筛选
   - 如果设备列表为空，明确说明"当前没有设备"
   - 所有回答要准确，严格基于实际提供的设备数据
5. 对于具体设备查询问题，从设备列表中查找匹配的设备并列出详细信息
6. 回答要准确、详细且有条理，使用清晰的段落结构：
   - 使用标题和子标题组织内容
   - 重要信息用**粗体**标记
   - 使用项目符号(•)或数字列表展示要点
   - 每个段落专注一个主题，段落间留空行
   - 复杂内容使用表格或结构化格式
7. 可以引用具体的文档名称和设备信息，格式：「文档名：具体内容」或「设备名：具体信息」
8. 如果有多个信息来源提供了相关信息，请综合分析并标明信息来源
9. 用中文回答，语言要专业但易懂，适当使用emoji增强可读性

提供的文档内容：
{document_context}

提供的设备信息：
{device_context}"""

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

    async def generate_answer(self, query: str, context_chunks: List[Dict[str, Any]], device_context: str = "") -> str:
        """
        基于检索到的文档内容生成智能回答
        
        回答策略：
        1. 优先使用LLM智能回答（如果可用）
        2. 降级到简单回答模式（备用方案）
        3. 提供上下文信息和来源引用
        
        Args:
            query: 用户问题
            context_chunks: 检索到的相关文档块
            device_context: 设备信息上下文
            
        Returns:
            str: 生成的回答
        """
        try:
            # 检查是否有相关文档或设备信息
            if not context_chunks and not device_context:
                return "抱歉，没有找到相关的文档内容或设备信息来回答您的问题。请确保已上传相关文档或添加设备信息，或尝试使用不同的关键词重新提问。"

            # 构建文档上下文信息
            context_parts = []
            print(f"RAG生成器接收到文档数量: {len(context_chunks)}")
            
            for i, chunk in enumerate(context_chunks, 1):
                # 处理不同的结果格式
                if chunk.get('document') and chunk.get('chunk'):
                    doc_name = chunk['document'].original_filename or chunk['document'].filename
                    content = chunk['chunk'].content
                    print(f"文档 {i}: {doc_name}, 内容长度: {len(content) if content else 0}")
                else:
                    # 使用备用格式
                    doc_name = chunk.get('metadata', {}).get('source', '未知文档')
                    content = chunk.get('content', '无内容')
                    print(f"备用格式文档 {i}: {doc_name}, 内容长度: {len(content) if content else 0}")

                similarity = chunk.get('similarity', 0)

                # 格式化文档片段
                context_part = f"""文档 {i}: {doc_name}
相似度: {similarity:.2f}
内容: {content}"""
                context_parts.append(context_part)

            document_context = "\n\n" + "=" * 50 + "\n\n".join(context_parts) if context_parts else "无相关文档"
            print(f"构建的文档上下文长度: {len(document_context)}")

            # 如果没有设备信息，使用空字符串
            if not device_context:
                device_context = "无相关设备信息"

            # 选择回答模式
            if self.llm_available and self.chain:
                try:
                    answer = await self._llm_answer(query, document_context, device_context)

                    # 不再自动添加来源信息，由前端决定是否显示
                    return answer

                except Exception:
                    return self._simple_answer(query, context_chunks, device_context)
            else:
                return self._simple_answer(query, context_chunks, device_context)

        except Exception as e:
            return f"抱歉，生成回答时出现错误: {str(e)}"

    async def generate_answer_stream(self, query: str, context_chunks: List[Dict[str, Any]], device_context: str = ""):
        """
        流式生成回答
        
        Args:
            query: 用户问题
            context_chunks: 文档上下文块列表
            device_context: 设备信息上下文
            
        Yields:
            str: 流式生成的文本块
        """
        try:
            # 构建文档上下文
            context_parts = []
            print(f"流式RAG生成器接收到文档数量: {len(context_chunks)}")
            
            for i, chunk in enumerate(context_chunks, 1):
                # 直接使用数据结构
                doc_name = chunk['document'].original_filename or chunk['document'].filename
                content = chunk['chunk'].content
                print(f"流式文档 {i}: {doc_name}, 内容长度: {len(content) if content else 0}")
                context_parts.append(f"文档{i}: {doc_name}\n内容: {content}")

            document_context = "\n\n" + "=" * 50 + "\n\n".join(context_parts) if context_parts else "无相关文档"
            print(f"流式构建的文档上下文长度: {len(document_context)}")
            
            # 如果没有设备信息，使用空字符串
            if not device_context:
                device_context = "无相关设备信息"

            # 选择回答模式
            if self.llm_available and self.chain:
                try:
                    print("使用LLM流式生成回答")
                    async for chunk in self._llm_answer_stream(query, document_context, device_context):
                        yield chunk
                except Exception as e:
                    print(f"LLM流式生成失败: {e}")
                    print("降级到简单回答模式")
                    # 降级到简单回答
                    simple_answer = self._simple_answer(query, context_chunks, device_context)
                    yield simple_answer
            else:
                print("LLM不可用，使用简单回答模式")
                # 非LLM模式，直接返回简单回答
                simple_answer = self._simple_answer(query, context_chunks, device_context)
                yield simple_answer

        except Exception as e:
            yield f"抱歉，生成回答时出现错误: {str(e)}"

    async def _llm_answer_stream(self, query: str, document_context: str, device_context: str):
        """
        使用LangChain链式流式生成智能回答
        
        Args:
            query: 用户问题
            document_context: 文档上下文
            device_context: 设备信息上下文
            
        Yields:
            str: 流式生成的文本块
        """
        try:
            # 使用已经创建好的chain进行流式调用
            if self.chain:
                async for chunk in self.chain.astream({
                    "question": query,
                    "document_context": document_context,
                    "device_context": device_context
                }):
                    if chunk:
                        yield chunk
            else:
                raise Exception("LangChain处理链未初始化")

        except Exception as e:
            traceback.print_exc()
            raise Exception(f"LLM链式流式调用失败: {str(e)}")

    async def _llm_answer(self, query: str, document_context: str, device_context: str) -> str:
        """
        使用LLM生成智能回答
        
        Args:
            query: 用户问题
            document_context: 文档上下文
            device_context: 设备信息上下文
            
        Returns:
            str: LLM生成的回答
        """
        try:
            # 调用LangChain处理链
            response = await self.chain.ainvoke({
                "question": query,
                "document_context": document_context,
                "device_context": device_context
            })

            if not response or not response.strip():
                raise Exception("LLM返回空回答")

            return response.strip()

        except Exception as e:
            raise Exception(f"LLM调用失败: {str(e)}")

    def _simple_answer(self, query: str, context_chunks: List[Dict[str, Any]], device_context: str = "") -> str:
        """
        简单回答模式 - 基于关键词匹配的备用方案
        
        Args:
            query: 用户问题
            context_chunks: 相关文档块
            device_context: 设备信息上下文
            
        Returns:
            str: 简单模式生成的回答
        """
        try:
            answer_parts = []
            print(f"简单回答模式 - 设备上下文: {device_context}")
            print(f"简单回答模式 - 文档块数量: {len(context_chunks) if context_chunks else 0}")
            
            # 添加设备信息
            if device_context and device_context != "无相关设备信息":
                print("添加设备信息到回答中")
                answer_parts.append(f"📱 **设备信息：**\n{device_context}")
            else:
                print("设备上下文为空或为'无相关设备信息'，跳过设备信息")
            
            # 添加文档信息
            if context_chunks:
                print("添加文档信息到回答中")
                best_chunk = context_chunks[0]
                document_name = best_chunk['document'].original_filename or best_chunk['document'].filename
                content = best_chunk['chunk'].content
                answer_parts.append(f"📄 **基于文档《{document_name}》中的相关内容：**\n\n{content}")
            else:
                print("没有文档块，跳过文档信息")
            
            print(f"回答部分数量: {len(answer_parts)}")
            
            if not answer_parts:
                print("没有回答部分，返回默认消息")
                return "抱歉，没有找到相关的文档内容或设备信息来回答您的问题。"
            
            answer = "\n\n" + "\n\n".join(answer_parts)
            answer += "\n\n💡 **提示**：当前使用简单回答模式。配置OpenAI API Key后可获得更智能的回答。"

            return answer

        except Exception:
            return "抱歉，生成回答时出现错误。"


rag_generator = RAGGenerator()
