"""
日志工具
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

# 日志器缓存
_loggers = {}


def setup_logger(name: str = "orchestrator", log_level: str = "INFO"):
    """设置日志器"""

    # 创建日志目录
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # 日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_handler.setFormatter(formatter)

    # 文件处理器
    log_file = log_dir / f"{name}_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # 创建日志器
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    # 缓存日志器
    _loggers[name] = logger

    return logger


def get_logger(name: str = "orchestrator", log_level: str = "INFO"):
    """获取或创建日志器"""

    # 如果已存在，直接返回
    if name in _loggers:
        return _loggers[name]

    # 否则创建新的日志器
    return setup_logger(name, log_level)
