"""
向量数据库管理模块 - 用于存储和检索华为云服务操作信息
使用 ChromaDB 作为向量存储后端
"""

import chromadb
from chromadb.config import Settings
from typing import Dict, List, Optional, Any
import json
from utils.logger import get_logger

logger = get_logger(__name__)


class OperationVectorStore:
    """华为云操作向量存储"""

    def __init__(self, persist_directory: str = "./data/vector_db"):
        """
        初始化向量存储

        Args:
            persist_directory: 向量数据持久化目录
        """
        self.persist_directory = persist_directory

        # 初始化 ChromaDB 客户端
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        # 创建或获取集合
        self.collection = self._get_or_create_collection()

        logger.info(f"向量存储初始化完成，目录: {persist_directory}")

    def _get_or_create_collection(self):
        """获取或创建集合"""
        try:
            collection = self.client.get_collection(
                name="huawei_cloud_operations",
                embedding_function=None  # 使用默认的嵌入函数
            )
            logger.info(f"已存在集合，当前文档数: {collection.count()}")
            return collection
        except Exception:
            # 集合不存在，创建新集合
            collection = self.client.create_collection(
                name="huawei_cloud_operations",
                metadata={
                    "description": "华为云服务操作向量存储",
                    "created_at": "2026-02-03"
                }
            )
            logger.info("创建新集合: huawei_cloud_operations")
            return collection

    def add_operation(
        self,
        operation_id: str,
        service_name: str,
        operation_name: str,
        description: str,
        input_params: Dict[str, Any],
        output_params: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        添加单个操作到向量数据库

        Args:
            operation_id: 操作唯一ID (格式: service_name:operation_name)
            service_name: 服务名称
            operation_name: 操作名称
            description: 操作描述/用途
            input_params: 输入参数定义
            output_params: 输出参数定义
            metadata: 额外的元数据

        Returns:
            是否添加成功
        """
        try:
            # 构建文档文本 - 用于向量嵌入
            doc_text = self._build_document_text(
                service_name=service_name,
                operation_name=operation_name,
                description=description,
                input_params=input_params,
                output_params=output_params
            )

            # 构建元数据
            metadatas = {
                "service_name": service_name,
                "operation_name": operation_name,
                "operation_id": operation_id,
                "description": description,
            }
            if metadata:
                metadatas.update(metadata)

            # 添加到集合
            self.collection.add(
                ids=[operation_id],
                documents=[doc_text],
                metadatas=[metadatas]
            )

            logger.debug(f"添加操作成功: {operation_id}")
            return True

        except Exception as e:
            logger.error(f"添加操作失败 {operation_id}: {e}")
            return False

    def batch_add_operations(self, operations: List[Dict[str, Any]]) -> int:
        """
        批量添加操作

        Args:
            operations: 操作列表，每个操作是一个字典

        Returns:
            成功添加的数量
        """
        try:
            ids = []
            documents = []
            metadatas = []

            for op in operations:
                operation_id = op.get("operation_id")
                service_name = op.get("service_name")
                operation_name = op.get("operation_name")
                description = op.get("description", "")
                input_params = op.get("input_params", {})
                output_params = op.get("output_params", {})
                metadata = op.get("metadata", {})

                # 构建文档文本
                doc_text = self._build_document_text(
                    service_name=service_name,
                    operation_name=operation_name,
                    description=description,
                    input_params=input_params,
                    output_params=output_params
                )

                ids.append(operation_id)
                documents.append(doc_text)

                # 构建元数据
                metadatas.append({
                    "service_name": service_name,
                    "operation_name": operation_name,
                    "operation_id": operation_id,
                    "description": description,
                    **metadata
                })

            # 批量添加
            self.collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )

            logger.info(f"批量添加操作成功: {len(operations)} 条")
            return len(operations)

        except Exception as e:
            logger.error(f"批量添加操作失败: {e}")
            return 0

    def _build_document_text(
        self,
        service_name: str,
        operation_name: str,
        description: str,
        input_params: Dict[str, Any],
        output_params: Dict[str, Any]
    ) -> str:
        """
        构建用于向量嵌入的文档文本

        Args:
            service_name: 服务名称
            operation_name: 操作名称
            description: 操作描述
            input_params: 输入参数
            output_params: 输出参数

        Returns:
            构建好的文档文本
        """
        parts = []

        # 服务和操作名称
        parts.append(f"服务: {service_name}")
        parts.append(f"操作: {operation_name}")

        # 描述
        if description:
            parts.append(f"描述: {description}")

        # 输入参数
        if input_params:
            parts.append("输入参数:")
            for param_name, param_info in input_params.items():
                param_desc = param_info.get("description", "")
                param_type = param_info.get("type", "string")
                parts.append(f"  - {param_name} ({param_type}): {param_desc}")

        # 输出参数
        if output_params:
            parts.append("输出参数:")
            for param_name, param_info in output_params.items():
                param_desc = param_info.get("description", "")
                param_type = param_info.get("type", "string")
                parts.append(f"  - {param_name} ({param_type}): {param_desc}")

        # 用换行连接所有部分
        return "\n".join(parts)

    def search(
        self,
        query: str,
        n_results: int = 10,
        service_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        搜索相关操作

        Args:
            query: 查询文本
            n_results: 返回结果数量
            service_filter: 服务过滤条件 (可选)

        Returns:
            搜索结果列表
        """
        try:
            # 构建过滤条件
            where = None
            if service_filter:
                where = {"service_name": service_filter}

            # 查询
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where,
                include=["documents", "metadatas", "distances"]
            )

            # 格式化结果
            formatted_results = []
            if results["ids"] and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    formatted_results.append({
                        "operation_id": doc_id,
                        "service_name": results["metadatas"][0][i]["service_name"],
                        "operation_name": results["metadatas"][0][i]["operation_name"],
                        "description": results["metadatas"][0][i].get("description", ""),
                        "document": results["documents"][0][i],
                        "similarity": 1 - results["distances"][0][i],  # 转换为相似度
                        "distance": results["distances"][0][i]
                    })

            return formatted_results

        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []

    def search_by_service_operations(
        self,
        service_operations: List[Dict[str, str]],
        n_results_per_op: int = 5
    ) -> List[Dict[str, Any]]:
        """
        按服务+操作对进行针对性检索

        Args:
            service_operations: 列表，每项含 service 和 operation
            n_results_per_op: 每个操作对返回的结果数

        Returns:
            去重后的搜索结果列表
        """
        seen_ids = set()
        results = []

        for pair in service_operations:
            service = pair.get("service", "")
            operation = pair.get("operation", "")
            if not service or not operation:
                continue

            # 精确搜索：用操作名作为查询，服务名作为过滤
            hits = self.search(
                query=operation,
                n_results=n_results_per_op,
                service_filter=service
            )

            if not hits:
                # 回退：仅按服务名搜索
                hits = self.search(
                    query=f"{service} {operation}",
                    n_results=n_results_per_op,
                    service_filter=service
                )

            for hit in hits:
                op_id = hit.get("operation_id", "")
                if op_id not in seen_ids:
                    seen_ids.add(op_id)
                    results.append(hit)

        return results

    def get_all_operations(
        self,
        service_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取所有操作

        Args:
            service_filter: 服务过滤条件 (可选)

        Returns:
            操作列表
        """
        try:
            where = None
            if service_filter:
                where = {"service_name": service_filter}

            results = self.collection.get(
                where=where,
                include=["documents", "metadatas"]
            )

            formatted_results = []
            for i, doc_id in enumerate(results["ids"]):
                formatted_results.append({
                    "operation_id": doc_id,
                    "service_name": results["metadatas"][i]["service_name"],
                    "operation_name": results["metadatas"][i]["operation_name"],
                    "description": results["metadatas"][i].get("description", ""),
                    "document": results["documents"][i]
                })

            return formatted_results

        except Exception as e:
            logger.error(f"获取所有操作失败: {e}")
            return []

    def delete_operation(self, operation_id: str) -> bool:
        """
        删除操作

        Args:
            operation_id: 操作ID

        Returns:
            是否删除成功
        """
        try:
            self.collection.delete(ids=[operation_id])
            logger.debug(f"删除操作成功: {operation_id}")
            return True
        except Exception as e:
            logger.error(f"删除操作失败 {operation_id}: {e}")
            return False

    def clear_all(self) -> bool:
        """
        清空所有数据

        Returns:
            是否清空成功
        """
        try:
            # 删除并重新创建集合
            self.client.delete_collection("huawei_cloud_operations")
            self.collection = self._get_or_create_collection()
            logger.info("清空所有数据成功")
            return True
        except Exception as e:
            logger.error(f"清空数据失败: {e}")
            return False

    def count(self) -> int:
        """获取操作总数"""
        return self.collection.count()

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            all_ops = self.get_all_operations()

            # 按服务统计
            service_count = {}
            for op in all_ops:
                service = op["service_name"]
                service_count[service] = service_count.get(service, 0) + 1

            return {
                "total_operations": len(all_ops),
                "total_services": len(service_count),
                "operations_by_service": service_count
            }
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {
                "total_operations": 0,
                "total_services": 0,
                "operations_by_service": {}
            }


# 全局向量存储实例
_vector_store: Optional[OperationVectorStore] = None


def get_vector_store() -> OperationVectorStore:
    """获取全局向量存储实例"""
    global _vector_store
    if _vector_store is None:
        _vector_store = OperationVectorStore()
    return _vector_store
