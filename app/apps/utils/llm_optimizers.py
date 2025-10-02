"""
LLM优化器模块

专门管理问题理解和搜索优化的LLM实例
从API模块中分离出来，提供更好的代码组织
"""

from typing import Optional, Tuple
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from pydantic import BaseModel, Field

from config import OPENAI_API_KEY, OPENAI_BASE_URL

# Pydantic模型定义
class QuestionAnalysis(BaseModel):
    """问题分析结果模型"""
    question_type: str = Field(description="问题类型，如：事实查询、操作指导、概念解释等")
    core_intent: str = Field(description="问题的核心意图描述")
    keywords: list[str] = Field(description="提取的关键词列表")
    optimized_query: str = Field(description="优化后的搜索查询")
    confidence: float = Field(description="分析置信度，0-1之间", ge=0, le=1)

# 全局优化器实例
question_optimizer = None
search_optimizer = None

def initialize_question_optimizers() -> Tuple[Optional[object], Optional[object]]:
    """
    初始化问题理解和搜索优化LLM
    
    Returns:
        tuple: (question_optimizer, search_optimizer)
    """
    global question_optimizer, search_optimizer
    
    if not OPENAI_API_KEY or not OPENAI_API_KEY.strip():
        return None, None
    
    try:
        # 创建OpenAI客户端
        question_llm = ChatOpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
            temperature=0.1,
            model="gpt-3.5-turbo",
            max_tokens=500  # 限制输出长度
        )
        
        # 创建JSON输出解析器
        json_parser = JsonOutputParser(pydantic_object=QuestionAnalysis)
        
        # 问题理解和优化提示模板
        question_template = """你是一个问题理解助手。请分析用户的问题，提取关键信息并优化搜索策略。

任务：
1. 理解问题的核心意图和关键概念
2. 识别问题类型（事实查询、操作指导、概念解释等）
3. 提取最重要的搜索关键词
4. 优化搜索查询语句
5. 评估分析的置信度

用户问题：{question}

{format_instructions}"""

        # 搜索查询优化模板
        search_template = """你是一个搜索查询优化专家。请将用户问题转换为最适合文档搜索的查询语句。

要求：
1. 提取核心关键词和概念
2. 去除无关的语气词和修饰词
3. 保持查询的准确性和完整性
4. 适合向量相似度搜索
5. 保持中文输出

原问题：{question}

优化后的搜索查询（只输出查询语句）："""

        # 创建优化器链
        question_prompt = ChatPromptTemplate.from_template(question_template)
        search_prompt = ChatPromptTemplate.from_template(search_template)
        
        # 问题分析使用JSON解析器
        question_optimizer = question_prompt | question_llm | json_parser
        # 搜索优化使用字符串解析器
        search_optimizer = search_prompt | question_llm | StrOutputParser()
        
        return question_optimizer, search_optimizer
        
    except Exception as e:
        print(f"初始化LLM优化器失败: {e}")
        return None, None

def get_question_optimizer():
    """获取问题优化器实例"""
    global question_optimizer
    if question_optimizer is None:
        question_optimizer, _ = initialize_question_optimizers()
    return question_optimizer

def get_search_optimizer():
    """获取搜索优化器实例"""
    global search_optimizer
    if search_optimizer is None:
        _, search_optimizer = initialize_question_optimizers()
    return search_optimizer

def optimize_question(question: str) -> Optional[dict]:
    """
    优化用户问题
    
    Args:
        question: 原始问题
        
    Returns:
        优化后的问题分析结果（字典格式）
    """
    optimizer = get_question_optimizer()
    if optimizer is None:
        return None
    
    try:
        # 现在返回的是结构化的字典数据
        result = optimizer.invoke({
            "question": question,
            "format_instructions": JsonOutputParser(pydantic_object=QuestionAnalysis).get_format_instructions()
        })
        return result
    except Exception as e:
        print(f"问题优化失败: {e}")
        return None

def optimize_search_results(question: str, search_results: str) -> Optional[str]:
    """
    优化搜索结果
    
    Args:
        question: 原始问题
        search_results: 搜索结果
        
    Returns:
        搜索优化建议
    """
    optimizer = get_search_optimizer()
    if optimizer is None:
        return None
    
    try:
        return optimizer.invoke({
            "question": question,
            "search_results": search_results
        })
    except Exception as e:
        print(f"搜索优化失败: {e}")
        return None

def reset_optimizers():
    """重置优化器实例"""
    global question_optimizer, search_optimizer
    question_optimizer = None
    search_optimizer = None
