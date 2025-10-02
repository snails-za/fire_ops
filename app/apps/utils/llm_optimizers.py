"""
LLM优化器模块

专门管理问题理解和搜索优化的LLM实例
从API模块中分离出来，提供更好的代码组织
"""

from typing import Optional, Tuple
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from config import OPENAI_API_KEY, OPENAI_BASE_URL

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
        
        # 问题理解和优化提示模板
        question_template = """你是一个问题理解助手。请分析用户的问题，提取关键信息并优化搜索策略。

任务：
1. 理解问题的核心意图和关键概念
2. 识别问题类型（事实查询、操作指导、概念解释等）
3. 提取最重要的搜索关键词
4. 如果问题模糊，推测可能的具体含义

用户问题：{question}

请用以下格式回答：
问题类型：[类型]
核心意图：[意图描述]
关键词：[关键词1, 关键词2, ...]
优化建议：[搜索建议]"""

        # 搜索优化提示模板
        search_template = """你是一个搜索优化专家。基于用户问题和搜索到的文档片段，优化搜索策略。

原始问题：{question}
搜索结果：{search_results}

请分析：
1. 搜索结果是否与问题相关
2. 是否需要调整搜索关键词
3. 是否需要扩展或缩小搜索范围

请提供：
- 相关性评分（1-10）
- 改进建议
- 优化后的搜索词"""

        # 创建优化器链
        question_prompt = ChatPromptTemplate.from_template(question_template)
        search_prompt = ChatPromptTemplate.from_template(search_template)
        
        question_optimizer = question_prompt | question_llm | StrOutputParser()
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

def optimize_question(question: str) -> Optional[str]:
    """
    优化用户问题
    
    Args:
        question: 原始问题
        
    Returns:
        优化后的问题分析结果
    """
    optimizer = get_question_optimizer()
    if optimizer is None:
        return None
    
    try:
        return optimizer.invoke({"question": question})
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
