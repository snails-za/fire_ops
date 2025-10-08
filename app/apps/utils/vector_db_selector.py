"""
简单的向量数据库选择器

支持ChromaDB和Qdrant两个数据库的切换
"""
import traceback
from typing import List, Dict, Any

import torch
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_qdrant import Qdrant
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue
from qdrant_client.http.models import VectorParams
from qdrant_client.models import Distance

from apps.models.document import Document as DocumentModel, DocumentChunk
from apps.utils.common import get_local_model_path
from config import CHROMA_PERSIST_DIRECTORY, CHROMA_COLLECTION, SIMILARITY_THRESHOLD
from config import (
    EMBEDDING_MODEL, HF_HOME, HF_OFFLINE,
    QDRANT_HOST, QDRANT_PORT, QDRANT_COLLECTION_NAME
)
from config import VECTOR_DB_TYPE


class VectorDBSelector:
    """向量数据库选择器"""

    def __init__(self):
        self.db_type = VECTOR_DB_TYPE
        self.vectorstore = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.embeddings = self._get_embedding_model()
        self._init_database()

    def _init_database(self):
        """初始化数据库"""
        if self.db_type == "qdrant":
            self._init_qdrant()
        else:
            self._init_chroma()

    def _get_embedding_model(self):
        """获取嵌入模型"""
        # 初始化嵌入模型
        local_model_path = get_local_model_path(EMBEDDING_MODEL, HF_HOME)

        if local_model_path and HF_OFFLINE:
            embeddings = HuggingFaceEmbeddings(
                model_name=local_model_path,
                model_kwargs={'device': self.device},
                encode_kwargs={'normalize_embeddings': True}
            )
        else:
            embeddings = HuggingFaceEmbeddings(
                model_name=EMBEDDING_MODEL,
                cache_folder=HF_HOME,
                model_kwargs={'device': self.device},
                encode_kwargs={'normalize_embeddings': True}
            )
        return embeddings

    def _init_chroma(self):
        """初始化ChromaDB"""
        self.vectorstore = Chroma(
            collection_name=CHROMA_COLLECTION,
            embedding_function=self.embeddings,
            persist_directory=CHROMA_PERSIST_DIRECTORY,
        )
        print("✅ 使用ChromaDB向量存储")

    def _init_qdrant(self):
        """初始化 Qdrant（修正版）"""
        host, port, collection_name = QDRANT_HOST, QDRANT_PORT, QDRANT_COLLECTION_NAME

        # ✅ 必须用 url= 显式指定 HTTP 访问，否则默认走 gRPC！
        client = QdrantClient(url=f"http://{host}:{port}", timeout=30)
        print(f"🌐 正在连接 Qdrant: http://{host}:{port}")

        # ✅ 如果 collection 不存在则自动创建
        if not client.collection_exists(collection_name):
            dim = self.embeddings.client.get_sentence_embedding_dimension()
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE)
            )
            print(f"✅ 自动创建 Qdrant collection: {collection_name} (dim={dim})")

        # ✅ 初始化 LangChain 向量存储
        self.vectorstore = Qdrant(
            client=client,
            collection_name=collection_name,
            embeddings=self.embeddings,
        )
        print("✅ 使用Qdrant向量存储")


    async def add_documents_from_chunks(self, document_id: int, chunks: List[str], chunk_objects: List,
                                        metadata: Dict[str, Any] = None) -> List[str]:
        """添加文档到向量存储"""
        try:
            if not chunks or not chunk_objects:
                raise Exception("文档块为空")

            # 创建LangChain文档对象
            documents = []
            chunk_ids = []

            for i, (chunk_text, chunk_obj) in enumerate(zip(chunks, chunk_objects)):
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

            # 添加到向量存储
            if documents:
                self.vectorstore.add_documents(documents)

            return chunk_ids

        except Exception as e:
            traceback.print_exc()
            raise Exception(f"添加文档到向量存储失败: {e}")

    async def search_similar_documents(self, query: str, top_k: int = 5, use_threshold: bool = True) -> List[
        Dict[str, Any]]:
        """搜索相似文档"""
        try:
            # 执行搜索
            print(f"🔍 执行向量搜索: 查询='{query}', top_k={top_k}, 数据库类型={self.db_type}")
            results = self.vectorstore.similarity_search_with_score(query, k=20)
            print(f"📊 搜索结果数量: {len(results)}")

            # 转换为标准格式
            all_results = []
            filtered_results = []

            for i, (doc, score) in enumerate(results):
                # 计算相似度
                if self.db_type == "qdrant":
                    similarity = score
                else:
                    similarity = max(0.0, 1.0 - score)
                print(f"📈 结果 {i + 1}: score={score:.4f}, similarity={similarity:.4f}")
                # 获取元数据
                metadata = doc.metadata
                print(f"📄 文档元数据: {metadata}")
                document_id = metadata.get('document_id')
                chunk_id = metadata.get('chunk_id')

                if document_id and chunk_id:
                    try:
                        # 获取数据库中的文档和块信息
                        document = await DocumentModel.get_or_none(id=document_id)
                        if not document:
                            await vector_search.delete_document(document_id)
                            continue
                        chunk = await DocumentChunk.get_or_none(id=chunk_id)
                        if not chunk:
                            await vector_search.delete_document(document_id)
                            continue

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
                        print(f"处理搜索结果项失败: {e}")
                        continue

            # 选择返回结果
            print(f"📋 过滤前结果: {len(all_results)}, 过滤后结果: {len(filtered_results)}")

            if filtered_results:
                filtered_results.sort(key=lambda x: x['similarity'], reverse=True)
                print(f"✅ 返回过滤后的结果: {len(filtered_results)}")
                return filtered_results[:top_k]
            elif all_results:
                all_results.sort(key=lambda x: x['similarity'], reverse=True)
                print(f"⚠️ 返回所有结果: {len(all_results)}")
                return all_results[:min(top_k, 3)]
            else:
                print("❌ 没有找到任何结果")
                return []

        except Exception as e:
            traceback.print_exc()
            print(f"搜索相似文档失败: {e}")
            return []

    async def delete_document(self, document_id: int):
        """删除文档"""
        try:
            if self.db_type == "qdrant":
                # Qdrant删除
                self.vectorstore.client.delete(
                    collection_name=QDRANT_COLLECTION_NAME,
                    points_selector=Filter(
                        must=[
                            FieldCondition(
                                key="document_id",
                                match=MatchValue(value=document_id)
                            )
                        ]
                    )
                )
            else:
                # ChromaDB删除
                self.vectorstore._collection.delete(where={"document_id": document_id})

            print(f"✅ 成功删除文档 {document_id} 的向量数据")

        except Exception as e:
            traceback.print_exc()
            raise Exception(f"删除文档 {document_id} 向量数据失败: {e}")

    async def count_vectors(self) -> int:
        """统计向量数量"""
        try:
            if self.db_type == "qdrant":
                # Qdrant统计
                collection_info = self.vectorstore.client.get_collection(QDRANT_COLLECTION_NAME)
                return collection_info.points_count
            else:
                # ChromaDB统计
                collection = self.vectorstore._collection
                return collection.count()
        except Exception as e:
            print(f"统计向量数量失败: {e}")
            return 0


vector_search = VectorDBSelector()
print("✅ 使用LangChain向量存储")
