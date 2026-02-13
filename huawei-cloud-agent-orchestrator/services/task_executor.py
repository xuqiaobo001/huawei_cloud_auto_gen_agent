"""
任务执行器
负责执行具体的华为云API调用
"""

import importlib
from typing import Dict, Any, Optional
from datetime import datetime
from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkcore.region.region import Region

from utils.logger import setup_logger
from models.workflow import Task


class TaskExecutor:
    """任务执行器

    负责:
    1. 动态创建华为云服务客户端
    2. 执行API调用
    3. 处理认证和授权
    4. 错误处理和重试
    """

    def __init__(self):
        self.logger = setup_logger()
        self.credentials = None
        self.region = "cn-north-4"
        self._init_credentials()

    def _init_credentials(self):
        """初始化认证信息"""
        import os
        ak = os.environ.get('HUAWEICLOUD_SDK_AK')
        sk = os.environ.get('HUAWEICLOUD_SDK_SK')

        if ak and sk:
            self.credentials = BasicCredentials(ak, sk)
            self.logger.info("已配置华为云认证信息")
        else:
            self.logger.warning("未找到华为云认证信息，请在环境变量中设置HUAWEICLOUD_SDK_AK和HUAWEICLOUD_SDK_SK")

    def set_credentials(self, ak: str, sk: str, region: str = "cn-north-4"):
        """设置认证信息"""
        self.credentials = BasicCredentials(ak, sk)
        self.region = region
        self.logger.info(f"更新认证信息，区域: {region}")

    async def execute(self, service: str, operation: str, parameters: Dict[str, Any],
                      timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        执行任务

        Args:
            service: 服务名称，如ecs, vpc, rds
            operation: 操作名称，如create_servers, list_vpcs
            parameters: 请求参数
            timeout: 超时时间(秒)

        Returns:
            API调用结果

        Raises:
            Exception: 执行失败时抛出异常
        """
        self.logger.info(f"执行任务: {service}.{operation}")

        if not self.credentials:
            raise Exception("未配置华为云认证信息")

        try:
            # 动态创建客户端
            client = self._create_client(service)

            # 获取操作调用方法
            operation_method = getattr(client, operation)

            # 创建请求对象
            request = self._create_request(service, operation, parameters)

            # 执行API调用
            response = operation_method(request)

            # 处理响应
            result = self._process_response(response)

            self.logger.info(f"任务 {service}.{operation} 执行成功")
            return result

        except Exception as e:
            self.logger.error(f"任务 {service}.{operation} 执行失败: {str(e)}")
            raise

    def _create_client(self, service: str):
        """
        动态创建服务客户端

        Args:
            service: 服务名称

        Returns:
            服务客户端实例
        """
        try:
            # 根据服务名称确定模块和类名
            service_module = f"huaweicloudsdk{service}"
            client_class_name = f"{self._to_camel_case(service)}Client"

            # 导入模块
            module = importlib.import_module(f"{service_module}.v2.{service}_client")

            # 获取Client类
            client_class = getattr(module, client_class_name)

            # 创建客户端
            client = (client_class.new_builder()
                     .with_credentials(self.credentials)
                     .with_region(self.region)
                     .build())

            return client

        except ImportError as e:
            self.logger.error(f"无法导入服务模块 {service}: {str(e)}")
            raise Exception(f"不支技的服务: {service}")

    def _create_request(self, service: str, operation: str, parameters: Dict[str, Any]):
        """
        创建请求对象

        Args:
            service: 服务名称
            operation: 操作名称
            parameters: 请求参数

        Returns:
            请求对象
        """
        try:
            request_class_name = self._to_pascal_case(operation) + "Request"
            module_name = f"huaweicloudsdk{service}.v2.model.{operation}_request"

            module = importlib.import_module(module_name)
            request_class = getattr(module, request_class_name)

            request = request_class()

            # 设置参数
            for key, value in parameters.items():
                if hasattr(request, key):
                    setattr(request, key, value)

            return request

        except Exception as e:
            self.logger.warning(f"使用简化的请求创建方式 (错误: {str(e)})")
            # 简化的创建方式
            return parameters

    def _process_response(self, response) -> Dict[str, Any]:
        """处理响应"""
        if hasattr(response, 'to_dict'):
            return response.to_dict()
        elif hasattr(response, '__dict__'):
            return response.__dict__
        else:
            return {"response": str(response)}

    def _to_camel_case(self, service: str) -> str:
        """转换服务名到驼峰命名"""
        parts = service.split('_')
        return ''.join(part.capitalize() for part in parts)

    def _to_pascal_case(self, operation: str) -> str:
        """转换操作名到帕斯卡命名"""
        parts = operation.split('_')
        return ''.join(part.capitalize() for part in parts)

    async def test_connection(self, service: str = "ecs") -> bool:
        """测试与服务器的连接"""
        try:
            self.logger.info(f"测试连接: {service}")
            client = self._create_client(service)

            # 执行一个简单的查询操作
            list_method = getattr(client, "list_instances" if hasattr(client, "list_instances") else "list")

            request_params = {"limit": 1} if service == "ecs" else {}
            response = list_method(request_params)

            self.logger.info(f"成功连接 {service}")
            return True

        except Exception as e:
            self.logger.error(f"连接失败 {service}: {str(e)}")
            return False
