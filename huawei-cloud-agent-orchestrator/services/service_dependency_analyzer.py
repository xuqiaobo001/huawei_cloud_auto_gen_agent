"""
华为云服务依赖关系分析器
分析和管理华为云服务之间的依赖关系，用于知识图谱构建和可视化
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from utils.logger import get_logger

logger = get_logger(__name__)


class DependencyType(str, Enum):
    """依赖类型"""
    REQUIRES = "requires"        # 强依赖：必须先创建
    OPTIONAL = "optional"        # 可选依赖：推荐配合使用
    MONITORS = "monitors"        # 监控关系：监控/审计目标服务
    INTEGRATES = "integrates"    # 集成关系：深度集成协作


class ServiceCategory(str, Enum):
    """服务类别"""
    COMPUTE = "compute"
    NETWORK = "network"
    STORAGE = "storage"
    DATABASE = "database"
    SECURITY = "security"
    MONITORING = "monitoring"
    CONTAINER = "container"
    MIDDLEWARE = "middleware"
    APPLICATION = "application"
    AI = "ai"
    BIG_DATA = "big_data"
    MEDIA = "media"
    MIGRATION = "migration"
    MANAGEMENT = "management"


# 服务分类映射
SERVICE_CATEGORIES: Dict[str, Dict[str, str]] = {
    # 计算
    "ecs": {"category": ServiceCategory.COMPUTE, "label": "弹性云服务器", "short": "ECS"},
    "bms": {"category": ServiceCategory.COMPUTE, "label": "裸金属服务器", "short": "BMS"},
    "functiongraph": {"category": ServiceCategory.COMPUTE, "label": "函数工作流", "short": "FunctionGraph"},
    "as": {"category": ServiceCategory.COMPUTE, "label": "弹性伸缩", "short": "AS"},

    # 网络
    "vpc": {"category": ServiceCategory.NETWORK, "label": "虚拟私有云", "short": "VPC"},
    "elb": {"category": ServiceCategory.NETWORK, "label": "弹性负载均衡", "short": "ELB"},
    "eip": {"category": ServiceCategory.NETWORK, "label": "弹性公网IP", "short": "EIP"},
    "nat": {"category": ServiceCategory.NETWORK, "label": "NAT网关", "short": "NAT"},
    "dns": {"category": ServiceCategory.NETWORK, "label": "云解析服务", "short": "DNS"},
    "cdn": {"category": ServiceCategory.NETWORK, "label": "内容分发网络", "short": "CDN"},
    "vpn": {"category": ServiceCategory.NETWORK, "label": "虚拟专用网络", "short": "VPN"},
    "dc": {"category": ServiceCategory.NETWORK, "label": "云专线", "short": "DC"},
    "vpcep": {"category": ServiceCategory.NETWORK, "label": "VPC终端节点", "short": "VPCEP"},

    # 存储
    "obs": {"category": ServiceCategory.STORAGE, "label": "对象存储服务", "short": "OBS"},
    "evs": {"category": ServiceCategory.STORAGE, "label": "云硬盘", "short": "EVS"},
    "sfs": {"category": ServiceCategory.STORAGE, "label": "弹性文件服务", "short": "SFS"},
    "csbs": {"category": ServiceCategory.STORAGE, "label": "云服务器备份", "short": "CSBS"},
    "cbr": {"category": ServiceCategory.STORAGE, "label": "云备份", "short": "CBR"},

    # 数据库
    "rds": {"category": ServiceCategory.DATABASE, "label": "关系型数据库", "short": "RDS"},
    "dds": {"category": ServiceCategory.DATABASE, "label": "文档数据库", "short": "DDS"},
    "gaussdb": {"category": ServiceCategory.DATABASE, "label": "GaussDB", "short": "GaussDB"},
    "drs": {"category": ServiceCategory.DATABASE, "label": "数据复制服务", "short": "DRS"},

    # 缓存/中间件
    "dcs": {"category": ServiceCategory.MIDDLEWARE, "label": "分布式缓存", "short": "DCS"},
    "dms": {"category": ServiceCategory.MIDDLEWARE, "label": "分布式消息", "short": "DMS"},
    "roma": {"category": ServiceCategory.MIDDLEWARE, "label": "应用与数据集成", "short": "ROMA"},

    # 安全
    "iam": {"category": ServiceCategory.SECURITY, "label": "统一身份认证", "short": "IAM"},
    "waf": {"category": ServiceCategory.SECURITY, "label": "Web应用防火墙", "short": "WAF"},
    "kms": {"category": ServiceCategory.SECURITY, "label": "密钥管理", "short": "KMS"},
    "scm": {"category": ServiceCategory.SECURITY, "label": "SSL证书管理", "short": "SCM"},
    "dbss": {"category": ServiceCategory.SECURITY, "label": "数据库安全", "short": "DBSS"},
    "hss": {"category": ServiceCategory.SECURITY, "label": "主机安全", "short": "HSS"},
    "anti_ddos": {"category": ServiceCategory.SECURITY, "label": "Anti-DDoS", "short": "Anti-DDoS"},

    # 监控/运维
    "ces": {"category": ServiceCategory.MONITORING, "label": "云监控服务", "short": "CES"},
    "lts": {"category": ServiceCategory.MONITORING, "label": "云日志服务", "short": "LTS"},
    "cts": {"category": ServiceCategory.MONITORING, "label": "云审计服务", "short": "CTS"},
    "smn": {"category": ServiceCategory.MONITORING, "label": "消息通知", "short": "SMN"},
    "apm": {"category": ServiceCategory.MONITORING, "label": "应用性能管理", "short": "APM"},

    # 容器
    "cce": {"category": ServiceCategory.CONTAINER, "label": "云容器引擎", "short": "CCE"},
    "swr": {"category": ServiceCategory.CONTAINER, "label": "容器镜像服务", "short": "SWR"},
    "cci": {"category": ServiceCategory.CONTAINER, "label": "云容器实例", "short": "CCI"},

    # 应用
    "apig": {"category": ServiceCategory.APPLICATION, "label": "API网关", "short": "APIG"},
    "servicestage": {"category": ServiceCategory.APPLICATION, "label": "应用管理与运维", "short": "ServiceStage"},

    # AI
    "modelarts": {"category": ServiceCategory.AI, "label": "AI开发平台", "short": "ModelArts"},

    # 大数据
    "mrs": {"category": ServiceCategory.BIG_DATA, "label": "MapReduce服务", "short": "MRS"},
    "dli": {"category": ServiceCategory.BIG_DATA, "label": "数据湖探索", "short": "DLI"},
    "css": {"category": ServiceCategory.BIG_DATA, "label": "云搜索服务", "short": "CSS"},

    # 迁移
    "sms": {"category": ServiceCategory.MIGRATION, "label": "主机迁移服务", "short": "SMS"},
}


# 服务依赖关系定义
SERVICE_DEPENDENCIES: List[Dict[str, str]] = [
    # === 计算服务依赖 ===
    {"source": "ecs", "target": "vpc", "type": DependencyType.REQUIRES, "description": "ECS实例必须部署在VPC子网中"},
    {"source": "ecs", "target": "evs", "type": DependencyType.REQUIRES, "description": "ECS使用EVS作为系统盘和数据盘"},
    {"source": "ecs", "target": "eip", "type": DependencyType.OPTIONAL, "description": "ECS可绑定EIP实现公网访问"},
    {"source": "ecs", "target": "iam", "type": DependencyType.REQUIRES, "description": "ECS操作需要IAM权限认证"},
    {"source": "ecs", "target": "kms", "type": DependencyType.OPTIONAL, "description": "ECS可使用KMS加密磁盘数据"},
    {"source": "bms", "target": "vpc", "type": DependencyType.REQUIRES, "description": "裸金属服务器部署在VPC中"},
    {"source": "bms", "target": "eip", "type": DependencyType.OPTIONAL, "description": "BMS可绑定EIP"},
    {"source": "as", "target": "ecs", "type": DependencyType.REQUIRES, "description": "弹性伸缩管理ECS实例组"},
    {"source": "as", "target": "elb", "type": DependencyType.OPTIONAL, "description": "伸缩组可关联ELB自动注册"},
    {"source": "functiongraph", "target": "obs", "type": DependencyType.OPTIONAL, "description": "函数可由OBS事件触发"},
    {"source": "functiongraph", "target": "apig", "type": DependencyType.OPTIONAL, "description": "函数可通过API网关暴露"},
    {"source": "functiongraph", "target": "smn", "type": DependencyType.OPTIONAL, "description": "函数可由SMN消息触发"},
    {"source": "functiongraph", "target": "vpc", "type": DependencyType.OPTIONAL, "description": "函数可配置VPC访问"},

    # === 网络服务依赖 ===
    {"source": "elb", "target": "vpc", "type": DependencyType.REQUIRES, "description": "ELB部署在VPC子网中"},
    {"source": "elb", "target": "eip", "type": DependencyType.OPTIONAL, "description": "公网ELB需要绑定EIP"},
    {"source": "elb", "target": "ecs", "type": DependencyType.REQUIRES, "description": "ELB后端服务器为ECS实例"},
    {"source": "elb", "target": "scm", "type": DependencyType.OPTIONAL, "description": "HTTPS监听器需要SSL证书"},
    {"source": "nat", "target": "vpc", "type": DependencyType.REQUIRES, "description": "NAT网关部署在VPC中"},
    {"source": "nat", "target": "eip", "type": DependencyType.REQUIRES, "description": "NAT网关需要绑定EIP"},
    {"source": "vpn", "target": "vpc", "type": DependencyType.REQUIRES, "description": "VPN网关部署在VPC中"},
    {"source": "vpn", "target": "eip", "type": DependencyType.REQUIRES, "description": "VPN网关需要EIP"},
    {"source": "dc", "target": "vpc", "type": DependencyType.REQUIRES, "description": "云专线连接到VPC"},
    {"source": "vpcep", "target": "vpc", "type": DependencyType.REQUIRES, "description": "终端节点部署在VPC中"},
    {"source": "cdn", "target": "obs", "type": DependencyType.OPTIONAL, "description": "CDN可使用OBS作为源站"},
    {"source": "cdn", "target": "elb", "type": DependencyType.OPTIONAL, "description": "CDN可使用ELB作为源站"},
    {"source": "cdn", "target": "dns", "type": DependencyType.OPTIONAL, "description": "CDN加速域名需要DNS解析"},
    {"source": "dns", "target": "eip", "type": DependencyType.OPTIONAL, "description": "DNS记录可指向EIP"},
    {"source": "dns", "target": "elb", "type": DependencyType.OPTIONAL, "description": "DNS记录可指向ELB"},
    {"source": "waf", "target": "elb", "type": DependencyType.OPTIONAL, "description": "WAF可对接ELB防护Web应用"},
    {"source": "waf", "target": "dns", "type": DependencyType.OPTIONAL, "description": "WAF云模式需要DNS CNAME"},

    # === 存储服务依赖 ===
    {"source": "obs", "target": "iam", "type": DependencyType.REQUIRES, "description": "OBS访问需要IAM认证授权"},
    {"source": "obs", "target": "kms", "type": DependencyType.OPTIONAL, "description": "OBS可使用KMS加密对象"},
    {"source": "evs", "target": "kms", "type": DependencyType.OPTIONAL, "description": "EVS可使用KMS加密云硬盘"},
    {"source": "sfs", "target": "vpc", "type": DependencyType.REQUIRES, "description": "SFS文件系统部署在VPC中"},
    {"source": "csbs", "target": "ecs", "type": DependencyType.REQUIRES, "description": "CSBS备份ECS服务器"},
    {"source": "csbs", "target": "obs", "type": DependencyType.OPTIONAL, "description": "备份数据可存储到OBS"},
    {"source": "cbr", "target": "ecs", "type": DependencyType.OPTIONAL, "description": "CBR可备份ECS"},
    {"source": "cbr", "target": "evs", "type": DependencyType.OPTIONAL, "description": "CBR可备份EVS云硬盘"},
    {"source": "cbr", "target": "sfs", "type": DependencyType.OPTIONAL, "description": "CBR可备份SFS文件系统"},

    # === 数据库服务依赖 ===
    {"source": "rds", "target": "vpc", "type": DependencyType.REQUIRES, "description": "RDS实例部署在VPC子网中"},
    {"source": "rds", "target": "evs", "type": DependencyType.REQUIRES, "description": "RDS使用EVS存储数据"},
    {"source": "rds", "target": "kms", "type": DependencyType.OPTIONAL, "description": "RDS可使用KMS加密数据"},
    {"source": "dds", "target": "vpc", "type": DependencyType.REQUIRES, "description": "DDS部署在VPC中"},
    {"source": "gaussdb", "target": "vpc", "type": DependencyType.REQUIRES, "description": "GaussDB部署在VPC中"},
    {"source": "drs", "target": "rds", "type": DependencyType.OPTIONAL, "description": "DRS可迁移RDS数据"},
    {"source": "drs", "target": "gaussdb", "type": DependencyType.OPTIONAL, "description": "DRS可迁移GaussDB数据"},
    {"source": "drs", "target": "vpc", "type": DependencyType.REQUIRES, "description": "DRS任务需要VPC网络"},

    # === 中间件依赖 ===
    {"source": "dcs", "target": "vpc", "type": DependencyType.REQUIRES, "description": "DCS实例部署在VPC中"},
    {"source": "dms", "target": "vpc", "type": DependencyType.REQUIRES, "description": "DMS实例部署在VPC中"},
    {"source": "roma", "target": "vpc", "type": DependencyType.REQUIRES, "description": "ROMA实例部署在VPC中"},

    # === 容器服务依赖 ===
    {"source": "cce", "target": "vpc", "type": DependencyType.REQUIRES, "description": "CCE集群部署在VPC中"},
    {"source": "cce", "target": "ecs", "type": DependencyType.REQUIRES, "description": "CCE节点为ECS实例"},
    {"source": "cce", "target": "evs", "type": DependencyType.OPTIONAL, "description": "CCE可使用EVS持久化存储"},
    {"source": "cce", "target": "sfs", "type": DependencyType.OPTIONAL, "description": "CCE可使用SFS共享存储"},
    {"source": "cce", "target": "elb", "type": DependencyType.OPTIONAL, "description": "CCE Service可对接ELB"},
    {"source": "cce", "target": "swr", "type": DependencyType.INTEGRATES, "description": "CCE从SWR拉取容器镜像"},
    {"source": "cce", "target": "obs", "type": DependencyType.OPTIONAL, "description": "CCE可使用OBS存储"},
    {"source": "cci", "target": "vpc", "type": DependencyType.REQUIRES, "description": "CCI部署在VPC中"},
    {"source": "cci", "target": "swr", "type": DependencyType.INTEGRATES, "description": "CCI从SWR拉取镜像"},
    {"source": "swr", "target": "obs", "type": DependencyType.INTEGRATES, "description": "SWR镜像存储在OBS中"},

    # === 安全服务依赖 ===
    {"source": "hss", "target": "ecs", "type": DependencyType.MONITORS, "description": "HSS监控保护ECS主机"},
    {"source": "dbss", "target": "rds", "type": DependencyType.MONITORS, "description": "DBSS审计保护RDS数据库"},
    {"source": "dbss", "target": "gaussdb", "type": DependencyType.MONITORS, "description": "DBSS审计保护GaussDB"},
    {"source": "anti_ddos", "target": "eip", "type": DependencyType.MONITORS, "description": "Anti-DDoS防护EIP"},
    {"source": "scm", "target": "elb", "type": DependencyType.OPTIONAL, "description": "SSL证书可部署到ELB"},
    {"source": "scm", "target": "cdn", "type": DependencyType.OPTIONAL, "description": "SSL证书可部署到CDN"},

    # === 监控运维依赖 ===
    {"source": "ces", "target": "ecs", "type": DependencyType.MONITORS, "description": "CES监控ECS指标"},
    {"source": "ces", "target": "rds", "type": DependencyType.MONITORS, "description": "CES监控RDS指标"},
    {"source": "ces", "target": "elb", "type": DependencyType.MONITORS, "description": "CES监控ELB指标"},
    {"source": "ces", "target": "evs", "type": DependencyType.MONITORS, "description": "CES监控EVS指标"},
    {"source": "ces", "target": "dcs", "type": DependencyType.MONITORS, "description": "CES监控DCS指标"},
    {"source": "ces", "target": "cce", "type": DependencyType.MONITORS, "description": "CES监控CCE集群指标"},
    {"source": "ces", "target": "smn", "type": DependencyType.INTEGRATES, "description": "CES告警通过SMN发送通知"},
    {"source": "lts", "target": "ecs", "type": DependencyType.MONITORS, "description": "LTS采集ECS日志"},
    {"source": "lts", "target": "cce", "type": DependencyType.MONITORS, "description": "LTS采集CCE容器日志"},
    {"source": "lts", "target": "functiongraph", "type": DependencyType.MONITORS, "description": "LTS采集函数执行日志"},
    {"source": "cts", "target": "obs", "type": DependencyType.INTEGRATES, "description": "CTS审计日志存储到OBS"},
    {"source": "cts", "target": "smn", "type": DependencyType.OPTIONAL, "description": "CTS可通过SMN发送审计通知"},
    {"source": "apm", "target": "ecs", "type": DependencyType.MONITORS, "description": "APM监控ECS上的应用性能"},
    {"source": "apm", "target": "cce", "type": DependencyType.MONITORS, "description": "APM监控CCE中的微服务"},

    # === 应用服务依赖 ===
    {"source": "apig", "target": "vpc", "type": DependencyType.REQUIRES, "description": "APIG实例部署在VPC中"},
    {"source": "apig", "target": "ecs", "type": DependencyType.OPTIONAL, "description": "APIG后端可对接ECS"},
    {"source": "apig", "target": "cce", "type": DependencyType.OPTIONAL, "description": "APIG后端可对接CCE"},
    {"source": "apig", "target": "functiongraph", "type": DependencyType.OPTIONAL, "description": "APIG后端可对接FunctionGraph"},
    {"source": "servicestage", "target": "cce", "type": DependencyType.REQUIRES, "description": "ServiceStage基于CCE部署应用"},
    {"source": "servicestage", "target": "swr", "type": DependencyType.INTEGRATES, "description": "ServiceStage使用SWR镜像"},
    {"source": "servicestage", "target": "elb", "type": DependencyType.OPTIONAL, "description": "ServiceStage可配置ELB"},

    # === AI/大数据依赖 ===
    {"source": "modelarts", "target": "obs", "type": DependencyType.REQUIRES, "description": "ModelArts数据集和模型存储在OBS"},
    {"source": "modelarts", "target": "vpc", "type": DependencyType.OPTIONAL, "description": "ModelArts可配置VPC访问"},
    {"source": "mrs", "target": "vpc", "type": DependencyType.REQUIRES, "description": "MRS集群部署在VPC中"},
    {"source": "mrs", "target": "obs", "type": DependencyType.INTEGRATES, "description": "MRS可读写OBS数据"},
    {"source": "dli", "target": "obs", "type": DependencyType.INTEGRATES, "description": "DLI查询OBS中的数据"},
    {"source": "dli", "target": "vpc", "type": DependencyType.OPTIONAL, "description": "DLI可配置VPC对等连接"},
    {"source": "css", "target": "vpc", "type": DependencyType.REQUIRES, "description": "CSS集群部署在VPC中"},

    # === 迁移服务依赖 ===
    {"source": "sms", "target": "ecs", "type": DependencyType.REQUIRES, "description": "SMS将源服务器迁移到ECS"},
    {"source": "sms", "target": "vpc", "type": DependencyType.REQUIRES, "description": "SMS目标ECS需要VPC"},
]


class ServiceDependencyAnalyzer:
    """华为云服务依赖关系分析器"""

    def __init__(self):
        self._categories = SERVICE_CATEGORIES
        self._dependencies = SERVICE_DEPENDENCIES
        logger.info(f"服务依赖分析器初始化: {len(self._categories)} 个服务, {len(self._dependencies)} 条依赖")

    def get_all_nodes(self) -> List[Dict[str, Any]]:
        """获取所有服务节点"""
        nodes = []
        for service_id, info in self._categories.items():
            nodes.append({
                "id": service_id,
                "label": info["label"],
                "short": info["short"],
                "category": info["category"].value if isinstance(info["category"], ServiceCategory) else info["category"],
            })
        return nodes

    def get_all_edges(self) -> List[Dict[str, Any]]:
        """获取所有依赖边"""
        edges = []
        for dep in self._dependencies:
            # 只返回两端节点都存在的边
            if dep["source"] in self._categories and dep["target"] in self._categories:
                edges.append({
                    "source": dep["source"],
                    "target": dep["target"],
                    "type": dep["type"].value if isinstance(dep["type"], DependencyType) else dep["type"],
                    "description": dep["description"],
                })
        return edges

    def get_service_dependencies(self, service_name: str) -> Dict[str, Any]:
        """获取单个服务的上下游依赖"""
        if service_name not in self._categories:
            return {"error": f"服务不存在: {service_name}"}

        info = self._categories[service_name]
        upstream = []   # 该服务依赖的（source=service_name）
        downstream = [] # 依赖该服务的（target=service_name）

        for dep in self._dependencies:
            src = dep["source"]
            tgt = dep["target"]
            dep_type = dep["type"].value if isinstance(dep["type"], DependencyType) else dep["type"]

            if src == service_name and tgt in self._categories:
                tgt_info = self._categories[tgt]
                upstream.append({
                    "service": tgt,
                    "label": tgt_info["label"],
                    "short": tgt_info["short"],
                    "category": tgt_info["category"].value if isinstance(tgt_info["category"], ServiceCategory) else tgt_info["category"],
                    "type": dep_type,
                    "description": dep["description"],
                })
            elif tgt == service_name and src in self._categories:
                src_info = self._categories[src]
                downstream.append({
                    "service": src,
                    "label": src_info["label"],
                    "short": src_info["short"],
                    "category": src_info["category"].value if isinstance(src_info["category"], ServiceCategory) else src_info["category"],
                    "type": dep_type,
                    "description": dep["description"],
                })

        return {
            "service": service_name,
            "label": info["label"],
            "short": info["short"],
            "category": info["category"].value if isinstance(info["category"], ServiceCategory) else info["category"],
            "depends_on": upstream,
            "depended_by": downstream,
        }

    def get_stats(self) -> Dict[str, Any]:
        """获取图统计信息"""
        nodes = self.get_all_nodes()
        edges = self.get_all_edges()

        # 按类别统计
        category_count: Dict[str, int] = {}
        for node in nodes:
            cat = node["category"]
            category_count[cat] = category_count.get(cat, 0) + 1

        # 按依赖类型统计
        type_count: Dict[str, int] = {}
        for edge in edges:
            t = edge["type"]
            type_count[t] = type_count.get(t, 0) + 1

        # 被依赖最多的服务（入度）
        in_degree: Dict[str, int] = {}
        out_degree: Dict[str, int] = {}
        for edge in edges:
            in_degree[edge["target"]] = in_degree.get(edge["target"], 0) + 1
            out_degree[edge["source"]] = out_degree.get(edge["source"], 0) + 1

        top_depended = sorted(in_degree.items(), key=lambda x: -x[1])[:10]
        top_depending = sorted(out_degree.items(), key=lambda x: -x[1])[:10]

        return {
            "total_services": len(nodes),
            "total_dependencies": len(edges),
            "categories": category_count,
            "dependency_types": type_count,
            "top_depended": [{"service": s, "count": c} for s, c in top_depended],
            "top_depending": [{"service": s, "count": c} for s, c in top_depending],
        }


# 单例
_analyzer: Optional[ServiceDependencyAnalyzer] = None


def get_analyzer() -> ServiceDependencyAnalyzer:
    """获取全局分析器实例"""
    global _analyzer
    if _analyzer is None:
        _analyzer = ServiceDependencyAnalyzer()
    return _analyzer
