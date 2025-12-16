import logging
import os
import time
from threading import Lock
from pathlib import Path
from logging.handlers import RotatingFileHandler

class Logger:
    _instance = None
    _lock = Lock()
    _initialized = False

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(Logger, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        with self._lock:
            if not self._initialized:
                # 创建并配置logger
                self.logger = logging.getLogger("app")
                self.logger.setLevel(logging.INFO)

                # 清除现有处理器（避免重复）
                if self.logger.hasHandlers():
                    self.logger.handlers.clear()

                base_dir = Path(__file__).resolve().parents[1]
                env_log_dir = os.getenv("APP_LOG_DIR")
                log_dir = Path(env_log_dir) if env_log_dir else (base_dir / "logs")
                os.makedirs(log_dir, exist_ok=True)
                
                pid = os.getpid()
                log_path = str(log_dir / f"backend_{pid}.log")

                file_handler = RotatingFileHandler(log_path, maxBytes=10 * 1024 * 1024, backupCount=5)
                file_handler.setLevel(logging.INFO)

                # 设置日志格式
                formatter = logging.Formatter(
                    "%(asctime)s - %(levelname)s - pid=%(process)d - %(name)s - %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S"
                )
                file_handler.setFormatter(formatter)

                self.logger.addHandler(file_handler)

                console_handler = logging.StreamHandler()
                console_handler.setFormatter(formatter)
                self.logger.addHandler(console_handler)

                root = logging.getLogger()
                root.setLevel(logging.INFO)
                if root.handlers:
                    root.handlers.clear()
                root.addHandler(file_handler)
                root.addHandler(console_handler)

                # 测试日志
                self.logger.info("===== 日志系统初始化成功 ======")
                self.logger.info(f"日志文件路径: {log_path}")

                self._initialized = True

    def info(self, msg, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.logger.error(msg, *args, **kwargs)

    def exception(self, msg, *args, **kwargs):
        self.logger.exception(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self.logger.warning(msg, *args, **kwargs)

    def debug(self, msg, *args, **kwargs):
        self.logger.debug(msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        self.logger.critical(msg, *args, **kwargs)


# 创建全局实例
global_logger = Logger()


# 提供直接调用方法的接口
def get_logger():
    return global_logger


# 为了保持与原代码兼容，提供直接访问方法
info = global_logger.info
error = global_logger.error
exception = global_logger.exception
warning = global_logger.warning
debug = global_logger.debug
critical = global_logger.critical
