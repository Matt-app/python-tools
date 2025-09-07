import time
from functools import wraps
from api.log.local_log import logger


def timeit(name=None, log_level='DEBUG'):
    """简单的耗时装饰器：记录方法执行耗时（毫秒）到日志。
    用法：@timeit() 或 @timeit('custom_name')
    """
    def _deco(func):
        label = name or func.__qualname__

        @wraps(func)
        def _wrapper(*args, **kwargs):
            _start = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                _cost_ms = (time.time() - _start) * 1000.0
                if log_level == 'DEBUG':
                    logger.info("TIME %s took %.2f ms", label, _cost_ms)
                elif log_level == 'INFO':
                    logger.info("TIME %s took %.2f ms", label, _cost_ms)
        return _wrapper

    return _deco
