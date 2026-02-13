#!/bin/bash

# 华为云Agent编排系统启动脚本

echo "=========================================="
echo "华为云Agent编排系统"
echo "=========================================="

# 检查Python3
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到python3命令"
    exit 1
fi

# 检查环境变量
if [[ -z "$HUAWEICLOUD_SDK_AK" || -z "$HUAWEICLOUD_SDK_SK" ]]; then
    echo "警告: 未设置华为云认证环境变量"
    echo "请设置:"
    echo "  export HUAWEICLOUD_SDK_AK=your-access-key"
    echo "  export HUAWEICLOUD_SDK_SK=your-secret-key"
fi

echo "开始启动Web服务..."
echo ""

# 启动应用
python3 main.py
