"""
自然语言工作流自动生成器
基于LLM完全自动化的工作流生成和执行
"""

import json
from typing import Dict, List, Any, Optional
from agents.llm_orchestration_agent import LLMOrchestrationAgent
from services.workflow_engine import WorkflowEngine
from utils.logger import setup_logger


class NaturalLanguageWorkflowGenerator:
    """
    自然语言工作流生成器

    职责:
    1. 接收自然语言描述
    2. 使用LLM生成完整工作流
    3. 自动执行工作流（可选）
    4. 返回执行结果
    """

    def __init__(self):
        self.agent = LLMOrchestrationAgent()
        self.workflow_engine = WorkflowEngine()
        self.logger = setup_logger()

    async def generate_and_execute(
        self,
        requirement: str,
        auto_execute: bool = False,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        从自然语言生成并执行工作流

        Args:
            requirement: 自然语言描述
            auto_execute: 是否自动执行工作流
            context: 可选上下文

        Returns:
            包含工作流和/或执行结果的字典
        """
        self.logger.info(f"收到自然语言需求: {requirement}")

        # 1. 使用LLM生成工作流
        workflow = await self._generate_workflow(requirement, context)

        if not workflow:
            return {
                "success": False,
                "error": "无法生成工作流",
                "message": "LLM生成工作流失败"
            }

        result = {
            "success": True,
            "workflow": workflow.to_dict(),
            "message": "工作流生成成功"
        }

        # 2. 如果需要自动执行
        if auto_execute:
            self.logger.info("自动执行工作流...")
            execution_result = await self.workflow_engine.execute(workflow)
            result["execution"] = execution_result

        return result

    async def _generate_workflow(self, requirement: str, context: Optional[Dict[str, Any]]) -> Any:
        """生成工作流"""
        try:
            # 使用Agent生成工作流
            workflow = self.agent.plan(requirement, context)
            return workflow
        except Exception as e:
            self.logger.error(f"生成工作流失败: {e}")
            return None

    def explain_workflow(self, workflow_dict: Dict[str, Any]) -> str:
        """
        解释工作流

        Args:
            workflow_dict: 工作流字典

        Returns:
            工作流解释文本
        """
        try:
            from agents.llm_orchestration_agent import LLMOrchestrationAgent
            agent = LLMOrchestrationAgent()

            # 从字典创建Workflow对象
            from models.workflow import Workflow
            workflow = Workflow.from_dict(workflow_dict)

            return agent.explain(workflow) or "无法生成解释"
        except Exception as e:
            self.logger.error(f"解释工作流失败: {e}")
            return f"解释失败: {str(e)}"

    def _validate_requirement(self, requirement: str) -> bool:
        """
        验证需求描述是否有效

        Args:
            requirement: 自然语言描述

        Returns:
            是否有效
        """
        if not requirement or len(requirement.strip()) < 5:
            return False
        return True

    async def batch_generate(self, requirements: List[str]) -> List[Dict[str, Any]]:
        """
        批量生成工作流

        Args:
            requirements: 需求列表

        Returns:
            结果列表
        """
        results = []
        for req in requirements:
            result = await self.generate_and_execute(req, auto_execute=False)
            results.append(result)
        return results


# 单例实例
_generator = None


def get_workflow_generator():
    """获取工作流生成器单例"""
    global _generator
    if not _generator:
        _generator = NaturalLanguageWorkflowGenerator()
    return _generator
