#!/usr/bin/env python3
"""
智能模型对比测试工具

支持自动检测快照、自动下载、性能对比和智能推荐
"""

import os
import sys
import time
import numpy as np

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sklearn.metrics.pairwise import cosine_similarity

from config import HF_HOME, HF_OFFLINE

def setup_environment():
    """设置环境变量"""
    os.environ["HF_HOME"] = HF_HOME
    os.environ["TRANSFORMERS_CACHE"] = HF_HOME
    os.environ["HF_HUB_CACHE"] = HF_HOME
    
    os.makedirs(HF_HOME, exist_ok=True)

def find_local_model_path(model_name):
    """查找本地模型路径"""
    # HuggingFace将 '/' 转换为 '--'
    local_model_name = model_name.replace('/', '--')
    local_model_path = os.path.join(HF_HOME, f"models--{local_model_name}")
    
    if os.path.exists(local_model_path):
        # 检查是否有snapshots目录
        snapshots_dir = os.path.join(local_model_path, "snapshots")
        if os.path.exists(snapshots_dir):
            snapshots = [d for d in os.listdir(snapshots_dir) 
                        if os.path.isdir(os.path.join(snapshots_dir, d))]
            if snapshots:
                latest_snapshot = os.path.join(snapshots_dir, snapshots[0])
                return latest_snapshot
        return local_model_path
    return None

def download_model_if_needed(model_name):
    """如果需要则下载模型"""
    print(f"📥 下载模型: {model_name}")
    
    # 临时禁用离线模式进行下载
    original_offline = os.environ.get("TRANSFORMERS_OFFLINE")
    original_hub_offline = os.environ.get("HF_HUB_OFFLINE")
    
    if "TRANSFORMERS_OFFLINE" in os.environ:
        del os.environ["TRANSFORMERS_OFFLINE"]
    if "HF_HUB_OFFLINE" in os.environ:
        del os.environ["HF_HUB_OFFLINE"]
    
    try:
        from sentence_transformers import SentenceTransformer
        
        print(f"🌐 正在从HuggingFace下载...")
        start_time = time.time()
        
        model = SentenceTransformer(model_name, cache_folder=HF_HOME)
        
        download_time = time.time() - start_time
        print(f"✅ 下载完成！耗时: {download_time:.2f}秒")
        
        return True
        
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        return False
        
    finally:
        # 恢复原始离线设置
        if original_offline:
            os.environ["TRANSFORMERS_OFFLINE"] = original_offline
        if original_hub_offline:
            os.environ["HF_HUB_OFFLINE"] = original_hub_offline

def test_model_performance(model_name, test_texts):
    """测试模型性能"""
    print(f"\n🧪 测试模型: {model_name}")
    print("-" * 60)
    
    # 1. 检查本地模型
    local_model_path = find_local_model_path(model_name)
    
    if not local_model_path:
        print("📭 本地未找到模型，开始下载...")
        if not download_model_if_needed(model_name):
            print(f"❌ 模型 {model_name} 下载失败")
            return None
        
        # 重新查找下载后的模型
        local_model_path = find_local_model_path(model_name)
        if not local_model_path:
            print(f"❌ 下载后仍未找到模型: {model_name}")
            return None
    else:
        print(f"✅ 找到本地模型快照")
    
    try:
        from sentence_transformers import SentenceTransformer
        
        # 2. 加载模型 - 优先使用本地路径
        start_time = time.time()
        
        # 设置临时离线模式确保使用本地模型
        original_offline = os.environ.get("TRANSFORMERS_OFFLINE")
        original_hub_offline = os.environ.get("HF_HUB_OFFLINE")
        
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_HUB_OFFLINE"] = "1"
        
        try:
            model = SentenceTransformer(local_model_path)
            load_method = "本地快照"
        except:
            # 如果本地加载失败，尝试在线加载
            if original_offline:
                os.environ["TRANSFORMERS_OFFLINE"] = original_offline
            else:
                del os.environ["TRANSFORMERS_OFFLINE"]
            if original_hub_offline:
                os.environ["HF_HUB_OFFLINE"] = original_hub_offline
            else:
                del os.environ["HF_HUB_OFFLINE"]
            
            model = SentenceTransformer(model_name, cache_folder=HF_HOME)
            load_method = "在线加载"
        
        load_time = time.time() - start_time
        
        # 3. 编码测试
        encode_start = time.time()
        embeddings = model.encode(test_texts)
        encode_time = time.time() - encode_start
        
        print(f"⏱️  加载时间: {load_time:.2f}秒 ({load_method})")
        print(f"⚡ 编码时间: {encode_time:.3f}秒")
        print(f"📊 向量维度: {embeddings.shape}")
        print(f"🔢 平均每文本: {encode_time/len(test_texts):.3f}秒")
        
        # 恢复原始环境设置
        if original_offline:
            os.environ["TRANSFORMERS_OFFLINE"] = original_offline
        elif "TRANSFORMERS_OFFLINE" in os.environ:
            del os.environ["TRANSFORMERS_OFFLINE"]
            
        if original_hub_offline:
            os.environ["HF_HUB_OFFLINE"] = original_hub_offline
        elif "HF_HUB_OFFLINE" in os.environ:
            del os.environ["HF_HUB_OFFLINE"]
        
        # 4. 计算相似度
        if len(embeddings) >= 3:
            
            # 中文文本相似度
            sim_zh = cosine_similarity([embeddings[0]], [embeddings[2]])[0][0]
            # 中英文相似度
            sim_zh_en = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
            
            print(f"🔗 中文相似度: {sim_zh:.4f}")
            print(f"🌐 中英相似度: {sim_zh_en:.4f}")
            
            return {
                "load_time": load_time,
                "encode_time": encode_time,
                "dimensions": embeddings.shape[1],
                "zh_similarity": sim_zh,
                "zh_en_similarity": sim_zh_en,
                "load_method": load_method
            }
        
        return {
            "load_time": load_time,
            "encode_time": encode_time,
            "dimensions": embeddings.shape[1],
            "load_method": load_method
        }
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return None

def compare_models():
    """对比不同模型"""
    # 测试文本 - 包含中英文对照
    test_texts = [
        "这是一个关于人工智能和机器学习的中文文档，讨论了深度学习在自然语言处理中的应用。",
        "This is an English document about artificial intelligence and machine learning, discussing deep learning applications in NLP.",
        "本文档介绍了RAG检索增强生成技术，以及如何在实际项目中应用向量数据库进行语义搜索。",
        "The document explains RAG retrieval-augmented generation technology and vector database applications."
    ]
    
    # 要测试的模型
    models = [
        {
            "name": "当前模型",
            "model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            "description": "多语言通用模型"
        },
        {
            "name": "BGE中文模型", 
            "model": "BAAI/bge-small-zh-v1.5",
            "description": "百度BGE中文优化模型"
        }
    ]
    
    results = {}
    
    print("🚀 开始智能模型对比测试")
    print("=" * 60)
    print("📝 测试内容:")
    print("   - 模型加载速度")
    print("   - 文本编码性能") 
    print("   - 中文语义相似度")
    print("   - 中英文跨语言效果")
    print("=" * 60)
    
    for model_info in models:
        result = test_model_performance(model_info["model"], test_texts)
        if result:
            results[model_info["name"]] = result
            results[model_info["name"]]["description"] = model_info["description"]
    
    # 打印对比结果
    if len(results) >= 2:
        print("\n📊 智能对比结果")
        print("=" * 60)
        
        print(f"{'指标':<15} {'当前模型':<20} {'BGE模型':<20} {'优势':<10}")
        print("-" * 70)
        
        current = results.get("当前模型", {})
        bge = results.get("BGE中文模型", {})
        
        if current and bge:
            # 加载时间对比
            load_winner = "BGE" if bge["load_time"] < current["load_time"] else "当前"
            print(f"{'加载时间':<15} {current['load_time']:.2f}秒({current.get('load_method', 'N/A'):<8}) {bge['load_time']:.2f}秒({bge.get('load_method', 'N/A'):<8}) {load_winner}")
            
            # 编码时间对比
            encode_winner = "BGE" if bge["encode_time"] < current["encode_time"] else "当前"
            print(f"{'编码时间':<15} {current['encode_time']:.3f}秒{'':<12} {bge['encode_time']:.3f}秒{'':<12} {encode_winner}")
            
            # 向量维度对比
            dim_winner = "BGE" if bge["dimensions"] > current["dimensions"] else "当前"
            print(f"{'向量维度':<15} {current['dimensions']}{'':<16} {bge['dimensions']}{'':<16} {dim_winner}")
            
            # 中文相似度对比
            if "zh_similarity" in current and "zh_similarity" in bge:
                zh_winner = "BGE" if bge["zh_similarity"] > current["zh_similarity"] else "当前"
                print(f"{'中文相似度':<15} {current['zh_similarity']:.4f}{'':<14} {bge['zh_similarity']:.4f}{'':<14} {zh_winner}")
    
    return results

def get_recommendation(results):
    """获取智能推荐建议"""
    print("\n💡 智能推荐建议")
    print("=" * 60)
    
    if "BGE中文模型" in results and "当前模型" in results:
        bge = results["BGE中文模型"]
        current = results["当前模型"]
        
        print("🎯 基于测试结果的建议:")
        
        # 计算综合得分
        bge_score = 0
        current_score = 0
        
        # 中文相似度权重最高
        if "zh_similarity" in bge and "zh_similarity" in current:
            if bge["zh_similarity"] > current["zh_similarity"]:
                bge_score += 3
                print("   ✅ BGE模型中文语义理解更准确 (+3分)")
            else:
                current_score += 3
                print("   ✅ 当前模型中文语义理解更准确 (+3分)")
        
        # 向量维度
        if bge["dimensions"] > current["dimensions"]:
            bge_score += 2
            print("   ✅ BGE模型向量维度更高，表达能力更强 (+2分)")
        else:
            current_score += 2
            print("   ✅ 当前模型向量维度适中，节省存储空间 (+2分)")
        
        # 编码速度
        if bge["encode_time"] < current["encode_time"]:
            bge_score += 1
            print("   ✅ BGE模型编码速度更快 (+1分)")
        else:
            current_score += 1
            print("   ✅ 当前模型编码速度更快 (+1分)")
        
        print(f"\n📊 综合评分:")
        print(f"   BGE模型: {bge_score}分")
        print(f"   当前模型: {current_score}分")
        
        if bge_score > current_score:
            print(f"\n🏆 推荐使用BGE模型！")
            print("🔧 切换方法:")
            print("   在 config.py 中修改:")
            print('   EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"')
            print('   EMBEDDING_DIMENSION = 512')
        else:
            print(f"\n🏆 建议保持当前模型！")
            print("💡 当前模型已经很好地满足需求")
        
        print("\n⚠️  切换注意事项:")
        print("   - 切换模型后需要重新处理已有文档")
        print("   - 新模型向量与旧模型不兼容")
        print("   - 建议先备份现有向量数据")
    
    else:
        print("❌ 无法获取完整测试结果，请检查网络连接")

def main():
    """主函数"""
    print("🔬 智能模型对比测试工具")
    print("=" * 60)
    print("📋 功能:")
    print("   ✅ 自动检测本地模型快照")
    print("   ✅ 缺失模型自动下载")
    print("   ✅ 多模型性能对比")
    print("   ✅ 中文效果评估")
    print("   ✅ 智能推荐建议")
    print("-" * 60)
    
    setup_environment()
    
    try:
        results = compare_models()
        get_recommendation(results)
        
        print(f"\n🎉 对比测试完成！")
        print("💡 您可以根据测试结果选择最适合的模型")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        print("🔧 请检查网络连接和环境配置")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
