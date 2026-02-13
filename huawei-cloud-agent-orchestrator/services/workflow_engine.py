"""
Workflow执行引擎
负责执行工作流定义，管理任务的生命周期
"""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor

from models.workflow import Workflow, Task, TaskStatus, WorkflowStatus
from services.task_executor import TaskExecutor
from utils.logger import setup_logger


@dataclass
class ExecutionContext:
    """执行上下文"""
    workflow_id: str
    variables: Dict[str, Any]
    outputs: Dict[str, Dict[str, Any]]
    task_outputs: Dict[str, Any]  # 任务输出缓存


class WorkflowEngine:
    """工作流执行引擎

    职责:
    1. 执行工作流定义
    2. 管理任务调度
    3. 处理任务依赖
    4. 维护执行状态
    5. 处理错误和重试
    """

    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.logger = setup_logger()
        self.task_executor = TaskExecutor()

        # 执行状态存储
        self.executions: Dict[str, Workflow] = {}
        self.execution_logs: Dict[str, List[Dict]] = {}

    async def execute(self, workflow: Workflow, dry_run: bool = False) -> Dict[str, Any]:
        """
        执行工作流

        Args:
            workflow: 要执行的工作流
            dry_run: 是否仅验证不执行

        Returns:
            执行结果
        """
        execution_id = str(uuid.uuid4())
        self.logger.info(f"开始执行工作流: {workflow.name} (ID: {execution_id})")

        # 初始化执行上下文
        context = ExecutionContext(
            workflow_id=execution_id,
            variables=workflow.variables.copy(),
            outputs={},
            task_outputs={}
        )

        # 验证工作流
        errors = workflow.validate()
        if errors:
            return {
                "execution_id": execution_id,
                "status": "failed",
                "errors": errors
            }

        if dry_run:
            self.logger.info(f"工作流 {workflow.name} 验证通过")
            return {
                "execution_id": execution_id,
                "status": "validated",
                "message": "工作流验证通过"
            }

        # 更新工作流状态
        workflow.status = WorkflowStatus.RUNNING
        workflow.start_time = datetime.now()
        self.executions[execution_id] = workflow
        self.execution_logs[execution_id] = []

        # 按依赖关系排序任务
        sorted_tasks = self._sort_tasks_by_dependency(workflow.tasks)

        # 执行所有任务
        try:
            for task in sorted_tasks:
                await self._execute_task(task, context, execution_id)

                # 检查是否需要停止执行
                if task.status == TaskStatus.FAILED:
                    if not self._should_continue_on_failure(workflow, task):
                        break

            # 更新最终状态
            workflow.status = self._determine_final_status(workflow)
            workflow.end_time = datetime.now()

            # 生成执行报告
            report = self._generate_execution_report(workflow, execution_id)

            self.logger.info(f"工作流 {workflow.name} 执行完成: {workflow.status.value}")

            return report

        except Exception as e:
            self.logger.error(f"工作流执行异常: {str(e)}")
            workflow.status = WorkflowStatus.FAILED
            workflow.end_time = datetime.now()

            return {
                "execution_id": execution_id,
                "status": "failed",
                "error": str(e),
                "message": "工作流执行发生异常"
            }

    async def _execute_task(self, task: Task, context: ExecutionContext, execution_id: str):
        """执行单个任务"""
        self.logger.info(f"执行任务: {task.name} ({task.service}.{task.operation})")

        # 更新任务状态
        task.status = TaskStatus.RUNNING
        task.start_time = datetime.now()
        task.attempts += 1

        # 记录任务开始
        self._log_execution(execution_id, "task_started", {
            "task_id": task.id,
            "task_name": task.name,
            "service": task.service,
            "operation": task.operation
        })

        try:
            # 准备任务参数（替换变量引用）
            parameters = self._prepare_parameters(task.parameters, context)

            # 执行任务
            result = await self.task_executor.execute(
                service=task.service,
                operation=task.operation,
                parameters=parameters,
                timeout=task.timeout
            )

            # 处理执行结果
            task.output = result
            task.status = TaskStatus.SUCCESS

            # 保存任务输出到上下文
            if task.name:
                context.task_outputs[task.name] = result
                context.outputs[task.name] = result

            # 记录任务完成
            self._log_execution(execution_id, "task_completed", {
                "task_id": task.id,
                "task_name": task.name,
                "status": "success",
                "output_size": len(str(result))
            })

            self.logger.info(f"任务 {task.name} 执行成功")

        except Exception as e:
            self.logger.error(f"任务 {task.name} 执行失败: {str(e)}")

            task.status = TaskStatus.FAILED
            task.error = str(e)

            # 记录失败
            self._log_execution(execution_id, "task_failed", {
                "task_id": task.id,
                "task_name": task.name,
                "error": str(e)
            })

            # 重试逻辑
            if self._should_retry(task):
                await self._retry_task(task, context, execution_id)

        finally:
            task.end_time = datetime.now()

    def _prepare_parameters(self, parameters: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """
        准备任务参数，替换变量引用

        支持:
        - {{ variables.xxx }} - 引用变量
        - {{ outputs.task_name.xxx }} - 引用任务输出
        """
        import json

        # 将参数转换为JSON字符串进行处理
        param_json = json.dumps(parameters)

        # 替换变量引用
        import re

        # 替换 {{ variables.xxx }}
        def replace_variables(match):
            var_path = match.group(1)
            parts = var_path.split('.')
            if parts[0] == 'variables' and len(parts) > 1:
                return str(context.variables.get(parts[1], match.group(0)))
            return match.group(0)

        param_json = re.sub(r'{{\s*variables\.([\w\.]+)\s*}}', replace_variables, param_json)

        # 替换 {{ outputs.task_name.xxx }}
        def replace_outputs(match):
            output_path = match.group(1)
            parts = output_path.split('.')
            if parts[0] == 'outputs' and len(parts) >= 3:
                task_name = parts[1]
                output_key = parts[2]
                task_output = context.outputs.get(task_name, {})
                if isinstance(task_output, dict):
                    return str(task_output.get(output_key, match.group(0)))
            return match.group(0)

        param_json = re.sub(r'{{\s*outputs\.([\w\.]+)\s*}}', replace_outputs, param_json)

        # 解析回字典
        return json.loads(param_json)

    def _should_retry(self, task: Task) -> bool:
        """判断是否应该重试任务"""
        if not task.retry_policy:
            return False

        max_attempts = task.retry_policy.get('max_attempts', 1)
        return task.attempts < max_attempts

    async def _retry_task(self, task: Task, context: ExecutionContext, execution_id: str):
        """重试任务"""
        retry_delay = 2  ** task.attempts  # 指数退避

        self.logger.info(f"任务 {task.name} 将在 {retry_delay} 秒后重试 (第 {task.attempts} 次)")

        self._log_execution(execution_id, "task_retry", {
            "task_id": task.id,
            "task_name": task.name,
            "attempt": task.attempts,
            "delay": retry_delay
        })

        await asyncio.sleep(retry_delay)
        await self._execute_task(task, context, execution_id)

    def _should_continue_on_failure(self, workflow: Workflow, failed_task: Task) -> bool:
        """判断任务失败后是否继续执行"""
        # TODO: 根据工作流配置判断
        return False

    def _determine_final_status(self, workflow: Workflow) -> WorkflowStatus:
        """确定工作流的最终状态"""
        all_success = True
        has_failure = False
        has_running = False

        for task in workflow.tasks:
            if task.status == TaskStatus.FAILED:
                has_failure = True
            elif task.status == TaskStatus.RUNNING:
                has_running = True
            elif task.status != TaskStatus.SUCCESS:
                all_success = False

        if has_running:
            return WorkflowStatus.RUNNING
        elif not has_failure and all_success:
            return WorkflowStatus.SUCCESS
        elif has_failure and any(task.status == TaskStatus.SUCCESS for task in workflow.tasks):
            return WorkflowStatus.PARTIAL_SUCCESS
        else:
            return WorkflowStatus.FAILED

    def _sort_tasks_by_dependency(self, tasks: List[Task]) -> List[Task]:
        """按依赖关系对任务排序"""
        # 构建依赖图
        task_map = {task.name: task for task in tasks if task.name}

        # 没有依赖的任务
        independent = [task for task in tasks if not task.depends_on]
        dependent = [task for task in tasks if task.depends_on]

        # 简单的拓扑排序
        sorted_tasks = independent.copy()
        added = {task.name for task in independent if task.name}

        while dependent and len(sorted_tasks) < len(tasks):
            added_in_iteration = False
            for task in dependent[:]:
                # 检查所有依赖是否已添加
                if all(dep in added for dep in task.depends_on):
                    sorted_tasks.append(task)
                    if task.name:
                        added.add(task.name)
                    dependent.remove(task)
                    added_in_iteration = True

            if not added_in_iteration:
                # 存在循环依赖
                break

        # 添加剩余任务（循环依赖的任务）
        sorted_tasks.extend(dependent)

        return sorted_tasks

    def _generate_execution_report(self, workflow: Workflow, execution_id: str) -> Dict[str, Any]:
        """生成执行报告"""
        task_stats = {
            "total": len(workflow.tasks),
            "success": sum(1 for t in workflow.tasks if t.status == TaskStatus.SUCCESS),
            "failed": sum(1 for t in workflow.tasks if t.status == TaskStatus.FAILED),
            "skipped": sum(1 for t in workflow.tasks if t.status == TaskStatus.SKIPPED)
        }

        # 汇总输出
        outputs = {}
        for task in workflow.tasks:
            if task.output and task.name:
                outputs[task.name] = task.output

        return {
            "execution_id": execution_id,
            "workflow_id": workflow.id,
            "workflow_name": workflow.name,
            "status": workflow.status.value,
            "task_stats": task_stats,
            "outputs": outputs,
            "start_time": workflow.start_time.isoformat() if workflow.start_time else None,
            "end_time": workflow.end_time.isoformat() if workflow.end_time else None,
            "duration": (workflow.end_time - workflow.start_time).total_seconds() if workflow.start_time and workflow.end_time else 0,
            "errors": [task.error for task in workflow.tasks if task.error]
        }

    def _log_execution(self, execution_id: str, event: str, data: Dict[str, Any]):
        """记录执行日志"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event,
            "data": data
        }

        if execution_id not in self.execution_logs:
            self.execution_logs[execution_id] = []

        self.execution_logs[execution_id].append(log_entry)

    def get_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """获取执行状态"""
        workflow = self.executions.get(execution_id)
        if not workflow:
            return None

        return self._generate_execution_report(workflow, execution_id)

    def list_executions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """列出执行历史"""
        executions = []

        for execution_id, workflow in list(self.executions.items())[-limit:]:
            status = self.get_status(execution_id)
            if status:
                executions.append(status)

        return executions
