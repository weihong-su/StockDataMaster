"""
重试工具模块

提供带指数退避的智能重试装饰器和辅助函数
用于增强xtquant等数据源的稳定性
"""

import time
import functools
import logging
from typing import Tuple, Type, Callable, Any


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 0.5,
    max_delay: float = 5.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    logger_name: str = "DataMaster.Retry"
) -> Callable:
    """
    带指数退避的重试装饰器

    Args:
        max_retries: 最大重试次数
        initial_delay: 初始延迟（秒）
        max_delay: 最大延迟（秒）
        backoff_factor: 退避因子
        retryable_exceptions: 可重试的异常类型
        logger_name: 日志记录器名称

    Returns:
        装饰器函数

    Example:
        @retry_with_backoff(max_retries=3, initial_delay=0.5)
        def get_data():
            # 可能失败的操作
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            logger = logging.getLogger(logger_name)
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.debug(
                            f"{func.__name__} 重试 {attempt+1}/{max_retries}, "
                            f"延迟 {delay:.2f}s, 错误: {e}"
                        )
                        time.sleep(delay)
                        delay = min(delay * backoff_factor, max_delay)
                    else:
                        logger.warning(
                            f"{func.__name__} 重试{max_retries}次后失败: {e}"
                        )

            # 所有重试失败
            if last_exception:
                raise last_exception
            return None

        return wrapper
    return decorator


def retry_on_failure(
    func: Callable,
    max_retries: int = 3,
    delay: float = 0.5,
    backoff: bool = True,
    on_retry: Callable = None,
    logger: logging.Logger = None
) -> Any:
    """
    执行带重试的函数调用

    Args:
        func: 要执行的函数
        max_retries: 最大重试次数
        delay: 重试延迟（秒）
        backoff: 是否使用指数退避
        on_retry: 重试时的回调函数
        logger: 日志记录器

    Returns:
        函数执行结果

    Example:
        result = retry_on_failure(
            lambda: api.get_data(),
            max_retries=3,
            delay=0.5
        )
    """
    if logger is None:
        logger = logging.getLogger("DataMaster.Retry")

    current_delay = delay
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            last_exception = e

            if attempt < max_retries:
                if on_retry:
                    on_retry(attempt + 1, e)

                logger.debug(
                    f"重试 {attempt+1}/{max_retries}, "
                    f"延迟 {current_delay:.2f}s, 错误: {e}"
                )

                time.sleep(current_delay)

                if backoff:
                    current_delay = min(current_delay * 2, 10.0)
            else:
                logger.warning(f"重试{max_retries}次后失败: {e}")

    return None


class RetryStats:
    """重试统计收集器"""

    def __init__(self):
        self.total_requests = 0
        self.successful_first_try = 0
        self.successful_after_retry = 0
        self.failed_after_all_retries = 0
        self.total_retries = 0

    def record_success(self, attempts: int):
        """记录成功请求"""
        self.total_requests += 1
        if attempts == 1:
            self.successful_first_try += 1
        else:
            self.successful_after_retry += 1
            self.total_retries += attempts - 1

    def record_failure(self, attempts: int):
        """记录失败请求"""
        self.total_requests += 1
        self.failed_after_all_retries += 1
        self.total_retries += attempts

    def get_stats(self) -> dict:
        """获取统计数据"""
        stats = {
            'total_requests': self.total_requests,
            'successful_first_try': self.successful_first_try,
            'successful_after_retry': self.successful_after_retry,
            'failed_after_all_retries': self.failed_after_all_retries,
            'total_retries': self.total_retries
        }

        if self.total_requests > 0:
            stats['first_try_success_rate'] = (
                self.successful_first_try / self.total_requests * 100
            )
            stats['overall_success_rate'] = (
                (self.successful_first_try + self.successful_after_retry)
                / self.total_requests * 100
            )
            stats['avg_retries_per_request'] = (
                self.total_retries / self.total_requests
            )
        else:
            stats['first_try_success_rate'] = 0
            stats['overall_success_rate'] = 0
            stats['avg_retries_per_request'] = 0

        return stats

    def reset(self):
        """重置统计"""
        self.__init__()
