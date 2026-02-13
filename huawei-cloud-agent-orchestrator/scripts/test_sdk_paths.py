import os
from pathlib import Path

# 测试各种可能的路径
paths_to_test = [
    "/root/huawei-service-agent/huaweicloud-sdk-python-v3",
    "/root/huawei-service-agent/huawei-cloud-agent-orchestrator/huaweiicloud-sdk-python-v3",
    "huaweicloud-sdk-python-v3",
    "../huaweicloud-sdk-python-v3",
]

for path in paths_to_test:
    print(f"路径: {path}")
    print(f"存在: {Path(path).exists()}")
    print(f"是目录: {Path(path).is_dir()}")
    print("---")
