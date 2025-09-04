import logging
from logging.handlers import TimedRotatingFileHandler
import os
import re
import time


class FileLog:
    def __init__(self):
        self._setup_logger = None

    def _setup_logger(self):
        # 配置日志
        m_logger = logging.getLogger("DailyLogger")
        m_logger.setLevel(logging.INFO)

        # 日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # 创建每天轮转的日志处理器
        log_file = "app.log"
        handler = TimedRotatingFileHandler(
            filename=log_file,
            when="midnight",  # 每天午夜轮转
            interval=1,  # 每天一次
            backupCount=7,  # 保留7个备份文件
            encoding="utf-8"
        )
        handler.setFormatter(formatter)
        handler.suffix = "%Y-%m-%d-%H-%M-%S"  # 备份文件后缀格式

        # 设置删除旧日志的回调
        def delete_old_logs():
            # 获取所有匹配的日志文件
            log_dir = os.path.dirname(os.path.abspath(log_file))
            base_name = os.path.basename(log_file)

            # 匹配模式：app.log.2023-10-01 等
            pattern = re.compile(rf"^{re.escape(base_name)}\.\d{{4}}-\d{{2}}-\d{{2}}$")

            # 计算7天前的时间戳
            seven_days_ago = time.time() - 7 * 24 * 60 * 60

            # 遍历日志目录
            for filename in os.listdir(log_dir):
                filepath = os.path.join(log_dir, filename)

                # 检查是否匹配日志文件模式且超过7天
                if pattern.match(filename) and os.path.isfile(filepath):
                    file_mtime = os.path.getmtime(filepath)
                    if file_mtime < seven_days_ago:
                        try:
                            os.remove(filepath)
                            print(f"Deleted old log: {filepath}")
                        except Exception as e:
                            print(f"Error deleting {filepath}: {e}")

        # 将删除函数绑定到日志轮转事件
        handler.doRollover = lambda: (
            TimedRotatingFileHandler.doRollover(handler),
            delete_old_logs()
        )

        m_logger.addHandler(handler)
        self.m_logger = m_logger
