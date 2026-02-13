#!/usr/bin/env python3
"""解析华为云SDK，提取API信息并导入向量数据库"""

import sys
import os
import ast
import re
from pathlib import Path
from typing import Dict, List, Any, Optional

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.vector_store import get_vector_store
from utils.logger import get_logger

logger = get_logger(__name__)

# SDK根目录（修正为正确的路径）
SDK_ROOT = Path("/root/huawei-service-agent/huawei-cloud-agent-orchestrator/huaweicloud-sdk-python-v3")

# 服务映射
SERVICE_MAPPING = {
    "ecs": "弹性云服务器",
    "vpc": "虚拟私有云",
    "rds": "关系型数据库",
    "obs": "对象存储服务",
    "cce": "云容器引擎",
    "elb": "弹性负载均衡",
    "as": "弹性伸缩",
    "ims": "镜像服务",
    "evs": "云硬盘",
    "sfs": "弹性文件服务",
    "nat": "NAT网关",
    "csbs": "云服务器备份服务",
    "vbs": "云硬盘备份服务",
    "vpn": "虚拟专用网络",
    "dc": "云专线",
    "dns": "云解析服务",
    "cdn": "内容分发网络",
    "gaussdb": "GaussDB数据库",
    "dcs": "分布式缓存服务",
    "dds": "文档数据库服务",
    "drs": "数据复制服务",
    "iam": "统一身份认证",
    "waf": "Web应用防火墙",
    "kms": "密钥管理服务",
    "ces": "云监控服务",
    "lts": "云日志服务",
    "apm": "应用性能管理",
    "rms": "资源管理服务",
    "config": "配置审计",
    "cts": "云审计服务",
    "dms": "分布式消息服务",
    "kafka": "Kafka消息队列",
    "smn": "消息通知服务",
    "cse": "微服务引擎",
    "modelarts": "AI开发平台",
    "mrs": "MapReduce服务",
    "cdm": "云数据迁移服务",
    "ges": "图引擎服务",
    "mpc": "媒体转码服务",
    "vod": "视频点播服务",
    "oms": "对象存储迁移服务",
    "scm": "SSL证书管理",
    "apig": "API网关",
    "meeting": "云会议",
    "bms": "裸金属服务器",
    "fgs": "函数工作流",
    "cci": "云容器实例",
}


def extract_service_name(sdk_dir_name: str) -> Optional[str]:
    """从SDK目录名提取服务名称"""
    match = re.match(r"huaweicloud-sdk-(.+)", sdk_dir_name)
    if match:
        return match.group(1)
    return None


def find_client_file(sdk_dir: Path, service_name: str) -> Optional[Path]:
    """查找服务的客户端文件"""
    # 1. 在版本子目录下查找 v2/*_client.py, v3/*_client.py
    for version in ['v1', 'v2', 'v3']:
        vdir = sdk_dir / version
        if vdir.is_dir():
            version_client_files = list(vdir.glob("*_client.py"))
            for f in version_client_files:
                if '__pycache__' in str(f):
                    continue
                if service_name in f.name.lower():
                    return f

    # 2. 直接在包目录下查找 *_client.py
    client_files = list(sdk_dir.glob("*_client.py"))
    for f in client_files:
        if '__pycache__' in str(f):
            continue
        if service_name in f.name.lower():
            return f

    return None


def find_model_dir(sdk_dir: Path, client_file: Path) -> Optional[Path]:
    """查找模型目录"""
    if not client_file:
        return None

    # 客户端文件相对路径
    client_rel_path = client_file.relative_to(sdk_dir)

    # 模型目录可能在不同的位置
    possible_paths = []

    # 1. 在版本目录的model子目录下查找
    parent_dir = client_file.parent
    possible_paths.append(parent_dir / "model")

    # 2. 直接查找 huaweicloudsdkxxx/model
    base_name = client_file.name.replace('_client', '').replace('_async_client', '')
    possible_paths.append(sdk_dir / base_name.replace('huaweicloud', 'huaweicloudsdk') / "model")

    # 3. 查找所有 huaweicloudsdkxxx 目录
    for item in sdk_dir.iterdir():
        if item.is_dir() and item.name.startswith('huaweicloudsdk') and 'model' in item.name:
            possible_paths.append(item / "model")

    # 返回第一个存在的目录
    for path in possible_paths:
        if path and path.exists() and path.is_dir():
            return path

    return None


def extract_api_methods_from_client(client_file_path: Path) -> List[Dict[str, Any]]:
    """从客户端文件中提取API方法"""
    methods = []

    try:
        with open(client_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and 'Client' in node.name:
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        if item.name.startswith('_') or item.name in ['__init__', 'new_builder']:
                            continue

                        method_info = {
                            "name": item.name,
                            "docstring": ast.get_docstring(item) or "",
                            "args": [arg.arg for arg in item.args.args],
                            "returns": ast.unparse(item.returns) if item.returns else None
                        }
                        methods.append(method_info)
    except Exception as e:
        logger.warning(f"解析客户端文件失败 {client_file_path}: {e}")

    return methods


def extract_model_fields_from_file(model_file_path: Path) -> Dict[str, Any]:
    """从模型文件中提取字段信息"""
    try:
        with open(model_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_name = node.name
                fields = {}
                for item in node.body:
                    if isinstance(item, ast.AnnAssign):
                        target = item.target
                        if isinstance(target, ast.Name):
                            field_name = target.id
                            field_type = None
                            if item.annotation:
                                field_type = ast.unparse(item.annotation)
                            field_doc = ""
                            if item.value and isinstance(item.value, ast.Str):
                                field_doc = item.value.s
                            fields[field_name] = {
                                "type": field_type,
                                "description": field_doc
                            }

                return {
                    "class_name": class_name,
                    "fields": fields
                }
    except Exception as e:
        logger.warning(f"解析模型文件失败 {model_file_path}: {e}")

    return {}


def find_request_model_name(method_name: str) -> str:
    """从方法名推断请求模型名称"""
    parts = method_name.split('_')
    camel_case = ''.join([p.capitalize() for p in parts])
    return f"{camel_case}Request"


def find_response_model_name(method_name: str) -> str:
    """从方法名推断响应模型名称"""
    parts = method_name.split('_')
    camel_case = ''.join([p.capitalize() for p in parts])
    return f"{camel_case}Response"


def extract_params_from_model(model_name: str, model_dir: Path) -> Dict[str, Any]:
    """从模型目录提取请求/响应参数"""
    # 查找模型文件（尝试小写、大写等）
    possible_files = [
        model_dir / f"{model_name.lower()}.py",
        model_dir / f"{model_name}.py",
        model_dir / f"{model_name.lower()}_request.py",
        model_dir / f"{model_name.lower()}_response.py",
    ]

    for model_file in possible_files:
        if model_file.exists():
            return extract_model_fields_from_file(model_file).get("fields", {})

    return {}


def build_operation_description(service_name: str, operation_name: str, docstring: str) -> str:
    """构建操作描述"""
    service_desc = SERVICE_MAPPING.get(service_name, f"{service_name}服务")
    desc = f"{service_desc}的{operation_name}操作"

    if docstring:
        first_line = docstring.strip().split('\n')[0].strip()
        if first_line and not first_line.startswith(':') and len(first_line) < 100:
            desc = first_line

    return desc


def scan_sdk_for_operations() -> List[Dict[str, Any]]:
    """扫描SDK目录，提取所有操作"""
    operations = []

    if not SDK_ROOT.exists():
        logger.error(f"SDK目录不存在: {SDK_ROOT}")
        return operations

    for sdk_dir in sorted(SDK_ROOT.iterdir()):
        if not sdk_dir.is_dir():
            continue

        service_name = extract_service_name(sdk_dir.name)
        if not service_name or service_name not in SERVICE_MAPPING:
            continue

        logger.info(f"扫描服务: {service_name}")

        client_file = find_client_file(sdk_dir, service_name)

        if not client_file:
            logger.warning(f"未找到 {service_name} 的客户端文件")
            continue

        logger.debug(f"使用客户端文件: {client_file}")

        model_dir = find_model_dir(sdk_dir, client_file)

        if not model_dir:
            logger.warning(f"未找到 {service_name} 的模型目录")

        api_methods = extract_api_methods_from_client(client_file)

        if not api_methods:
            logger.warning(f"未提取到 {service_name} 的任何API方法")
            continue

        for method in api_methods:
            operation_id = f"{service_name}:{method['name']}"

            request_model_name = find_request_model_name(method['name'])
            request_params = {}
            if model_dir:
                request_params = extract_params_from_model(request_model_name, model_dir)

            response_model_name = find_response_model_name(method['name'])
            response_params = {}
            if model_dir:
                response_params = extract_params_from_model(response_model_name, model_dir)

            description = build_operation_description(
                service_name,
                method['name'],
                method['docstring']
            )

            operations.append({
                "operation_id": operation_id,
                "service_name": service_name,
                "operation_name": method['name'],
                "description": description,
                "input_params": request_params,
                "output_params": response_params,
                "metadata": {
                    "service_description": SERVICE_MAPPING.get(service_name, ""),
                    "method_args": method['args'],
                    "return_type": method['returns']
                }
            })

    logger.info(f"共提取 {len(operations)} 个API操作")
    return operations


def import_to_vector_db(clear_existing=False):
    """将SDK解析结果导入向量数据库"""
    logger.info("开始解析华为云SDK并导入向量数据库...")

    vector_store = get_vector_store()

    if clear_existing:
        logger.info("清空已有数据...")
        if vector_store.clear_all():
            logger.info("清空完成")
        else:
            logger.error("清空失败")
            return False

    operations = scan_sdk_for_operations()

    if not operations:
        logger.warning("未提取到任何操作")
        return False

    success_count = vector_store.batch_add_operations(operations)

    stats = vector_store.get_stats()

    logger.info("=" * 80)
    logger.info("SDK解析和导入完成！")
    logger.info(f"成功导入: {success_count}/{len(operations)}")
    logger.info(f"总操作数: {stats['total_operations']}")
    logger.info(f"服务数量: {stats['total_services']}")
    logger.info(f"操作分布: {stats['operations_by_service']}")
    logger.info("=" * 80)

    return success_count > 0


def analyze_service(service_name: str) -> Dict[str, Any]:
    """分析单个服务的API信息"""
    sdk_dir = SDK_ROOT / f"huaweicloud-sdk-{service_name}"

    if not sdk_dir.exists():
        return {"error": f"服务 {service_name} 不存在"}

    result = {
        "service_name": service_name,
        "description": SERVICE_MAPPING.get(service_name, ""),
        "api_count": 0,
        "apis": []
    }

    client_file = find_client_file(sdk_dir, service_name)

    if not client_file:
        return {**result, "error": f"未找到 {service_name} 的客户端文件"}

    logger.info(f"使用客户端文件: {client_file}")

    model_dir = find_model_dir(sdk_dir, client_file)

    api_methods = extract_api_methods_from_client(client_file)
    result["api_count"] = len(api_methods)

    for method in api_methods:
        api_info = {
            "name": method['name'],
            "docstring": method['docstring'],
            "args": method['args']
        }

        if model_dir:
            request_model_name = find_request_model_name(method['name'])
            request_params = extract_params_from_model(request_model_name, model_dir)
            api_info["input_params"] = request_params

            response_model_name = find_response_model_name(method['name'])
            response_params = extract_params_from_model(response_model_name, model_dir)
            api_info["output_params"] = response_params

        result["apis"].append(api_info)

    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="解析华为云SDK并导入向量数据库")
    parser.add_argument("--clear", action="store_true", help="清空已有数据后导入")
    parser.add_argument("--service", type=str, help="仅分析指定服务，如 ims")
    parser.add_argument("--list-services", action="store_true", help="列出所有可用服务")

    args = parser.parse_args()

    if args.list_services:
        print("=" * 60)
        print("可用的华为云服务:")
        print("=" * 60)
        for service_name, desc in SERVICE_MAPPING.items():
            sdk_dir = SDK_ROOT / f"huaweicloud-sdk-{service_name}"
            client_file = find_client_file(sdk_dir, service_name)
            model_dir = find_model_dir(sdk_dir, client_file)
            has_client = "✓" if client_file else "✗"
            has_model = "✓" if model_dir else "✗"
            print(f"{has_client:2s} {service_name:15s} - {desc:30s} [客户端:{has_client} 模型:{has_model}]")
        print("=" * 60)
        sys.exit(0)

    if args.service:
        result = analyze_service(args.service)
        if "error" in result:
            print(f"错误: {result['error']}")
            sys.exit(1)

        print(f"\n服务: {result['service_name']}")
        print(f"描述: {result['description']}")
        print(f"API数量: {result['api_count']}")
        print(f"\nAPI列表 (前10个):")
        for api in result['apis'][:10]:
            print(f"  - {api['name']}")
            if api.get('input_params'):
                print(f"    入参数量: {len(api['input_params'])}")
            if api.get('output_params'):
                print(f"    出参数量: {len(api['output_params'])}")
        sys.exit(0)

    success = import_to_vector_db(clear_existing=args.clear)

    sys.exit(0 if success else 1)
