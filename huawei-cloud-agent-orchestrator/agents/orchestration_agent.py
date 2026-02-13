"""
Agent编排引擎 - 简化版本
负责解析用户需求、生成工作流
"""

import json
import re
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

from models.workflow import Workflow, Task, TaskType, TaskStatus, PARAMETER_TEMPLATES
from services.huawei_cloud_service_registry import get_registry


class OrchestrationAgent:
    """Agent编排引擎主类"""

    def __init__(self, llm_client: Optional[Any] = None):
        self.llm_client = llm_client
        self.service_registry = get_registry()

    def plan(self, user_requirement: str, context: Optional[Dict[str, Any]] = None) -> Workflow:
        """根据用户需求生成工作流"""
        print(f"\n{'='*60}")
        print("开始解析用户需求")
        print(f"{'='*60}")
        print(f"用户需求: {user_requirement}")

        # 分析用户需求
        workflow = self._analyze_requirement(user_requirement, context)

        if workflow:
            print("\n✓ 成功生成工作流")
            return workflow

        # 默认工作流
        return self._create_default_workflow()

    def _analyze_requirement(self, requirement: str, context: Optional[Dict[str, Any]]) -> Optional[Workflow]:
        """分析用户需求"""
        requirement_lower = requirement.lower()

        if '部署' in requirement_lower and ('web' in requirement_lower or '网站' in requirement_lower or '应用' in requirement_lower):
            return self._create_web_application_workflow(requirement)

        if 'ecs' in requirement_lower or '服务器' in requirement_lower or '实例' in requirement_lower:
            return self._create_ecs_workflow(requirement)

        if 'vpc' in requirement_lower or '网络' in requirement_lower or '子网' in requirement_lower:
            return self._create_vpc_workflow(requirement)

        if any(kw in requirement_lower for kw in ['rds', '数据库', 'mysql', 'postgresql', 'sqlserver']):
            return self._create_rds_workflow(requirement)

        if '存储' in requirement_lower or 'obs' in requirement_lower:
            return self._create_obs_workflow(requirement)

        return None

    def _create_web_application_workflow(self, requirement: str) -> Workflow:
        """创建Web应用部署工作流"""
        print("\n  Web应用部署模板")

        config = self._parse_configuration(requirement)

        workflow = Workflow(
            name="部署Web应用",
            description="自动创建VPC、ECS实例和数据库",
            variables={
                "vpc_name": config.get("vpc_name", "web-app-vpc"),
                "vpc_cidr": config.get("vpc_cidr", "192.168.0.0/16"),
                "subnet_name": config.get("subnet_name", "web-app-subnet"),
                "subnet_cidr": config.get("subnet_cidr", "192.168.1.0/24"),
                "ecs_name": config.get("ecs_name", "web-server"),
                "ecs_flavor": config.get("flavor", "s6.large.2"),
                "image_id": config.get("image", "CentOS 7.9"),
            }
        )

        # 创建VPC
        workflow.add_task(Task(
            name="create_vpc",
            type=TaskType.HUAWEICLOUD_API,
            description="创建VPC网络",
            service="vpc",
            operation="create_vpc",
            parameters={
                "name": "{{ variables.vpc_name }}",
                "cidr": "{{ variables.vpc_cidr }}"
            }
        ))

        # 创建子网
        workflow.add_task(Task(
            name="create_subnet",
            type=TaskType.HUAWEICLOUD_API,
            description="创建子网",
            service="vpc",
            operation="create_subnet",
            depends_on=["create_vpc"],
            parameters={
                "name": "{{ variables.subnet_name }}",
                "cidr": "{{ variables.subnet_cidr }}",
                "vpc_id": "{{ outputs.create_vpc.vpc.id }}"
            }
        ))

        workflow.add_task(Task(
            name="create_ecs",
            type=TaskType.HUAWEICLOUD_API,
            description="创建Web服务器",
            service="ecs",
            operation="create_servers",
            depends_on=["create_subnet"],
            parameters={
                "server": {
                    "name": "{{ variables.ecs_name }}",
                    "flavorRef": "{{ variables.ecs_flavor }}",
                    "imageRef": "{{ variables.image_id }}",
                    "vpcid": "{{ outputs.create_vpc.vpc.id }}",
                    "nics": [{"subnet_id": "{{ outputs.create_subnet.subnet.id }}"}]
                }
            },
            timeout=600
        ))

        workflow.status = WorkflowStatus.READY
        return workflow

    def _create_ecs_workflow(self, requirement: str) -> Workflow:
        """创建ECS实例工作流"""
        print("\n  ECS实例创建模板")

        config = self._parse_configuration(requirement)

        workflow = Workflow(
            name="创建ECS实例",
            variables={
                "ecs_name": config.get("name", "my-server"),
                "ecs_flavor": config.get("flavor", "s6.large.2"),
                "vpc_id": config.get("vpc_id", "default-vpc"),
                "subnet_id": config.get("subnet_id", "default-subnet"),
                "image_id": config.get("image", "CentOS 7.9"),
            }
        )

        workflow.add_task(Task(
            name="create_ecs_instance",
            type=TaskType.HUAWEICLOUD_API,
            service="ecs",
            operation="create_servers",
            parameters={
                "server": {
                    "name": "{{ variables.ecs_name }}",
                    "flavorRef": "{{ variables.ecs_flavor }}",
                    "imageRef": "{{ variables.image_id }}",
                    "vpcid": "{{ variables.vpc_id }}",
                    "nics": [{"subnet_id": "{{ variables.subnet_id }}"}]
                }
            }
        ))

        workflow.status = WorkflowStatus.READY
        return workflow

    def _create_vpc_workflow(self, requirement: str) -> Workflow:
        """创建VPC网络工作流"""
        print("\n  VPC网络模板")

        config = self._parse_configuration(requirement)

        workflow = Workflow(
            name="创建VPC网络",
            variables={
                "vpc_name": config.get("name", "my-vpc"),
                "vpc_cidr": config.get("cidr", "192.168.0.0/16"),
                "subnet_name": config.get("subnet", "my-subnet"),
                "subnet_cidr": config.get("subnet_cidr", "192.168.1.0/24")
            }
        )

        workflow.add_task(Task(
            name="create_vpc",
            type=TaskType.HUAWEICLOUD_API,
            service="vpc",
            operation="create_vpc",
            parameters={
                "name": "{{ variables.vpc_name }}",
                "cidr": "{{ variables.vpc_cidr }}"
            }
        ))

        workflow.add_task(Task(
            name="create_subnet",
            type=TaskType.HUAWEICLOUD_API,
            service="vpc",
            operation="create_subnet",
            depends_on=["create_vpc"],
            parameters={
                "name": "{{ variables.subnet_name }}",
                "cidr": "{{ variables.subnet_cidr }}",
                "vpc_id": "{{ outputs.create_vpc.vpc.id }}"
            }
        ))

        workflow.status = WorkflowStatus.READY
        return workflow

    def _create_rds_workflow(self, requirement: str) -> Workflow:
        """创建数据库工作流"""
        print("\n  RDS数据库创建模板")

        # 数据库类型
        db_type = "MySQL"
        if "postgresql" in requirement.lower():
            db_type = "PostgreSQL"
        elif "sqlserver" in requirement.lower():
            db_type = "SQLServer"

        config = self._parse_configuration(requirement)

        workflow = Workflow(
            name=f"创建{db_type}数据库",
            variables={
                "db_name": config.get("name", "my-database"),
                "db_type": db_type,
                "vpc_id": config.get("vpc_id", "default-vpc"),
                "subnet_id": config.get("subnet_id", "default-subnet")
            }
        )

        workflow.add_task(Task(
            name="create_db_instance",
            type=TaskType.HUAWEICLOUD_API,
            service="rds",
            operation="create_instance",
            parameters={
                "name": "{{ variables.db_name }}",
                "datastore": {
                    "type": "{{ variables.db_type }}",
                    "version": "8.0"
                },
                "vpc_id": "{{ variables.vpc_id }}",
                "subnet_id": "{{ variables.subnet_id }}",
                "volume": {
                    "type": "COMMON",
                    "size": 100
                }
            }
        ))

        workflow.status = WorkflowStatus.READY
        return workflow

    def _create_obs_workflow(self, requirement: str) -> Workflow:
        """创建OBS存储桶工作流"""
        print("\n  OBS存储模板")

        config = self._parse_configuration(requirement)

        workflow = Workflow(
            name="创建OBS存储桶",
            variables={
                "bucket_name": config.get("name", "my-bucket"),
                "storage_class": config.get("storage", "STANDARD")
            }
        )

        workflow.add_task(Task(
            name="create_bucket",
            type=TaskType.HUAWEICLOUD_API,
            service="obs",
            operation="create_bucket",
            parameters={
                "bucket_name": "{{ variables.bucket_name }}",
                "storage_class": "{{ variables.storage_class }}"
            }
        ))

        workflow.status = WorkflowStatus.READY
        return workflow

    def _create_default_workflow(self) -> Workflow:
        """创建默认空工作流"""
        return Workflow(
            name="新建工作流",
            description="",
            tasks=[]
        )

    def _parse_configuration(self, requirement: str) -> Dict[str, Any]:
        """从需求中提取配置参数"""
        config = {}
        patterns = [
            (r'(?:名称|name)[\s:：]\s*(\w+)', 'name'),
            (r'(?:规格|flavor)[\s:：]\s*([\w\.]+)', 'flavor'),
            (r'(?:vpc|VPC)[\s:：]?\s*(\w+)', 'vpc_id'),
            (r'(?:子网|subnet)[\s:：]?\s*(\w+)', 'subnet_id'),
            (r'(?:CIDR|cidr)[\s:：]?\s*([\d\./]+)', 'cidr'),
        ]

        for pattern, key in patterns:
            match = re.search(pattern, requirement, re.IGNORECASE)
            if match:
                config[key] = match.group(1).strip()

        return config
