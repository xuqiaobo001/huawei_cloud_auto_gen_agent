"""
Neo4j 图数据库存储模块 - 用于存储华为云服务依赖关系图
"""

from typing import Dict, List, Optional, Any
from utils.logger import get_logger
from utils.config_manager import get_config

logger = get_logger(__name__)


class ServiceGraphStore:
    """华为云服务依赖图存储（Neo4j）"""

    def __init__(self):
        config = get_config()
        neo4j_config = config.get("neo4j", {})

        self._uri = neo4j_config.get("uri", "bolt://localhost:7687")
        self._username = neo4j_config.get("username", "neo4j")
        self._password = neo4j_config.get("password", "")
        self._database = neo4j_config.get("database", "neo4j")
        self._driver = None
        self._connected = False

        self._connect()

    def _connect(self):
        """连接 Neo4j"""
        try:
            from neo4j import GraphDatabase
            self._driver = GraphDatabase.driver(
                self._uri,
                auth=(self._username, self._password),
            )
            # 验证连接
            self._driver.verify_connectivity()
            self._connected = True
            logger.info(f"Neo4j 连接成功: {self._uri}")
        except ImportError:
            logger.warning("neo4j 驱动未安装，图数据库功能不可用")
            self._connected = False
        except Exception as e:
            logger.warning(f"Neo4j 连接失败: {e}")
            self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def close(self):
        if self._driver:
            self._driver.close()
            self._connected = False

    # ===== 写操作 =====

    def upsert_service_node(self, service_id: str, label: str, short: str, category: str) -> bool:
        """创建或更新服务节点"""
        if not self._connected:
            return False
        try:
            with self._driver.session(database=self._database) as session:
                session.run(
                    """
                    MERGE (s:Service {id: $id})
                    SET s.label = $label, s.short = $short, s.category = $category
                    """,
                    id=service_id, label=label, short=short, category=category,
                )
            return True
        except Exception as e:
            logger.error(f"upsert_service_node 失败: {e}")
            return False

    def upsert_dependency(self, source: str, target: str, dep_type: str, description: str) -> bool:
        """创建或更新依赖边"""
        if not self._connected:
            return False
        try:
            with self._driver.session(database=self._database) as session:
                session.run(
                    """
                    MATCH (a:Service {id: $source}), (b:Service {id: $target})
                    MERGE (a)-[r:DEPENDS_ON {type: $type}]->(b)
                    SET r.description = $description
                    """,
                    source=source, target=target, type=dep_type, description=description,
                )
            return True
        except Exception as e:
            logger.error(f"upsert_dependency 失败: {e}")
            return False

    def clear_all(self) -> bool:
        """清空所有节点和边"""
        if not self._connected:
            return False
        try:
            with self._driver.session(database=self._database) as session:
                session.run("MATCH (n:Service) DETACH DELETE n")
            logger.info("Neo4j 图数据已清空")
            return True
        except Exception as e:
            logger.error(f"clear_all 失败: {e}")
            return False

    def populate_from_analyzer(self, analyzer) -> bool:
        """从分析器填充图数据"""
        if not self._connected:
            return False
        try:
            nodes = analyzer.get_all_nodes()
            edges = analyzer.get_all_edges()

            for node in nodes:
                self.upsert_service_node(node["id"], node["label"], node["short"], node["category"])

            for edge in edges:
                self.upsert_dependency(edge["source"], edge["target"], edge["type"], edge["description"])

            logger.info(f"图数据填充完成: {len(nodes)} 节点, {len(edges)} 边")
            return True
        except Exception as e:
            logger.error(f"populate_from_analyzer 失败: {e}")
            return False

    # ===== 读操作 =====

    def get_all_nodes_and_edges(self) -> Dict[str, Any]:
        """获取完整图数据"""
        if not self._connected:
            return {"nodes": [], "edges": []}
        try:
            with self._driver.session(database=self._database) as session:
                node_result = session.run(
                    "MATCH (s:Service) RETURN s.id AS id, s.label AS label, s.short AS short, s.category AS category"
                )
                nodes = [dict(record) for record in node_result]

                edge_result = session.run(
                    """
                    MATCH (a:Service)-[r:DEPENDS_ON]->(b:Service)
                    RETURN a.id AS source, b.id AS target, r.type AS type, r.description AS description
                    """
                )
                edges = [dict(record) for record in edge_result]

            return {"nodes": nodes, "edges": edges}
        except Exception as e:
            logger.error(f"get_all_nodes_and_edges 失败: {e}")
            return {"nodes": [], "edges": []}

    def get_service_dependencies(self, service_name: str) -> Dict[str, Any]:
        """获取单个服务的上下游依赖"""
        if not self._connected:
            return {}
        try:
            with self._driver.session(database=self._database) as session:
                # 服务自身信息
                svc = session.run(
                    "MATCH (s:Service {id: $id}) RETURN s.id AS id, s.label AS label, s.short AS short, s.category AS category",
                    id=service_name,
                ).single()
                if not svc:
                    return {"error": f"服务不存在: {service_name}"}

                # 该服务依赖的
                up_result = session.run(
                    """
                    MATCH (a:Service {id: $id})-[r:DEPENDS_ON]->(b:Service)
                    RETURN b.id AS service, b.label AS label, b.short AS short, b.category AS category,
                           r.type AS type, r.description AS description
                    """,
                    id=service_name,
                )
                depends_on = [dict(r) for r in up_result]

                # 依赖该服务的
                down_result = session.run(
                    """
                    MATCH (a:Service)-[r:DEPENDS_ON]->(b:Service {id: $id})
                    RETURN a.id AS service, a.label AS label, a.short AS short, a.category AS category,
                           r.type AS type, r.description AS description
                    """,
                    id=service_name,
                )
                depended_by = [dict(r) for r in down_result]

            return {
                "service": svc["id"],
                "label": svc["label"],
                "short": svc["short"],
                "category": svc["category"],
                "depends_on": depends_on,
                "depended_by": depended_by,
            }
        except Exception as e:
            logger.error(f"get_service_dependencies 失败: {e}")
            return {"error": str(e)}

    def get_stats(self) -> Dict[str, Any]:
        """获取图统计信息"""
        if not self._connected:
            return {}
        try:
            with self._driver.session(database=self._database) as session:
                node_count = session.run("MATCH (s:Service) RETURN count(s) AS c").single()["c"]
                edge_count = session.run("MATCH ()-[r:DEPENDS_ON]->() RETURN count(r) AS c").single()["c"]
            return {"total_services": node_count, "total_dependencies": edge_count}
        except Exception as e:
            logger.error(f"get_stats 失败: {e}")
            return {}

    def node_count(self) -> int:
        """获取节点数量"""
        if not self._connected:
            return 0
        try:
            with self._driver.session(database=self._database) as session:
                return session.run("MATCH (s:Service) RETURN count(s) AS c").single()["c"]
        except Exception:
            return 0


# 单例
_graph_store: Optional[ServiceGraphStore] = None


def get_graph_store() -> ServiceGraphStore:
    """获取全局图存储实例"""
    global _graph_store
    if _graph_store is None:
        _graph_store = ServiceGraphStore()
    return _graph_store
