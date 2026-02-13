"""
LLM客户端封装
支持Anthropic, OpenAI等多种LLM提供商
"""

import json
from typing import Dict, List, Any, Optional, Union
import anthropic
import openai
from utils.logger import setup_logger
from utils.config_manager import get_config


class LLMClient:
    """LLM客户端 - 支持多个提供商"""

    def __init__(self):
        self.config = get_config()
        self.logger = setup_logger()
        self.client = None
        self.provider = None
        self.model = None
        self._initialize_client()

    def _initialize_client(self):
        """初始化LLM客户端"""
        llm_config = self.config.get_llm_config()
        self.provider = llm_config.get('provider', 'anthropic')
        self.model = llm_config.get('model', 'claude-3-sonnet-20240229')
        api_key = llm_config.get('api_key')

        if not api_key:
            self.logger.warning("未配置LLM API密钥，LLM功能将不可用")
            return

        try:
            if self.provider == 'anthropic':
                self.client = anthropic.Anthropic(api_key=api_key)
            elif self.provider == 'openai':
                self.client = openai.OpenAI(api_key=api_key)
            elif self.provider == 'custom':
                endpoint = llm_config.get('endpoint')
                if endpoint:
                    self.client = openai.OpenAI(
                        api_key=api_key,
                        base_url=endpoint
                    )
            else:
                self.logger.error(f"不支持的LLM提供商: {self.provider}")

            self.logger.info(f"LLM客户端初始化成功: {self.provider} - {self.model}")

        except Exception as e:
            self.logger.error(f"初始化LLM客户端失败: {e}")
            self.client = None

    def reinitialize(self):
        """重新初始化LLM客户端（配置变更后调用）"""
        self.config = get_config()
        self.client = None
        self._initialize_client()

    def is_available(self) -> bool:
        """检查LLM是否可用"""
        return self.client is not None

    def get_assembled_prompt(self) -> dict:
        """获取组装后的完整Prompt（用于预览）"""
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt("（用户需求示例：部署一个Web应用）", None, None)
        return {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt
        }

    def generate_workflow(self, user_requirement: str, context: Optional[Dict[str, Any]] = None, relevant_operations: Optional[list] = None, parameter_templates: Optional[Dict] = None, architecture_plan: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """
        使用LLM生成工作流

        Args:
            user_requirement: 用户自然语言描述
            context: 可选上下文
            relevant_operations: 向量搜索返回的相关操作列表（含参数定义）
            parameter_templates: 参数模板字典（操作名 -> 参数结构）
            architecture_plan: 架构计划（由generate_architecture_plan生成）

        Returns:
            工作流定义字典
        """
        if not self.is_available():
            self.logger.warning("LLM不可用，无法生成工作流")
            return None

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            user_requirement, context, relevant_operations,
            parameter_templates=parameter_templates,
            architecture_plan=architecture_plan
        )

        try:
            if self.provider == 'anthropic':
                return self._call_anthropic(system_prompt, user_prompt)
            elif self.provider in ['openai', 'custom']:
                return self._call_openai(system_prompt, user_prompt)
            else:
                return None

        except Exception as e:
            self.logger.error(f"LLM调用失败: {e}")
            return None

    def identify_required_operations(self, user_requirement: str) -> Optional[List[Dict]]:
        """
        轻量级LLM调用：识别用户需求所需的服务和操作

        Args:
            user_requirement: 用户自然语言描述

        Returns:
            List[Dict] 每项包含 service, operation, reason；失败返回 None
        """
        if not self.is_available():
            return None

        from services.huawei_cloud_service_registry import get_registry
        registry = get_registry()
        services_info = []
        for name, service in registry.get_all_services().items():
            ops = list(service.common_operations) if service.common_operations else []
            services_info.append(f"- {name}: {service.description} | 操作: {', '.join(ops)}")
        service_list = '\n'.join(services_info)

        system_prompt = "你是华为云架构分析助手。根据用户需求和可用服务列表，识别需要调用的服务和操作。只返回JSON数组，不要其他文本。"

        user_prompt = f"""用户需求: "{user_requirement}"

可用服务和操作:
{service_list}

请返回一个JSON数组，每个元素包含:
- "service": 服务名称（必须与上方列表完全一致）
- "operation": 操作名称（必须与上方列表完全一致）
- "reason": 为什么需要这个操作

只返回JSON数组，不要markdown代码块或其他文本。"""

        try:
            if self.provider == 'anthropic':
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=1024,
                    temperature=0.0,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}]
                )
                content = response.content[0].text
            elif self.provider in ['openai', 'custom']:
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=1024,
                    temperature=0.0,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                )
                content = response.choices[0].message.content
            else:
                return None

            result = self._parse_json_response(content)
            if isinstance(result, list):
                return result
            return None

        except Exception as e:
            self.logger.error(f"identify_required_operations 失败: {e}")
            return None

    def generate_architecture_plan(self, user_requirement: str) -> Optional[Dict]:
        """
        生成架构计划（Step 1）：分析需求，输出架构模式、DFX级别、所需服务和依赖图

        Args:
            user_requirement: 用户自然语言描述

        Returns:
            架构计划字典，失败返回None
        """
        if not self.is_available():
            return None

        from services.huawei_cloud_service_registry import get_registry
        registry = get_registry()
        services_info = []
        for name, service in registry.get_all_services().items():
            ops = list(service.common_operations) if service.common_operations else []
            services_info.append(f"- {name}: {service.description} | 操作: {', '.join(ops)}")
        service_list = '\n'.join(services_info)

        system_prompt = (
            "你是华为云架构规划专家。分析用户需求，输出架构计划JSON。"
            "只返回JSON对象，不要其他文本。"
        )

        user_prompt = f"""用户需求: "{user_requirement}"

可用服务和操作:
{service_list}

请返回一个JSON对象，包含以下字段:
{{
  "pattern": "架构模式(single/ha/cluster/serverless)",
  "dfx_level": "DFX级别(basic/standard/advanced)",
  "services_needed": [
    {{"service": "服务名", "operation": "操作名", "reason": "原因"}}
  ],
  "dependency_graph": {{
    "层级名": ["该层包含的服务操作"]
  }},
  "notes": "架构说明"
}}

只返回JSON对象，不要markdown代码块或其他文本。"""

        try:
            if self.provider == 'anthropic':
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=1024,
                    temperature=0.0,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}]
                )
                content = response.content[0].text
            elif self.provider in ['openai', 'custom']:
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=1024,
                    temperature=0.0,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                )
                content = response.choices[0].message.content
            else:
                return None

            result = self._parse_json_response(content)
            if isinstance(result, dict):
                return result
            return None

        except Exception as e:
            self.logger.error(f"generate_architecture_plan 失败: {e}")
            return None

    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        config = self.config.get('agent', {})
        system_prompt = config.get('system_prompt', '')

        # 获取可用的服务列表（精简：只保留服务名+描述，节省token）
        from services.huawei_cloud_service_registry import get_registry
        registry = get_registry()
        services_info = []
        for name, service in registry.get_all_services().items():
            services_info.append(f"- {name}: {service.description}")

        service_list = '\n'.join(services_info)

        return f"""{system_prompt}

# 系统已注册的华为云服务（仅可使用以下服务）

{service_list}

# 执行流程

1. 解析用户需求，识别目标架构模式（单机/高可用/容器化/Serverless）
2. 确定所需服务清单，从上方已注册服务中选取
3. 构建依赖拓扑：网络层 → 基础设施层 → 应用层 → 接入层
4. 生成符合上述JSON Schema的工作流，确保零额外文本输出
5. 自检：任务名唯一性、依赖无环、outputs路径正确、参数结构合规
"""

    def _build_user_prompt(self, user_requirement: str, context: Optional[Dict[str, Any]], relevant_operations: Optional[list] = None, parameter_templates: Optional[Dict] = None, architecture_plan: Optional[Dict] = None) -> str:
        """构建用户提示词"""
        context_info = ""
        if context:
            context_info = f"""

# 上下文信息

- 区域: {context.get('region', 'cn-north-4')}
- 项目: {context.get('project_id', '')}
- 可用区: {context.get('availability_zone', '')}
"""

        # 添加向量搜索到的相关API操作（含完整参数定义）
        operations_text = ""
        if relevant_operations:
            operations_text = "\n# 相关API操作（含参数定义）\n\n"
            operations_text += "以下是与用户需求最相关的华为云API操作及其参数定义，请严格使用这些操作和参数：\n\n"
            for i, op in enumerate(relevant_operations, 1):
                operations_text += f"## 操作 {i}: {op.get('service_name', '')}.{op.get('operation_name', '')}\n"
                operations_text += f"{op.get('document', '')}\n\n"

        # 添加参数模板
        templates_text = ""
        if parameter_templates:
            templates_text = "\n# Exact Parameter Templates\n\n"
            templates_text += "以下是各操作的精确参数结构模板，生成工作流时必须严格遵循这些参数结构：\n\n"
            for op_name, template in parameter_templates.items():
                templates_text += f"## {op_name}\n```json\n"
                templates_text += json.dumps(template, indent=2, ensure_ascii=False)
                templates_text += "\n```\n\n"

        # 添加架构计划
        arch_plan_text = ""
        if architecture_plan:
            arch_plan_text = "\n# Architecture Plan\n\n"
            arch_plan_text += json.dumps(architecture_plan, indent=2, ensure_ascii=False)
            arch_plan_text += "\n\n请严格按照上述架构计划生成工作流。\n"

        # 添加示例
        config = self.config.get('agent', {})
        examples = config.get('examples', [])

        examples_text = ""
        if examples:
            examples_text = "\n# 示例工作流\n\n"
            for i, example in enumerate(examples, 1):
                examples_text += f"""
## 示例 {i}: {example['name']}
用户: {example['user_requirement']}
工作流:
{example['workflow']}
"""

        return f"""# 用户需求

用户要求: "{user_requirement}"

请分析这个需求，生成一个合适的工作流来部署和管理华为云资源。{context_info}{arch_plan_text}{operations_text}{templates_text}{examples_text}

# 生成工作流

请为上述需求生成一个工作流JSON。确保：
1. 严格使用上述API操作中定义的service名称和operation名称
2. 严格使用上述API操作中定义的参数名称和参数结构
3. 如果提供了参数模板，必须严格遵循模板中的参数结构
4. 任务顺序合理，考虑依赖关系
5. 包含必要的资源（如VPC先于ECS）
6. 返回合法的JSON格式"""

    def _call_anthropic(self, system_prompt: str, user_prompt: str) -> Optional[Dict[str, Any]]:
        """调用Anthropic API"""
        llm_config = self.config.get_llm_config()

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=llm_config.get('max_tokens', 4096),
                temperature=llm_config.get('temperature', 0.1),
                system=system_prompt,
                messages=[{
                    "role": "user",
                    "content": user_prompt
                }]
            )

            content = response.content[0].text
            return self._parse_json_response(content)

        except Exception as e:
            self.logger.error(f"Anthropic API调用失败: {e}")
            return None

    def _call_openai(self, system_prompt: str, user_prompt: str) -> Optional[Dict[str, Any]]:
        """调用OpenAI API"""
        llm_config = self.config.get_llm_config()

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=llm_config.get('max_tokens', 4096),
                temperature=llm_config.get('temperature', 0.1),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )

            content = response.choices[0].message.content
            return self._parse_json_response(content)

        except Exception as e:
            self.logger.error(f"OpenAI API调用失败: {e}")
            return None

    def _parse_json_response(self, content: str) -> Optional[Dict[str, Any]]:
        """从LLM响应中解析JSON（含截断修复）"""
        # 临时调试：保存原始响应
        try:
            with open('/tmp/llm_raw_response.txt', 'w') as f:
                f.write(content)
        except Exception:
            pass
        try:
            # 提取JSON代码块
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            content = content.strip()

            # 第一次尝试：直接解析
            import json
            try:
                workflow = json.loads(content)
                self.logger.info("成功从LLM响应解析工作流JSON")
                return workflow
            except json.JSONDecodeError:
                pass

            # 第二次尝试：修复常见问题（尾部逗号、截断）
            import re
            fixed = content
            # 移除尾部逗号
            fixed = re.sub(r',\s*([}\]])', r'\1', fixed)

            try:
                workflow = json.loads(fixed)
                self.logger.info("修复尾部逗号后成功解析JSON")
                return workflow
            except json.JSONDecodeError:
                pass

            # 第三次尝试：修复括号不匹配（LLM常见错误：漏掉}或]）
            fixed = self._repair_json_brackets(fixed)
            try:
                workflow = json.loads(fixed)
                self.logger.info("修复括号不匹配后成功解析JSON")
                return workflow
            except json.JSONDecodeError:
                pass

            # 第四次尝试：修复截断的JSON（补全括号）
            open_braces = fixed.count('{') - fixed.count('}')
            open_brackets = fixed.count('[') - fixed.count(']')
            if open_braces > 0 or open_brackets > 0:
                # 去掉最后一个不完整的键值对
                last_complete = max(fixed.rfind('}'), fixed.rfind(']'))
                if last_complete > 0:
                    fixed = fixed[:last_complete + 1]
                # 补全缺失的括号
                open_braces = fixed.count('{') - fixed.count('}')
                open_brackets = fixed.count('[') - fixed.count(']')
                fixed += ']' * open_brackets + '}' * open_braces

                try:
                    workflow = json.loads(fixed)
                    self.logger.info("修复截断JSON后成功解析")
                    return workflow
                except json.JSONDecodeError:
                    pass

            # 最终尝试：使用json_repair库
            try:
                from json_repair import repair_json
                repaired = repair_json(content, return_objects=True)
                if isinstance(repaired, dict):
                    self.logger.info("使用json_repair库成功修复并解析JSON")
                    return repaired
            except ImportError:
                pass
            except Exception as repair_err:
                self.logger.warning(f"json_repair也失败: {repair_err}")

            self.logger.error(f"解析LLM响应的JSON失败，所有修复尝试均失败")
            self.logger.error(f"原始响应前500字符: {content[:500]}")
            return None

        except Exception as e:
            self.logger.error(f"解析LLM响应时发生异常: {e}")
            return None

    def _repair_json_brackets(self, text: str) -> str:
        """
        基于栈的JSON括号修复：当遇到]但栈顶是{时，插入}；反之亦然。
        处理LLM常见的漏掉闭合括号问题。
        """
        result = []
        stack = []
        in_string = False
        escape = False

        for ch in text:
            if escape:
                result.append(ch)
                escape = False
                continue
            if ch == '\\' and in_string:
                result.append(ch)
                escape = True
                continue
            if ch == '"' and not escape:
                in_string = not in_string
                result.append(ch)
                continue
            if in_string:
                result.append(ch)
                continue

            if ch == '{':
                stack.append('{')
                result.append(ch)
            elif ch == '[':
                stack.append('[')
                result.append(ch)
            elif ch == '}':
                # 弹出匹配的{，如果栈顶是[则先补]
                while stack and stack[-1] == '[':
                    result.append(']')
                    stack.pop()
                if stack and stack[-1] == '{':
                    stack.pop()
                result.append(ch)
            elif ch == ']':
                # 弹出匹配的[，如果栈顶是{则先补}
                while stack and stack[-1] == '{':
                    result.append('}')
                    stack.pop()
                if stack and stack[-1] == '[':
                    stack.pop()
                result.append(ch)
            else:
                result.append(ch)

        return ''.join(result)

    def correct_workflow(self, workflow_dict: Dict[str, Any], validation_errors: List[str], relevant_operations: Optional[list] = None) -> Optional[Dict[str, Any]]:
        """
        根据验证错误修正工作流

        Args:
            workflow_dict: 当前工作流JSON
            validation_errors: 验证发现的错误列表
            relevant_operations: 相关API操作（提供正确的schema参考）

        Returns:
            修正后的工作流字典，失败返回None
        """
        if not self.is_available():
            return None

        workflow_json = json.dumps(workflow_dict, indent=2, ensure_ascii=False)
        errors_text = "\n".join(f"- {e}" for e in validation_errors)

        ops_ref = ""
        if relevant_operations:
            ops_ref = "\n# 正确的API操作参考\n\n"
            for op in relevant_operations[:20]:
                ops_ref += f"- {op.get('service_name','')}.{op.get('operation_name','')}\n"

        system_prompt = "你是华为云工作流修正专家。只修复指出的问题，不要改变其他部分。返回完整的修正后工作流JSON。"

        user_prompt = f"""# 当前工作流

```json
{workflow_json}
```

# 验证发现的错误

{errors_text}
{ops_ref}
请修正上述错误，返回完整的修正后工作流JSON。只修复列出的问题，保持其他部分不变。"""

        try:
            if self.provider == 'anthropic':
                return self._call_anthropic(system_prompt, user_prompt)
            elif self.provider in ['openai', 'custom']:
                return self._call_openai(system_prompt, user_prompt)
            return None
        except Exception as e:
            self.logger.error(f"correct_workflow 失败: {e}")
            return None

    def improve_workflow(self, workflow: Dict[str, Any], feedback: str) -> Optional[Dict[str, Any]]:
        """
        根据反馈改进工作流

        Args:
            workflow: 当前工作流
            feedback: 用户反馈

        Returns:
            改进后的工作流
        """
        if not self.is_available():
            return None

        system_prompt = """你是一个工作流优化专家。根据用户反馈改进工作流。

当前工作流:
{workflow_json}

请分析用户反馈并进行相应的改进。
返回改进后的完整工作流JSON。"""

        user_prompt = f"用户反馈: {feedback}"

        workflow_json = json.dumps(workflow, indent=2, ensure_ascii=False)

        if self.provider == 'anthropic':
            return self._call_anthropic(system_prompt.format(workflow_json=workflow_json), user_prompt)
        else:
            return self._call_openai(system_prompt.format(workflow_json=workflow_json), user_prompt)

    def explain_workflow(self, workflow: Dict[str, Any]) -> Optional[str]:
        """
        解释工作流

        Args:
            workflow: 工作流定义

        Returns:
            解释文本
        """
        if not self.is_available():
            return "LLM不可用，无法提供解释"

        workflow_json = json.dumps(workflow, indent=2, ensure_ascii=False)

        user_prompt = f"""请解释以下工作流的用途和执行步骤：

{workflow_json}

请用中文简要说明：
1. 这个工作流的目的是什么
2. 包含哪些任务
3. 执行顺序和依赖关系
4. 会创建哪些云资源"""

        try:
            if self.provider == 'anthropic':
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=1000,
                    temperature=0.3,
                    messages=[{
                        "role": "user",
                        "content": user_prompt
                    }]
                )
                return response.content[0].text
            else:
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=1000,
                    temperature=0.3,
                    messages=[{"role": "user", "content": user_prompt}]
                )
                return response.choices[0].message.content

        except Exception as e:
            self.logger.error(f"生成解释失败: {e}")
            return None
