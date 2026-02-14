"""
ModelArts 昇腾文档知识库 - 向量存储模块
基于 ChromaDB 存储华为云 ModelArts 文档知识，支持语义检索
"""

import time
import hashlib
import chromadb
from chromadb.config import Settings
from typing import Dict, List, Optional, Any, Tuple
from utils.logger import get_logger

logger = get_logger(__name__)


class ModelArtsKnowledgeStore:
    """ModelArts 昇腾部署知识向量存储"""

    def __init__(self, persist_directory: str = "./data/vector_db"):
        self.persist_directory = persist_directory
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        self.collection = self._get_or_create_collection()
        # 搜索结果缓存: key -> (timestamp, results)
        self._search_cache: Dict[str, Tuple[float, List]] = {}
        self._search_cache_ttl = 300  # 5分钟
        self._search_cache_max = 128
        # 统计缓存
        self._stats_cache: Optional[Dict[str, Any]] = None
        self._stats_cache_time: float = 0
        self._stats_cache_ttl = 600  # 10分钟
        logger.info(f"ModelArts 知识库初始化完成，目录: {persist_directory}")

    def _get_or_create_collection(self):
        """获取或创建 ModelArts 知识集合"""
        try:
            collection = self.client.get_collection(
                name="modelarts_knowledge",
                embedding_function=None
            )
            logger.info(f"已存在 ModelArts 知识集合，当前文档数: {collection.count()}")
            return collection
        except Exception:
            collection = self.client.create_collection(
                name="modelarts_knowledge",
                metadata={
                    "description": "华为云 ModelArts 昇腾部署知识库",
                    "created_at": "2026-02-13"
                }
            )
            logger.info("创建新集合: modelarts_knowledge")
            return collection

    def add_document(
        self,
        doc_id: str,
        category: str,
        title: str,
        content: str,
        doc_url: str = "",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """添加单个知识文档"""
        try:
            doc_text = self._build_document_text(
                category=category,
                title=title,
                content=content,
                tags=tags or []
            )

            metadatas = {
                "category": category,
                "title": title,
                "doc_url": doc_url,
                "tags": ",".join(tags) if tags else "",
                "doc_id": doc_id,
            }
            if metadata:
                # ChromaDB metadata 只支持 str/int/float/bool
                for k, v in metadata.items():
                    if isinstance(v, (str, int, float, bool)):
                        metadatas[k] = v

            self.collection.add(
                ids=[doc_id],
                documents=[doc_text],
                metadatas=[metadatas]
            )
            self._stats_cache = None
            self._search_cache.clear()
            logger.debug(f"添加知识文档成功: {doc_id}")
            return True
        except Exception as e:
            logger.error(f"添加知识文档失败 {doc_id}: {e}")
            return False

    def batch_add_documents(self, documents: List[Dict[str, Any]]) -> int:
        """批量添加知识文档"""
        try:
            ids = []
            doc_texts = []
            metadatas = []

            for doc in documents:
                doc_id = doc["doc_id"]
                category = doc.get("category", "")
                title = doc.get("title", "")
                content = doc.get("content", "")
                doc_url = doc.get("doc_url", "")
                tags = doc.get("tags", [])
                extra_meta = doc.get("metadata", {})

                doc_text = self._build_document_text(
                    category=category,
                    title=title,
                    content=content,
                    tags=tags
                )

                ids.append(doc_id)
                doc_texts.append(doc_text)

                meta = {
                    "category": category,
                    "title": title,
                    "doc_url": doc_url,
                    "tags": ",".join(tags) if tags else "",
                    "doc_id": doc_id,
                }
                for k, v in extra_meta.items():
                    if isinstance(v, (str, int, float, bool)):
                        meta[k] = v
                metadatas.append(meta)

            self.collection.add(
                ids=ids,
                documents=doc_texts,
                metadatas=metadatas
            )
            self._stats_cache = None
            self._search_cache.clear()
            logger.info(f"批量添加 ModelArts 知识文档成功: {len(documents)} 条")
            return len(documents)
        except Exception as e:
            logger.error(f"批量添加知识文档失败: {e}")
            return 0

    def _build_document_text(
        self,
        category: str,
        title: str,
        content: str,
        tags: List[str]
    ) -> str:
        """构建用于向量嵌入的文档文本"""
        parts = []
        parts.append(f"分类: {category}")
        parts.append(f"标题: {title}")
        if tags:
            parts.append(f"标签: {', '.join(tags)}")
        parts.append(f"内容: {content}")
        return "\n".join(parts)

    def warm_up(self):
        """预热嵌入模型，避免首次搜索冷启动"""
        try:
            self.collection.query(query_texts=["预热"], n_results=1)
            logger.info("ModelArts 知识库嵌入模型预热完成")
        except Exception as e:
            logger.warning(f"预热失败（不影响使用）: {e}")

    def _make_cache_key(self, query: str, n_results: int,
                        category_filter: Optional[str],
                        tag_filter: Optional[str]) -> str:
        raw = f"{query}|{n_results}|{category_filter}|{tag_filter}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _get_cached_search(self, key: str) -> Optional[List]:
        if key in self._search_cache:
            ts, results = self._search_cache[key]
            if time.time() - ts < self._search_cache_ttl:
                return results
            del self._search_cache[key]
        return None

    def _put_search_cache(self, key: str, results: List):
        # 简单淘汰：超过上限时清除最旧的一半
        if len(self._search_cache) >= self._search_cache_max:
            sorted_keys = sorted(self._search_cache, key=lambda k: self._search_cache[k][0])
            for k in sorted_keys[:len(sorted_keys) // 2]:
                del self._search_cache[k]
        self._search_cache[key] = (time.time(), results)

    def search(
        self,
        query: str,
        n_results: int = 10,
        category_filter: Optional[str] = None,
        tag_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """语义搜索知识文档（带缓存）"""
        try:
            cache_key = self._make_cache_key(query, n_results, category_filter, tag_filter)
            cached = self._get_cached_search(cache_key)
            if cached is not None:
                logger.debug(f"搜索命中缓存: {query[:30]}")
                return cached

            where = None
            if category_filter and tag_filter:
                where = {
                    "$and": [
                        {"category": category_filter},
                        {"tags": {"$contains": tag_filter}}
                    ]
                }
            elif category_filter:
                where = {"category": category_filter}
            elif tag_filter:
                where = {"tags": {"$contains": tag_filter}}

            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where,
                include=["documents", "metadatas", "distances"]
            )

            formatted = []
            if results["ids"] and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    formatted.append({
                        "doc_id": doc_id,
                        "category": results["metadatas"][0][i].get("category", ""),
                        "title": results["metadatas"][0][i].get("title", ""),
                        "doc_url": results["metadatas"][0][i].get("doc_url", ""),
                        "tags": results["metadatas"][0][i].get("tags", ""),
                        "document": results["documents"][0][i],
                        "similarity": 1 - results["distances"][0][i],
                        "distance": results["distances"][0][i]
                    })

            self._put_search_cache(cache_key, formatted)
            return formatted
        except Exception as e:
            logger.error(f"搜索 ModelArts 知识库失败: {e}")
            return []

    def get_by_category(self, category: str) -> List[Dict[str, Any]]:
        """按分类获取所有文档"""
        try:
            results = self.collection.get(
                where={"category": category},
                include=["documents", "metadatas"]
            )
            formatted = []
            for i, doc_id in enumerate(results["ids"]):
                formatted.append({
                    "doc_id": doc_id,
                    "category": results["metadatas"][i].get("category", ""),
                    "title": results["metadatas"][i].get("title", ""),
                    "doc_url": results["metadatas"][i].get("doc_url", ""),
                    "tags": results["metadatas"][i].get("tags", ""),
                    "document": results["documents"][i]
                })
            return formatted
        except Exception as e:
            logger.error(f"按分类获取失败: {e}")
            return []

    def clear_all(self) -> bool:
        """清空所有数据"""
        try:
            self.client.delete_collection("modelarts_knowledge")
            self.collection = self._get_or_create_collection()
            self._stats_cache = None
            self._search_cache.clear()
            logger.info("清空 ModelArts 知识库成功")
            return True
        except Exception as e:
            logger.error(f"清空失败: {e}")
            return False

    def count(self) -> int:
        return self.collection.count()

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息（带缓存）"""
        now = time.time()
        if self._stats_cache and now - self._stats_cache_time < self._stats_cache_ttl:
            return self._stats_cache
        try:
            all_docs = self.collection.get(include=["metadatas"])
            category_count = {}
            for meta in all_docs["metadatas"]:
                cat = meta.get("category", "unknown")
                category_count[cat] = category_count.get(cat, 0) + 1
            stats = {
                "total_documents": len(all_docs["ids"]),
                "total_categories": len(category_count),
                "documents_by_category": category_count
            }
            self._stats_cache = stats
            self._stats_cache_time = now
            return stats
        except Exception as e:
            logger.error(f"获取统计失败: {e}")
            return {"total_documents": 0, "total_categories": 0, "documents_by_category": {}}


# 全局实例
_modelarts_store: Optional[ModelArtsKnowledgeStore] = None


def get_modelarts_store() -> ModelArtsKnowledgeStore:
    """获取全局 ModelArts 知识库实例"""
    global _modelarts_store
    if _modelarts_store is None:
        _modelarts_store = ModelArtsKnowledgeStore()
    return _modelarts_store
