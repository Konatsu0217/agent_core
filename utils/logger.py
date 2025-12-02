import logging
import os
import time
from threading import Lock

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

                # 确保日志目录存在
                log_dir = "./logs"
                os.makedirs(log_dir, exist_ok=True)
                
                # 创建带时间戳的日志文件路径
                timestamp = time.time()
                log_path = os.path.join(log_dir, f"backend_{timestamp}.log")

                # 创建文件处理器
                file_handler = logging.FileHandler(log_path, mode='a')
                file_handler.setLevel(logging.INFO)

                # 设置日志格式
                formatter = logging.Formatter(
                    "%(asctime)s - %(levelname)s - %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S"
                )
                file_handler.setFormatter(formatter)

                # 添加文件处理器
                self.logger.addHandler(file_handler)

                # 添加控制台处理器
                console_handler = logging.StreamHandler()
                console_handler.setFormatter(formatter)
                self.logger.addHandler(console_handler)

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