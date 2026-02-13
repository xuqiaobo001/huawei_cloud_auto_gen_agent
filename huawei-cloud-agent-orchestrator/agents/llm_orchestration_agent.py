"""
基于LLM的智能Agent编排引擎
使用大语言模型理解用户需求并生成工作流
"""

import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

from models.workflow import Workflow, Task, TaskType, TaskStatus, WorkflowStatus, PARAMETER_TEMPLATES
from services.huawei_cloud_service_registry import get_registry
from services.llm_client import LLMClient
from utils.config_manager import get_config
from utils.vector_store import get_vector_store


class LLMOrchestrationAgent:
    """
    基于LLM的智能Agent编排引擎

    核心职责:
    1. 使用LLM理解用户的自然语言需求
    2. 调用LLM生成工作流定义
    3. 验证和优化生成的工流
    4. 提供工作流解释和改进功能

    使用示例:
        agent = LLMOrchestrationAgent()
        workflow = agent.plan("部署一个Web应用，包含ECS和RDS")
        explanation = agent.explain(workflow)
    """

    def __init__(self):
        self.config = get_config()
        self.service_registry = get_registry()
        self.llm_client = LLMClient()
        self.logger = LLMClient().logger  # 复用logger

    def is_llm_available(self) -> bool:
        """检查LLM是否可用"""
        return self.llm_client.is_available()

    def plan(self, user_requirement: str, context: Optional[Dict[str, Any]] = None) -> Workflow:
        """
        基于LLM生成工作流（含两阶段检索、参数模板注入、架构规划、验证重试）

        Args:
            user_requirement: 用户的自然语言描述
            context: 可选上下文（区域、项目等）

        Returns:
            Workflow: 生成的可执行工作流
        """
        print(f"\n{'='*60}")
        print("开始解析用户需求 (使用LLM)")
        print(f"{'='*60}")
        print(f"用户需求: {user_requirement}")

        # Stage 0: 架构规划 + 识别所需操作 (P3 subsumes P0)
        architecture_plan = None
        identified_ops = None
        if self.is_llm_available():
            print("\n[Stage 0] 生成架构计划...")
            architecture_plan = self.llm_client.generate_architecture_plan(user_requirement)
            if architecture_plan:
                identified_ops = architecture_plan.get("services_needed", [])
                print(f"  ✓ 架构模式: {architecture_plan.get('pattern', 'unknown')}")
                print(f"  ✓ DFX级别: {architecture_plan.get('dfx_level', 'unknown')}")
                print(f"  ✓ 识别到 {len(identified_ops)} 个所需操作")
            else:
                print("  ⚠ 架构计划生成失败，尝试轻量级操作识别...")
                identified_ops = self.llm_client.identify_required_operations(user_requirement)
                if identified_ops:
                    print(f"  ✓ 识别到 {len(identified_ops)} 个所需操作")
                else:
                    print("  ⚠ 操作识别也失败，将使用广泛搜索")

        # Stage 1: 针对性向量检索 (P0)
        relevant_operations = []
        try:
            vector_store = get_vector_store()
            if identified_ops:
                print("\n[Stage 1] 针对性向量检索...")
                relevant_operations = vector_store.search_by_service_operations(identified_ops)
                print(f"  ✓ 针对性检索找到 {len(relevant_operations)} 个相关操作")
            else:
                print("\n[Stage 1] 广泛向量检索 (fallback)...")
                relevant_operations = vector_store.search(query=user_requirement, n_results=25)

            if relevant_operations:
                for op in relevant_operations[:5]:
                    print(f"  - {op['service_name']}.{op['operation_name']} (相似度: {op.get('similarity', 0):.2f})")
                if len(relevant_operations) > 5:
                    print(f"  ... 及其他 {len(relevant_operations) - 5} 个操作")
            else:
                print("  ⚠ 向量搜索未找到相关操作")
        except Exception as e:
            print(f"  ⚠ 向量搜索失败: {e}")

        # P2: 筛选相关参数模板
        filtered_templates = self._filter_templates(identified_ops, relevant_operations)
        if filtered_templates:
            print(f"\n[P2] 匹配到 {len(filtered_templates)} 个参数模板")

        # Step 2: 使用LLM生成工作流 (P3: 两步生成)
        if self.is_llm_available():
            print("\n[Step 2] 调用LLM生成工作流...")
            workflow_dict = self.llm_client.generate_workflow(
                user_requirement, context,
                relevant_operations=relevant_operations if relevant_operations else None,
                parameter_templates=filtered_templates if filtered_templates else None,
                architecture_plan=architecture_plan
            )

            if workflow_dict:
                try:
                    workflow = self._parse_workflow_from_llm(workflow_dict)
                    print("\n✓ LLM成功生成工作流")
                except Exception as e:
                    print(f"\n✗ 解析LLM生成的工作流失败: {e}")
                    print("使用备用方案生成...")
                    workflow = self._generate_with_rules(user_requirement, context)
            else:
                print("\n✗ LLM生成失败，使用备用方案...")
                workflow = self._generate_with_rules(user_requirement, context)
        else:
            print("\n⚠ LLM不可用，使用规则引擎生成...")
            workflow = self._generate_with_rules(user_requirement, context)

        # 2. 验证工作流
        errors = workflow.validate()
        if errors:
            print(f"\n⚠ 工作流验证发现 {len(errors)} 个问题:")
            for error in errors:
                print(f"  - {error}")
        else:
            print("\n✓ 工作流验证通过")

        # 3. 注册表验证 + 自动修正 + LLM重试 (P1)
        registry_result = self._validate_against_registry(workflow, auto_correct=True)
        auto_corrected = registry_result.get("auto_corrected", [])
        needs_llm_fix = registry_result.get("needs_llm_fix", [])

        if auto_corrected:
            print(f"\n✓ 自动修正了 {len(auto_corrected)} 个问题:")
            for ac in auto_corrected:
                print(f"  - {ac}")

        if needs_llm_fix:
            print(f"\n⚠ 注册表验证发现 {len(needs_llm_fix)} 个需要修正的问题:")
            for fix in needs_llm_fix:
                print(f"  - {fix}")

            # P1: 验证重试循环
            if self.is_llm_available():
                print("\n[P1] 启动验证重试循环...")
                workflow = self._retry_with_validation_feedback(
                    workflow, needs_llm_fix,
                    relevant_operations=relevant_operations,
                    max_retries=2
                )
        else:
            print("\n✓ 注册表验证通过")

        # 4. 生成解释（如果LLM可用）
        if self.is_llm_available():
            explanation = self.explain(workflow)
            if explanation:
                print(f"\n工作流说明:\n{explanation[:300]}...")

        return workflow

    def _filter_templates(
        self,
        identified_ops: Optional[List[Dict]],
        relevant_operations: Optional[List[Dict]]
    ) -> Optional[Dict]:
        """
        根据识别到的操作和向量搜索结果，筛选相关的参数模板

        Args:
            identified_ops: Stage 0 识别到的操作列表
            relevant_operations: 向量搜索返回的操作列表

        Returns:
            匹配的参数模板字典，无匹配返回None
        """
        if not PARAMETER_TEMPLATES:
            return None

        operation_names = set()

        if identified_ops:
            for op in identified_ops:
                op_name = op.get("operation", "")
                if op_name:
                    operation_names.add(op_name.lower())

        if relevant_operations:
            for op in relevant_operations:
                op_name = op.get("operation_name", "")
                if op_name:
                    operation_names.add(op_name.lower())

        if not operation_names:
            return None

        filtered = {}
        for template_key, template_value in PARAMETER_TEMPLATES.items():
            if template_key.lower() in operation_names:
                filtered[template_key] = template_value

        return filtered if filtered else None

    def _parse_workflow_from_llm(self, workflow_dict: Dict[str, Any]) -> Workflow:
        """
        从LLM生成的字典解析工作流

        Args:
            workflow_dict: LLM生成的字典

        Returns:
            Workflow对象
        """
        # 创建工作流
        workflow = Workflow(
            id=workflow_dict.get('id', ''),
            name=workflow_dict.get('name', 'LLM生成的工作流'),
            description=workflow_dict.get('description', ''),
            version=workflow_dict.get('version', '1.0'),
            variables=workflow_dict.get('variables', {}),
            status=WorkflowStatus.READY
        )

        # 解析任务
        for task_data in workflow_dict.get('tasks', []):
            task = self._parse_task(task_data)
            workflow.add_task(task)

        return workflow

    def _parse_task(self, task_data: Dict[str, Any]) -> Task:
        """
        解析任务定义

        Args:
            task_data: 任务数据字典

        Returns:
            Task对象
        """
        # 解析任务类型
        task_type = task_data.get('type', 'huaweicloud_api')
        if isinstance(task_type, str):
            task_type = TaskType(task_type)

        task = Task(
            id=task_data.get('id', ''),
            name=task_data.get('name', ''),
            type=task_type,
            description=task_data.get('description', ''),
            service=task_data.get('service'),
            operation=task_data.get('operation'),
            parameters=task_data.get('parameters', {}),
            depends_on=task_data.get('depends_on', []),
            condition=task_data.get('condition'),
            retry_policy=task_data.get('retry_policy'),
            timeout=task_data.get('timeout')
        )

        return task

    def _validate_against_registry(self, workflow: Workflow, auto_correct: bool = True) -> Dict[str, List[str]]:
        """
        验证工作流中的service+operation是否在注册表中真实存在

        Args:
            workflow: 待验证的工作流
            auto_correct: 是否自动修正模糊匹配的候选项

        Returns:
            {"auto_corrected": [...], "needs_llm_fix": [...]}
        """
        auto_corrected = []
        needs_llm_fix = []
        all_services = self.service_registry.get_all_services()
        service_names_lower = {name.lower(): name for name in all_services}

        for task in workflow.tasks:
            if task.type != TaskType.HUAWEICLOUD_API:
                continue
            if not task.service:
                continue

            task_service_lower = task.service.lower()

            # 检查服务是否存在
            if task_service_lower not in service_names_lower:
                candidates = [
                    name for name_lower, name in service_names_lower.items()
                    if task_service_lower in name_lower or name_lower in task_service_lower
                ]
                if candidates and auto_correct:
                    old_service = task.service
                    task.service = candidates[0]
                    auto_corrected.append(
                        f"任务 '{task.name}': 服务 '{old_service}' → '{candidates[0]}'"
                    )
                elif candidates:
                    needs_llm_fix.append(
                        f"任务 '{task.name}': 服务 '{task.service}' 不存在，"
                        f"候选: {', '.join(candidates)}"
                    )
                else:
                    needs_llm_fix.append(
                        f"任务 '{task.name}': 服务 '{task.service}' 在注册表中不存在"
                    )
                    continue
                # 重新查找canonical name after auto-correct
                task_service_lower = task.service.lower()
                if task_service_lower not in service_names_lower:
                    continue

            # 自动修正大小写
            canonical_name = service_names_lower[task_service_lower]
            if task.service != canonical_name:
                task.service = canonical_name

            # 检查操作是否存在
            if not task.operation:
                continue

            service_info = all_services[canonical_name]
            operations = service_info.common_operations
            operations_lower = {op.lower(): op for op in operations}
            task_op_lower = task.operation.lower()

            if task_op_lower not in operations_lower:
                candidates = [
                    op for op_lower, op in operations_lower.items()
                    if task_op_lower in op_lower or op_lower in task_op_lower
                ]
                if candidates and auto_correct:
                    old_op = task.operation
                    task.operation = candidates[0]
                    auto_corrected.append(
                        f"任务 '{task.name}': 操作 '{old_op}' → '{candidates[0]}'"
                    )
                elif candidates:
                    needs_llm_fix.append(
                        f"任务 '{task.name}': 操作 '{task.operation}' "
                        f"不在服务 '{canonical_name}' 中，"
                        f"候选: {', '.join(candidates)}"
                    )
                else:
                    needs_llm_fix.append(
                        f"任务 '{task.name}': 操作 '{task.operation}' "
                        f"不在服务 '{canonical_name}' 的已知操作列表中"
                    )
            else:
                canonical_op = operations_lower[task_op_lower]
                if task.operation != canonical_op:
                    task.operation = canonical_op

        return {"auto_corrected": auto_corrected, "needs_llm_fix": needs_llm_fix}

    def _retry_with_validation_feedback(
        self,
        workflow: Workflow,
        needs_llm_fix: List[str],
        relevant_operations: Optional[List] = None,
        max_retries: int = 2
    ) -> Workflow:
        """
        将验证错误反馈给LLM进行修正，最多重试max_retries次

        Args:
            workflow: 当前工作流
            needs_llm_fix: 需要LLM修正的错误列表
            relevant_operations: 相关API操作
            max_retries: 最大重试次数

        Returns:
            修正后的工作流（尽力而为）
        """
        best_workflow = workflow
        remaining_errors = needs_llm_fix

        for attempt in range(max_retries):
            if not remaining_errors:
                break

            print(f"\n  修正尝试 {attempt + 1}/{max_retries}，待修正问题: {len(remaining_errors)}")

            corrected_dict = self.llm_client.correct_workflow(
                workflow_dict=best_workflow.to_dict(),
                validation_errors=remaining_errors,
                relevant_operations=relevant_operations
            )

            if not corrected_dict:
                print(f"  修正尝试 {attempt + 1} 失败：LLM未返回结果")
                break

            try:
                corrected_workflow = self._parse_workflow_from_llm(corrected_dict)
            except Exception as e:
                print(f"  修正尝试 {attempt + 1} 失败：解析错误 {e}")
                break

            # 重新验证
            result = self._validate_against_registry(corrected_workflow, auto_correct=True)
            remaining_errors = result.get("needs_llm_fix", [])
            best_workflow = corrected_workflow

            if result.get("auto_corrected"):
                for ac in result["auto_corrected"]:
                    print(f"    自动修正: {ac}")

            if not remaining_errors:
                print(f"  ✓ 修正尝试 {attempt + 1} 成功，所有问题已解决")
                break
            else:
                print(f"  仍有 {len(remaining_errors)} 个问题未解决")

        return best_workflow

    def _generate_with_rules(self, requirement: str, context: Optional[Dict[str, Any]]) -> Workflow:
        """
        使用规则引擎生成工作流（备用方案）

        Args:
            requirement: 用户需求
            context: 上下文

        Returns:
            Workflow对象
        """
        print("  \n使用规则引擎生成...")

        # 简单的模式匹配
        requirement_lower = requirement.lower()

        # 高可用/负载均衡场景优先匹配（含完整网络+安全+ELB+EIP）
        if any(word in requirement_lower for word in ['高可用', '负载均衡', 'elb', 'load balanc', 'ha ']):
            return self._create_ha_web_workflow(requirement)

        if 'web' in requirement_lower or '网站' in requirement_lower or '应用' in requirement_lower:
            return self._create_web_application_workflow(requirement)

        if any(word in requirement_lower for word in ['容器', 'cce', 'kubernetes', 'k8s']):
            return self._create_cce_workflow(requirement)

        if any(word in requirement_lower for word in ['存储', 'obs', '桶', 'bucket']):
            return self._create_obs_workflow(requirement)

        if any(word in requirement_lower for word in ['安全', 'waf', '防火墙', '防护']):
            return self._create_security_workflow(requirement)

        if any(word in requirement_lower for word in ['监控', '告警', 'ces']):
            return self._create_monitoring_workflow(requirement)

        if any(word in requirement_lower for word in ['gaussdb', '高斯']):
            return self._create_gaussdb_workflow(requirement)

        if 'ecs' in requirement_lower or '服务器' in requirement_lower:
            return self._create_ecs_workflow(requirement)

        if 'vpc' in requirement_lower or '网络' in requirement_lower:
            return self._create_vpc_workflow(requirement)

        if any(word in requirement_lower for word in ['rds', '数据库', 'mysql', 'postgresql']):
            return self._create_rds_workflow(requirement)

        # 默认空工作流
        return self._create_default_workflow()

    def _create_web_application_workflow(self, requirement: str) -> Workflow:
        """创建Web应用部署工作流"""
        config = self._parse_configuration(requirement)

        workflow = Workflow(
            name="部署Web应用",
            description="完整的Web应用部署，包括VPC、ECS和RDS",
            variables={
                "vpc_name": config.get("vpc_name", "web-app-vpc"),
                "vpc_cidr": config.get("vpc_cidr", "192.168.0.0/16"),
                "subnet_name": config.get("subnet_name", "web-app-subnet"),
                "subnet_cidr": config.get("subnet_cidr", "192.168.1.0/24"),
                "ecs_name": config.get("ecs_name", "web-server"),
                "ecs_flavor": config.get("flavor", "s6.large.2"),
                "image_id": config.get("image", "CentOS 7.9"),
            },
            status=WorkflowStatus.READY
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
            },
            retry_policy={"max_attempts": 3}
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
            },
            retry_policy={"max_attempts": 3}
        ))

        # 创建安全组
        workflow.add_task(Task(
            name="create_security_group",
            type=TaskType.HUAWEICLOUD_API,
            description="创建安全组",
            service="vpc",
            operation="create_security_group",
            depends_on=["create_vpc"],
            parameters={
                "name": "web-app-sg",
                "vpc_id": "{{ outputs.create_vpc.vpc.id }}"
            },
            retry_policy={"max_attempts": 3}
        ))

        # 创建ECS
        workflow.add_task(Task(
            name="create_ecs",
            type=TaskType.HUAWEICLOUD_API,
            description="创建Web服务器ECS实例",
            service="ecs",
            operation="create_servers",
            depends_on=["create_subnet", "create_security_group"],
            parameters={
                "server": {
                    "name": "{{ variables.ecs_name }}",
                    "flavorRef": "{{ variables.ecs_flavor }}",
                    "imageRef": "{{ variables.image_id }}",
                    "vpcid": "{{ outputs.create_vpc.vpc.id }}",
                    "nics": [{
                        "subnet_id": "{{ outputs.create_subnet.subnet.id }}",
                    }]
                }
            },
            timeout=600,
            retry_policy={"max_attempts": 2}
        ))

        return workflow

    def _create_ecs_workflow(self, requirement: str) -> Workflow:
        """创建ECS实例工作流"""
        config = self._parse_configuration(requirement)

        workflow = Workflow(
            name="创建ECS实例",
            variables={
                "ecs_name": config.get("name", "my-server"),
                "ecs_flavor": config.get("flavor", "s6.large.2"),
                "vpc_id": config.get("vpc_id", "default-vpc"),
                "subnet_id": config.get("subnet_id", "default-subnet"),
                "image_id": config.get("image", "CentOS 7.9"),
            },
            status=WorkflowStatus.READY
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

        return workflow

    def _create_vpc_workflow(self, requirement: str) -> Workflow:
        """创建VPC网络工作流"""
        config = self._parse_configuration(requirement)

        workflow = Workflow(
            name="创建VPC网络",
            variables={
                "vpc_name": config.get("name", "my-vpc"),
                "vpc_cidr": config.get("cidr", "192.168.0.0/16"),
                "subnet_name": config.get("subnet", "my-subnet"),
                "subnet_cidr": config.get("subnet_cidr", "192.168.1.0/24")
            },
            status=WorkflowStatus.READY
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

        return workflow

    def _create_rds_workflow(self, requirement: str) -> Workflow:
        """创建数据库工作流"""
        db_type = "MySQL"
        if "postgresql" in requirement.lower():
            db_type = "PostgreSQL"
        elif "sqlserver" in requirement.lower():
            db_type = "SQLServer"

        config = self._parse_configuration(requirement)

        workflow = Workflow(
            name=f"创建{db_type}数据库实例",
            variables={
                "db_name": config.get("name", "my-database"),
                "db_type": db_type,
                "vpc_id": config.get("vpc_id", "default-vpc"),
                "subnet_id": config.get("subnet_id", "default-subnet")
            },
            status=WorkflowStatus.READY
        )

        workflow.add_task(Task(
            name="create_db_instance",
            type=TaskType.HUAWEICLOUD_API,
            service="rds",
            operation="create_instance",
            parameters={
                "name": "{{ variables.db_name }}",
                "datastore": {"type": "{{ variables.db_type }}", "version": "8.0"},
                "vpc_id": "{{ variables.vpc_id }}",
                "subnet_id": "{{ variables.subnet_id }}",
                "flavor_ref": "rds.mysql.s1.large",
                "volume": {"type": "COMMON", "size": 100}
            }
        ))

        return workflow

    def _create_ha_web_workflow(self, requirement: str) -> Workflow:
        """创建高可用Web应用工作流（VPC+子网+安全组+安全组规则+ECS×2+ELB+Listener+Pool+EIP+RDS）"""
        config = self._parse_configuration(requirement)

        workflow = Workflow(
            name="高可用Web应用部署",
            description="完整的高可用Web应用架构：VPC网络、安全组、双ECS实例、弹性负载均衡、弹性公网IP、RDS数据库",
            variables={
                "vpc_name": config.get("vpc_name", "ha-web-vpc"),
                "vpc_cidr": config.get("vpc_cidr", "192.168.0.0/16"),
                "subnet_name": config.get("subnet_name", "ha-web-subnet"),
                "subnet_cidr": config.get("subnet_cidr", "192.168.1.0/24"),
                "ecs_flavor": config.get("flavor", "s6.large.2"),
                "image_id": config.get("image", "CentOS 7.9"),
                "db_name": config.get("db_name", "ha-web-db"),
            },
            status=WorkflowStatus.READY
        )

        # 1. 创建VPC
        workflow.add_task(Task(
            name="create_vpc",
            type=TaskType.HUAWEICLOUD_API,
            description="创建虚拟私有云",
            service="vpc",
            operation="create_vpc",
            parameters={
                "name": "{{ variables.vpc_name }}",
                "cidr": "{{ variables.vpc_cidr }}"
            },
            retry_policy={"max_attempts": 3}
        ))

        # 2. 创建子网
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
            },
            retry_policy={"max_attempts": 3}
        ))

        # 3. 创建安全组
        workflow.add_task(Task(
            name="create_security_group",
            type=TaskType.HUAWEICLOUD_API,
            description="创建安全组",
            service="vpc",
            operation="create_security_group",
            depends_on=["create_vpc"],
            parameters={
                "name": "ha-web-sg",
                "vpc_id": "{{ outputs.create_vpc.vpc.id }}"
            },
            retry_policy={"max_attempts": 3}
        ))

        # 4. 安全组规则 - 放通HTTP 80
        workflow.add_task(Task(
            name="create_sg_rule_http",
            type=TaskType.HUAWEICLOUD_API,
            description="安全组规则-放通HTTP 80端口",
            service="vpc",
            operation="create_security_group_rule",
            depends_on=["create_security_group"],
            parameters={
                "security_group_id": "{{ outputs.create_security_group.security_group.id }}",
                "direction": "ingress",
                "ethertype": "IPv4",
                "protocol": "tcp",
                "port_range_min": 80,
                "port_range_max": 80,
                "remote_ip_prefix": "0.0.0.0/0"
            }
        ))

        # 5. 安全组规则 - 放通HTTPS 443
        workflow.add_task(Task(
            name="create_sg_rule_https",
            type=TaskType.HUAWEICLOUD_API,
            description="安全组规则-放通HTTPS 443端口",
            service="vpc",
            operation="create_security_group_rule",
            depends_on=["create_security_group"],
            parameters={
                "security_group_id": "{{ outputs.create_security_group.security_group.id }}",
                "direction": "ingress",
                "ethertype": "IPv4",
                "protocol": "tcp",
                "port_range_min": 443,
                "port_range_max": 443,
                "remote_ip_prefix": "0.0.0.0/0"
            }
        ))

        # 6. 创建ECS实例1
        workflow.add_task(Task(
            name="create_ecs_1",
            type=TaskType.HUAWEICLOUD_API,
            description="创建Web服务器1",
            service="ecs",
            operation="create_servers",
            depends_on=["create_subnet", "create_security_group"],
            parameters={
                "server": {
                    "name": "ha-web-server-1",
                    "flavorRef": "{{ variables.ecs_flavor }}",
                    "imageRef": "{{ variables.image_id }}",
                    "vpcid": "{{ outputs.create_vpc.vpc.id }}",
                    "nics": [{"subnet_id": "{{ outputs.create_subnet.subnet.id }}"}],
                    "security_groups": [{"id": "{{ outputs.create_security_group.security_group.id }}"}]
                }
            },
            timeout=600,
            retry_policy={"max_attempts": 2}
        ))

        # 7. 创建ECS实例2
        workflow.add_task(Task(
            name="create_ecs_2",
            type=TaskType.HUAWEICLOUD_API,
            description="创建Web服务器2",
            service="ecs",
            operation="create_servers",
            depends_on=["create_subnet", "create_security_group"],
            parameters={
                "server": {
                    "name": "ha-web-server-2",
                    "flavorRef": "{{ variables.ecs_flavor }}",
                    "imageRef": "{{ variables.image_id }}",
                    "vpcid": "{{ outputs.create_vpc.vpc.id }}",
                    "nics": [{"subnet_id": "{{ outputs.create_subnet.subnet.id }}"}],
                    "security_groups": [{"id": "{{ outputs.create_security_group.security_group.id }}"}]
                }
            },
            timeout=600,
            retry_policy={"max_attempts": 2}
        ))

        # 8. 创建弹性负载均衡
        workflow.add_task(Task(
            name="create_elb",
            type=TaskType.HUAWEICLOUD_API,
            description="创建弹性负载均衡器",
            service="elb",
            operation="create_loadbalancer",
            depends_on=["create_subnet"],
            parameters={
                "name": "ha-web-elb",
                "vip_subnet_cidr_id": "{{ outputs.create_subnet.subnet.id }}",
                "vpc_id": "{{ outputs.create_vpc.vpc.id }}"
            },
            retry_policy={"max_attempts": 3}
        ))

        # 9. 创建ELB监听器
        workflow.add_task(Task(
            name="create_listener",
            type=TaskType.HUAWEICLOUD_API,
            description="创建ELB监听器(HTTP:80)",
            service="elb",
            operation="create_listener",
            depends_on=["create_elb"],
            parameters={
                "name": "ha-web-listener",
                "protocol": "HTTP",
                "protocol_port": 80,
                "loadbalancer_id": "{{ outputs.create_elb.loadbalancer.id }}"
            },
            retry_policy={"max_attempts": 3}
        ))

        # 10. 创建ELB后端服务器组
        workflow.add_task(Task(
            name="create_pool",
            type=TaskType.HUAWEICLOUD_API,
            description="创建后端服务器组",
            service="elb",
            operation="create_pool",
            depends_on=["create_listener"],
            parameters={
                "name": "ha-web-pool",
                "protocol": "HTTP",
                "lb_algorithm": "ROUND_ROBIN",
                "listener_id": "{{ outputs.create_listener.listener.id }}",
                "loadbalancer_id": "{{ outputs.create_elb.loadbalancer.id }}"
            },
            retry_policy={"max_attempts": 3}
        ))

        # 11. 添加后端服务器1到Pool
        workflow.add_task(Task(
            name="add_member_1",
            type=TaskType.HUAWEICLOUD_API,
            description="添加Web服务器1到后端服务器组",
            service="elb",
            operation="create_member",
            depends_on=["create_pool", "create_ecs_1"],
            parameters={
                "pool_id": "{{ outputs.create_pool.pool.id }}",
                "address": "{{ outputs.create_ecs_1.server.addresses }}",
                "protocol_port": 80,
                "subnet_cidr_id": "{{ outputs.create_subnet.subnet.id }}"
            }
        ))

        # 12. 添加后端服务器2到Pool
        workflow.add_task(Task(
            name="add_member_2",
            type=TaskType.HUAWEICLOUD_API,
            description="添加Web服务器2到后端服务器组",
            service="elb",
            operation="create_member",
            depends_on=["create_pool", "create_ecs_2"],
            parameters={
                "pool_id": "{{ outputs.create_pool.pool.id }}",
                "address": "{{ outputs.create_ecs_2.server.addresses }}",
                "protocol_port": 80,
                "subnet_cidr_id": "{{ outputs.create_subnet.subnet.id }}"
            }
        ))

        # 13. 创建弹性公网IP并绑定ELB
        workflow.add_task(Task(
            name="create_eip",
            type=TaskType.HUAWEICLOUD_API,
            description="创建弹性公网IP并绑定到ELB",
            service="eip",
            operation="create_publicip",
            depends_on=["create_elb"],
            parameters={
                "publicip": {
                    "type": "5_bgp"
                },
                "bandwidth": {
                    "name": "ha-web-bandwidth",
                    "size": 10,
                    "share_type": "PER",
                    "charge_mode": "traffic"
                },
                "port_id": "{{ outputs.create_elb.loadbalancer.vip_port_id }}"
            },
            retry_policy={"max_attempts": 3}
        ))

        # 14. 创建RDS数据库
        workflow.add_task(Task(
            name="create_rds",
            type=TaskType.HUAWEICLOUD_API,
            description="创建RDS MySQL数据库实例",
            service="rds",
            operation="create_instance",
            depends_on=["create_subnet", "create_security_group"],
            parameters={
                "name": "{{ variables.db_name }}",
                "datastore": {"type": "MySQL", "version": "8.0"},
                "flavor_ref": "rds.mysql.s1.large",
                "volume": {"type": "COMMON", "size": 100},
                "vpc_id": "{{ outputs.create_vpc.vpc.id }}",
                "subnet_id": "{{ outputs.create_subnet.subnet.id }}",
                "security_group_id": "{{ outputs.create_security_group.security_group.id }}"
            },
            timeout=900,
            retry_policy={"max_attempts": 2}
        ))

        return workflow

    def _create_elb_ecs_workflow(self, requirement: str) -> Workflow:
        """创建负载均衡Web应用工作流（VPC + ECS×2 + ELB）"""
        config = self._parse_configuration(requirement)

        workflow = Workflow(
            name="负载均衡Web应用部署",
            description="创建VPC网络、两台ECS实例和弹性负载均衡器",
            variables={
                "vpc_name": config.get("vpc_name", "elb-vpc"),
                "vpc_cidr": config.get("vpc_cidr", "192.168.0.0/16"),
                "subnet_name": config.get("subnet_name", "elb-subnet"),
                "subnet_cidr": config.get("subnet_cidr", "192.168.1.0/24"),
                "ecs_flavor": config.get("flavor", "s6.large.2"),
                "image_id": config.get("image", "CentOS 7.9"),
            },
            status=WorkflowStatus.READY
        )

        workflow.add_task(Task(
            name="create_vpc",
            type=TaskType.HUAWEICLOUD_API,
            description="创建VPC网络",
            service="vpc",
            operation="create_vpc",
            parameters={
                "name": "{{ variables.vpc_name }}",
                "cidr": "{{ variables.vpc_cidr }}"
            },
            retry_policy={"max_attempts": 3}
        ))

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
            },
            retry_policy={"max_attempts": 3}
        ))

        workflow.add_task(Task(
            name="create_ecs_1",
            type=TaskType.HUAWEICLOUD_API,
            description="创建Web服务器1",
            service="ecs",
            operation="create_servers",
            depends_on=["create_subnet"],
            parameters={
                "server": {
                    "name": "web-server-1",
                    "flavorRef": "{{ variables.ecs_flavor }}",
                    "imageRef": "{{ variables.image_id }}",
                    "vpcid": "{{ outputs.create_vpc.vpc.id }}",
                    "nics": [{"subnet_id": "{{ outputs.create_subnet.subnet.id }}"}]
                }
            },
            timeout=600,
            retry_policy={"max_attempts": 2}
        ))

        workflow.add_task(Task(
            name="create_ecs_2",
            type=TaskType.HUAWEICLOUD_API,
            description="创建Web服务器2",
            service="ecs",
            operation="create_servers",
            depends_on=["create_subnet"],
            parameters={
                "server": {
                    "name": "web-server-2",
                    "flavorRef": "{{ variables.ecs_flavor }}",
                    "imageRef": "{{ variables.image_id }}",
                    "vpcid": "{{ outputs.create_vpc.vpc.id }}",
                    "nics": [{"subnet_id": "{{ outputs.create_subnet.subnet.id }}"}]
                }
            },
            timeout=600,
            retry_policy={"max_attempts": 2}
        ))

        workflow.add_task(Task(
            name="create_elb",
            type=TaskType.HUAWEICLOUD_API,
            description="创建弹性负载均衡器",
            service="elb",
            operation="create_loadbalancer",
            depends_on=["create_subnet"],
            parameters={
                "name": "web-elb",
                "vip_subnet_cidr_id": "{{ outputs.create_subnet.subnet.id }}",
                "vpc_id": "{{ outputs.create_vpc.vpc.id }}"
            },
            retry_policy={"max_attempts": 3}
        ))

        return workflow

    def _create_cce_workflow(self, requirement: str) -> Workflow:
        """创建CCE容器集群部署工作流（VPC + CCE）"""
        config = self._parse_configuration(requirement)

        workflow = Workflow(
            name="CCE容器集群部署",
            description="创建VPC网络和CCE容器集群",
            variables={
                "vpc_name": config.get("vpc_name", "cce-vpc"),
                "vpc_cidr": config.get("vpc_cidr", "192.168.0.0/16"),
                "subnet_name": config.get("subnet_name", "cce-subnet"),
                "subnet_cidr": config.get("subnet_cidr", "192.168.1.0/24"),
                "cluster_name": config.get("name", "my-cce-cluster"),
            },
            status=WorkflowStatus.READY
        )

        workflow.add_task(Task(
            name="create_vpc",
            type=TaskType.HUAWEICLOUD_API,
            description="创建VPC网络",
            service="vpc",
            operation="create_vpc",
            parameters={
                "name": "{{ variables.vpc_name }}",
                "cidr": "{{ variables.vpc_cidr }}"
            },
            retry_policy={"max_attempts": 3}
        ))

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
            },
            retry_policy={"max_attempts": 3}
        ))

        workflow.add_task(Task(
            name="create_cce_cluster",
            type=TaskType.HUAWEICLOUD_API,
            description="创建CCE容器集群",
            service="cce",
            operation="create_cluster",
            depends_on=["create_subnet"],
            parameters={
                "kind": "Cluster",
                "metadata": {"name": "{{ variables.cluster_name }}"},
                "spec": {
                    "flavor": "cce.s2.small",
                    "hostNetwork": {
                        "vpc": "{{ outputs.create_vpc.vpc.id }}",
                        "subnet": "{{ outputs.create_subnet.subnet.id }}"
                    },
                    "containerNetwork": {
                        "mode": "overlay_l2"
                    }
                }
            },
            timeout=900,
            retry_policy={"max_attempts": 2}
        ))

        return workflow

    def _create_obs_workflow(self, requirement: str) -> Workflow:
        """创建OBS对象存储工作流"""
        config = self._parse_configuration(requirement)

        workflow = Workflow(
            name="创建OBS对象存储桶",
            description="创建OBS存储桶",
            variables={
                "bucket_name": config.get("name", "my-obs-bucket"),
            },
            status=WorkflowStatus.READY
        )

        workflow.add_task(Task(
            name="create_obs_bucket",
            type=TaskType.HUAWEICLOUD_API,
            description="创建OBS存储桶",
            service="obs",
            operation="create_bucket",
            parameters={
                "bucket_name": "{{ variables.bucket_name }}",
                "storage_class": "STANDARD",
                "acl": "private"
            },
            retry_policy={"max_attempts": 3}
        ))

        return workflow

    def _create_security_workflow(self, requirement: str) -> Workflow:
        """创建安全防护工作流（WAF）"""
        config = self._parse_configuration(requirement)

        workflow = Workflow(
            name="Web应用安全防护",
            description="创建WAF Web应用防火墙策略",
            variables={
                "policy_name": config.get("name", "my-waf-policy"),
                "domain": config.get("domain", "example.com"),
            },
            status=WorkflowStatus.READY
        )

        workflow.add_task(Task(
            name="create_waf_policy",
            type=TaskType.HUAWEICLOUD_API,
            description="创建WAF防护策略",
            service="waf",
            operation="create_policy",
            parameters={
                "name": "{{ variables.policy_name }}"
            },
            retry_policy={"max_attempts": 3}
        ))

        workflow.add_task(Task(
            name="create_waf_domain",
            type=TaskType.HUAWEICLOUD_API,
            description="添加WAF防护域名",
            service="waf",
            operation="create_host",
            depends_on=["create_waf_policy"],
            parameters={
                "hostname": "{{ variables.domain }}",
                "policy_id": "{{ outputs.create_waf_policy.id }}"
            },
            retry_policy={"max_attempts": 3}
        ))

        return workflow

    def _create_monitoring_workflow(self, requirement: str) -> Workflow:
        """创建云监控告警工作流（CES）"""
        config = self._parse_configuration(requirement)

        workflow = Workflow(
            name="云监控告警配置",
            description="创建CES云监控告警规则",
            variables={
                "alarm_name": config.get("name", "my-alarm"),
            },
            status=WorkflowStatus.READY
        )

        workflow.add_task(Task(
            name="create_alarm_rule",
            type=TaskType.HUAWEICLOUD_API,
            description="创建告警规则",
            service="ces",
            operation="create_alarm",
            parameters={
                "alarm_name": "{{ variables.alarm_name }}",
                "metric": {
                    "namespace": "SYS.ECS",
                    "metric_name": "cpu_util",
                    "dimensions": [{"name": "instance_id", "value": "*"}]
                },
                "condition": {
                    "comparison_operator": ">=",
                    "value": 80,
                    "period": 300,
                    "count": 3
                },
                "alarm_enabled": True
            },
            retry_policy={"max_attempts": 3}
        ))

        return workflow

    def _create_gaussdb_workflow(self, requirement: str) -> Workflow:
        """创建GaussDB数据库工作流"""
        config = self._parse_configuration(requirement)

        workflow = Workflow(
            name="创建GaussDB数据库实例",
            description="创建华为云GaussDB数据库实例",
            variables={
                "db_name": config.get("name", "my-gaussdb"),
                "vpc_id": config.get("vpc_id", "default-vpc"),
                "subnet_id": config.get("subnet_id", "default-subnet"),
            },
            status=WorkflowStatus.READY
        )

        workflow.add_task(Task(
            name="create_gaussdb_instance",
            type=TaskType.HUAWEICLOUD_API,
            description="创建GaussDB数据库实例",
            service="gaussdb",
            operation="create_instance",
            parameters={
                "name": "{{ variables.db_name }}",
                "datastore": {"type": "GaussDB(for MySQL)", "version": "8.0"},
                "flavor_ref": "gaussdb.mysql.xlarge.4",
                "vpc_id": "{{ variables.vpc_id }}",
                "subnet_id": "{{ variables.subnet_id }}",
                "volume": {"type": "COMMON", "size": 100}
            },
            timeout=600,
            retry_policy={"max_attempts": 2}
        ))

        return workflow

    def _create_default_workflow(self) -> Workflow:
        """创建默认空工作流"""
        return Workflow(
            name="新建工作流",
            description="",
            tasks=[]
        )

    def _parse_configuration(self, requirement: str) -> Dict[str, Any]:
        """从需求文本中提取配置参数"""
        import re
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

    def explain(self, workflow: Workflow) -> Optional[str]:
        """
        解释工作流

        Args:
            workflow: 工作流对象

        Returns:
            解释文本
        """
        if not self.is_llm_available():
            return self._manual_explain(workflow)

        workflow_dict = workflow.to_dict()
        return self.llm_client.explain_workflow(workflow_dict)

    def _manual_explain(self, workflow: Workflow) -> str:
        """手动生成工作流解释"""
        lines = []
        lines.append(f"工作流: {workflow.name}")
        lines.append(f"描述: {workflow.description}\n")

        lines.append("任务列表:")
        for i, task in enumerate(workflow.tasks, 1):
            lines.append(f"\n{i}. {task.name}")
            lines.append(f"   服务: {task.service}")
            lines.append(f"   操作: {task.operation}")
            if task.depends_on:
                lines.append(f"   依赖: {', '.join(task.depends_on)}")

        return '\n'.join(lines)

    def improve(self, workflow: Workflow, feedback: str) -> Workflow:
        """
        根据反馈改进工作流

        Args:
            workflow: 当前工作流
            feedback: 用户反馈

        Returns:
            改进后的工作流
        """
        if not self.is_llm_available():
            print("LLM不可用，无法智能改进工作流")
            return workflow

        workflow_dict = workflow.to_dict()
        improved_dict = self.llm_client.improve_workflow(workflow_dict, feedback)

        if improved_dict:
            try:
                return self._parse_workflow_from_llm(improved_dict)
            except Exception as e:
                print(f"解析改进的工作流失败: {e}")
                return workflow
        else:
            return workflow

    def describe_workflow(self, workflow: Workflow, detailed: bool = False) -> str:
        """描述工作流内容"""
        lines = []
        lines.append(f"工作流: {workflow.name}")
        lines.append(f"描述: {workflow.description}")
        lines.append(f"任务数: {len(workflow.tasks)}")
        lines.append(f"状态: {workflow.status.value}\n")

        if detailed:
            lines.append("任务详细:")
            for i, task in enumerate(workflow.tasks, 1):
                lines.append(f"\n{i}. {task.name} [{task.service}.{task.operation}]")
                lines.append(f"   描述: {task.description}")
                if task.depends_on:
                    lines.append(f"   依赖: {', '.join(task.depends_on)}")
                if task.parameters:
                    lines.append(f"   参数: {json.dumps(task.parameters, indent=6)}")

        return '\n'.join(lines)
