import logging
import os
from pathlib import Path


def setup_logger(name: str = "QuantLab") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    # 确保日志目录存在
    log_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # 文件处理器 (utf-8 防止中文乱码)
    fh = logging.FileHandler(log_dir / "quant_system.log", encoding='utf-8')
    ch = logging.StreamHandler()

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)
    logger.setLevel(logging.INFO)

    return logger


# 全局单例 logger
logger = setup_logger()