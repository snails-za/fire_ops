#!/usr/bin/env python3
"""
模型加载验证脚本

支持从快照直接加载已下载的模型
"""

import os
import sys
import time

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sklearn.metrics.pairwise import cosine_similarity

from config import EMBEDDING_MODEL, HF_HOME, HF_OFFLINE

def setup_environment():
    """设置环境变量"""
    os.environ["HF_HOME"] = HF_HOME
    os.environ["TRANSFORMERS_CACHE"] = HF_HOME
    os.environ["HF_HUB_CACHE"] = HF_HOME
    
    if HF_OFFLINE:
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_HUB_OFFLINE"] = "1"
    
    os.makedirs(HF_HOME, exist_ok=True)

def find_local_model_path(model_name):
    """查找本地模型路径"""
    # HuggingFace将 '/' 转换为 '--'
    local_model_name = model_name.replace('/', '--')
    local_model_path = os.path.join(HF_HOME, f"models--{local_model_name}")
    
    if os.path.exists(local_model_path):
        print(f"📁 找到模型目录: {local_model_path}")
        
        # 检查是否有snapshots目录
        snapshots_dir = os.path.join(local_model_path, "snapshots")
        if os.path.exists(snapshots_dir):
            snapshots = [d for d in os.listdir(snapshots_dir) 
                        if os.path.isdir(os.path.join(snapshots_dir, d))]
            if snapshots:
                latest_snapshot = os.path.join(snapshots_dir, snapshots[0])
                print(f"📸 找到快照: {snapshots[0]}")
                print(f"🎯 快照路径: {latest_snapshot}")
                return latest_snapshot
        
        print(f"🎯 使用模型目录: {local_model_path}")
        return local_model_path
    
    return None

def verify_model_files(model_path):
    """验证模型文件完整性"""
    print(f"🔍 验证模型文件: {model_path}")
    
    required_files = [
        "config.json",
        "modules.json", 
        "sentence_bert_config.json"
    ]
    
    # 检查模型文件
    model_files = ["model.safetensors", "pytorch_model.bin"]
    has_model_file = any(os.path.exists(os.path.join(model_path, f)) for f in model_files)
    
    # 检查tokenizer文件
    tokenizer_files = ["tokenizer.json", "vocab.txt"]
    has_tokenizer_file = any(os.path.exists(os.path.join(model_path, f)) for f in tokenizer_files)
    
    missing_files = []
    for file in required_files:
        file_path = os.path.join(model_path, file)
        if os.path.exists(file_path):
            print(f"   ✅ {file}")
        else:
            print(f"   ❌ {file} (缺失)")
            missing_files.append(file)
    
    if has_model_file:
        print(f"   ✅ 模型权重文件")
    else:
        print(f"   ❌ 模型权重文件 (缺失)")
        missing_files.append("model weights")
    
    if has_tokenizer_file:
        print(f"   ✅ 分词器文件")
    else:
        print(f"   ❌ 分词器文件 (缺失)")
        missing_files.append("tokenizer")
    
    return len(missing_files) == 0

def download_model_if_needed():
    """如果需要则下载模型"""
    print("📥 模型不存在，开始下载...")
    
    # 临时禁用离线模式进行下载
    original_offline = os.environ.get("TRANSFORMERS_OFFLINE")
    original_hub_offline = os.environ.get("HF_HUB_OFFLINE")
    
    if "TRANSFORMERS_OFFLINE" in os.environ:
        del os.environ["TRANSFORMERS_OFFLINE"]
    if "HF_HUB_OFFLINE" in os.environ:
        del os.environ["HF_HUB_OFFLINE"]
    
    try:
        from sentence_transformers import SentenceTransformer
        
        print(f"🌐 正在从HuggingFace下载: {EMBEDDING_MODEL}")
        start_time = time.time()
        
        model = SentenceTransformer(EMBEDDING_MODEL, cache_folder=HF_HOME)
        
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

def load_and_verify_model():
    """加载并验证模型"""
    print(f"🔍 模型: {EMBEDDING_MODEL}")
    print(f"📁 缓存: {HF_HOME}")
    print(f"🔒 离线: {HF_OFFLINE}")
    print("-" * 50)
    
    # 1. 查找本地模型
    local_model_path = find_local_model_path(EMBEDDING_MODEL)
    
    if not local_model_path:
        print("📭 未找到本地模型")
        
        # 如果离线模式，提示用户
        if HF_OFFLINE:
            print("⚠️  当前为离线模式，但模型不存在")
            print("🔄 临时切换到在线模式进行下载...")
        
        # 尝试下载模型
        if not download_model_if_needed():
            return False
        
        # 重新查找下载后的模型
        local_model_path = find_local_model_path(EMBEDDING_MODEL)
        if not local_model_path:
            print("❌ 下载后仍未找到模型文件")
            return False
    
    # 2. 验证文件完整性
    if not verify_model_files(local_model_path):
        print("❌ 模型文件不完整，尝试重新下载...")
        
        # 文件不完整，尝试重新下载
        if not download_model_if_needed():
            return False
        
        # 重新验证
        local_model_path = find_local_model_path(EMBEDDING_MODEL)
        if not local_model_path or not verify_model_files(local_model_path):
            print("❌ 重新下载后文件仍不完整")
            return False
    
    try:
        from sentence_transformers import SentenceTransformer
        
        # 3. 尝试直接从快照路径加载
        print(f"\n📥 从快照加载模型...")
        start_time = time.time()
        
        if HF_OFFLINE:
            # 离线模式：直接使用本地路径
            model = SentenceTransformer(local_model_path)
            load_method = "快照路径 (离线)"
        else:
            # 在线模式：先尝试模型名称，失败则使用本地路径
            try:
                model = SentenceTransformer(EMBEDDING_MODEL, cache_folder=HF_HOME)
                load_method = "模型名称 (在线)"
            except:
                model = SentenceTransformer(local_model_path)
                load_method = "快照路径 (降级)"
        
        load_time = time.time() - start_time
        print(f"✅ 模型加载成功！")
        print(f"   - 加载方式: {load_method}")
        print(f"   - 耗时: {load_time:.2f}秒")
        
        # 4. 测试编码功能
        print(f"\n🧪 测试编码功能...")
        test_texts = [
            "这是一个中文测试文本，用于验证模型的中文处理能力。",
            "This is an English test text for model validation.",
            "RAG系统向量化测试，检索增强生成技术验证。"
        ]
        
        encode_start = time.time()
        embeddings = model.encode(test_texts)
        encode_time = time.time() - encode_start
        
        print(f"✅ 编码测试成功！")
        print(f"   - 文本数量: {len(test_texts)}")
        print(f"   - 向量维度: {embeddings.shape}")
        print(f"   - 编码耗时: {encode_time:.3f}秒")
        print(f"   - 平均耗时: {encode_time/len(test_texts):.3f}秒/文本")
        
        # 5. 测试相似度计算
        print(f"\n🔗 测试相似度计算...")
        
        # 计算中文文本间的相似度
        sim_zh = cosine_similarity([embeddings[0]], [embeddings[2]])[0][0]
        sim_zh_en = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
        
        print(f"   - 中文文本相似度: {sim_zh:.4f}")
        print(f"   - 中英文本相似度: {sim_zh_en:.4f}")
        
        return True
        
    except Exception as e:
        print(f"❌ 加载失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("🚀 智能模型管理工具")
    print("=" * 50)
    print("📋 功能:")
    print("   ✅ 自动检测本地模型快照")
    print("   ✅ 如果不存在则自动下载")
    print("   ✅ 验证模型文件完整性")
    print("   ✅ 测试模型加载和编码功能")
    print("-" * 50)
    
    setup_environment()
    
    success = load_and_verify_model()
    
    if success:
        print("\n🎉 模型准备完成！")
        print("📝 现在可以启动RAG系统:")
        print("   fastapi dev asgi.py")
        print("\n💡 状态:")
        print("   ✅ 模型文件完整")
        print("   ✅ 快照加载正常")
        print("   ✅ 编码功能正常")
        print("   ✅ 可以开始处理文档")
    else:
        print("\n❌ 模型准备失败")
        print("🔧 请检查:")
        print("   - 网络连接是否正常")
        print("   - 磁盘空间是否充足")
        print("   - HuggingFace访问是否正常")
        print("   - 环境配置是否正确")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)