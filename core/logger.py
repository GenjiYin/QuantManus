"""
日志模块
提供统一的日志记录功能
"""
import logging
import sys
from pathlib import Path


class ColoredFormatter(logging.Formatter):
    """带颜色的日志格式化器(仅在终端支持时使用)"""

    # ANSI颜色代码
    COLORS = {
        'DEBUG': '\033[36m',      # 青色
        'INFO': '\033[32m',       # 绿色
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 红色
        'CRITICAL': '\033[35m',   # 紫色
        'RESET': '\033[0m'        # 重置
    }

    def format(self, record):
        # 添加颜色
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.COLORS['RESET']}"
        return super().format(record)


def setup_logger(
    name: str = "QuantManus",
    level: str = "INFO",
    log_file: str = None,
    use_color: bool = True
) -> logging.Logger:
    """
    设置日志记录器

    参数:
        name: 日志记录器名称
        level: 日志级别(DEBUG/INFO/WARNING/ERROR/CRITICAL)
        log_file: 日志文件路径(可选)
        use_color: 是否使用彩色输出

    返回:
        配置好的Logger实例
    """
    logger = logging.getLogger(name)

    # 避免重复添加handler
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper()))

    # 创建控制台handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)

    # 设置格式
    if use_color:
        formatter = ColoredFormatter(
            '%(levelname)s - %(message)s'
        )
    else:
        formatter = logging.Formatter(
            '%(levelname)s - %(message)s'
        )

    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 如果指定了日志文件,添加文件handler
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)

        # 文件日志使用更详细的格式
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


# 创建默认的全局logger
default_logger = setup_logger()


def get_logger(name: str = None) -> logging.Logger:
    """
    获取logger实例

    参数:
        name: logger名称,如果为None则返回默认logger

    返回:
        Logger实例
    """
    if name is None:
        return default_logger
    return logging.getLogger(name)
