"""
性能优化工具
提供性能监控、优化和各种性能提升功能
"""

import time
import json
import sys
import traceback
from typing import Dict, Any, Callable, Optional
from functools import wraps
from app.logger_setup import get_logger


class PerformanceMonitor:
    """性能监控器"""

    def __init__(self):
        self.metrics = {}
        self.logger = get_logger('performance_monitor', {})

    def record_execution(self, name: str, duration: float, success: bool = True):
        """记录执行指标"""
        if name not in self.metrics:
            self.metrics[name] = {
                'count': 0,
                'total_duration': 0,
                'min_duration': float('inf'),
                'max_duration': 0,
                'success_count': 0,
                'error_count': 0
            }

        metrics = self.metrics[name]
        metrics['count'] += 1
        metrics['total_duration'] += duration
        metrics['min_duration'] = min(metrics['min_duration'], duration)
        metrics['max_duration'] = max(metrics['max_duration'], duration)

        if success:
            metrics['success_count'] += 1
        else:
            metrics['error_count'] += 1

    def get_stats(self, name: str) -> Dict[str, Any]:
        """获取指定名称的统计信息"""
        if name not in self.metrics:
            return {}

        metrics = self.metrics[name]
        count = metrics['count']
        if count == 0:
            return metrics

        return {
            **metrics,
            'avg_duration': metrics['total_duration'] / count,
            'success_rate': metrics['success_count'] / count
        }

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取所有统计信息"""
        return {name: self.get_stats(name) for name in self.metrics}

    def reset(self, name: Optional[str] = None):
        """重置统计信息"""
        if name:
            self.metrics.pop(name, None)
        else:
            self.metrics.clear()


# 全局性能监控器实例
_global_monitor = PerformanceMonitor()


def monitor_performance(name: Optional[str] = None):
    """
    性能监控装饰器

    Args:
        name: 监控名称，默认使用函数名
    """
    def decorator(func: Callable) -> Callable:
        monitor_name = name or f"{func.__module__}.{func.__name__}"

        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                _global_monitor.logger.error(f"Error in {monitor_name}: {str(e)}")
                raise
            finally:
                duration = time.time() - start_time
                _global_monitor.record_execution(monitor_name, duration, success)

        return wrapper
    return decorator


def fast_json_dumps(obj: Any, ensure_ascii: bool = False) -> str:
    """
    快速JSON序列化
    尝试使用ujson，回退到标准json
    """
    try:
        import ujson
        return ujson.dumps(obj, ensure_ascii=ensure_ascii)
    except ImportError:
        return json.dumps(obj, ensure_ascii=ensure_ascii)


def fast_json_loads(s: str) -> Any:
    """
    快速JSON反序列化
    尝试使用ujson，回退到标准json
    """
    try:
        import ujson
        return ujson.loads(s)
    except ImportError:
        return json.loads(s)


def optimize_string_operations():
    """字符串操作优化配置"""
    # 对于频繁的字符串拼接，使用join而不是+
    # 对于正则表达式，预编译模式
    import re

    # 预编译常用正则表达式
    compiled_patterns = {
        'sse_line': re.compile(r'^data:\s*(.+)$'),
        'json_extraction': re.compile(r'\{.*\}'),
        'token_approximation': re.compile(r'\w+')
    }

    return compiled_patterns


class MemoryOptimizer:
    """内存优化器"""

    @staticmethod
    def clear_large_objects():
        """清理大对象"""
        import gc
        gc.collect()

    @staticmethod
    def get_memory_usage() -> Dict[str, float]:
        """获取内存使用情况"""
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            return {
                'rss_mb': memory_info.rss / (1024 * 1024),
                'vms_mb': memory_info.vms / (1024 * 1024)
            }
        except ImportError:
            return {}

    @staticmethod
    def monitor_memory_usage(threshold_mb: float = 500.0):
        """内存使用监控装饰器"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                initial_memory = MemoryOptimizer.get_memory_usage().get('rss_mb', 0)
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    final_memory = MemoryOptimizer.get_memory_usage().get('rss_mb', 0)
                    memory_increase = final_memory - initial_memory

                    if memory_increase > threshold_mb:
                        logger = get_logger('memory_optimizer', {})
                        logger.warning(
                            f"High memory usage detected in {func.__name__}: "
                            f"+{memory_increase:.2f}MB (total: {final_memory:.2f}MB)"
                        )
            return wrapper
        return decorator


class ResponseOptimizer:
    """响应优化器"""

    @staticmethod
    def compress_response(data: str) -> bytes:
        """响应压缩"""
        try:
            import gzip
            return gzip.compress(data.encode('utf-8'))
        except ImportError:
            return data.encode('utf-8')

    @staticmethod
    def optimize_batch_size(items: list, target_size: int = 1000) -> list:
        """优化批处理大小"""
        if len(items) <= target_size:
            return items

        # 智能分批策略
        optimal_size = min(target_size, max(10, len(items) // 10))
        return [items[i:i + optimal_size] for i in range(0, len(items), optimal_size)]


class RequestOptimizer:
    """请求优化器"""

    @staticmethod
    def batch_requests(requests_data: list, batch_size: int = 10):
        """批量请求处理"""

        async def async_batch_process(async_client):
            """异步批量处理"""
            import asyncio
            semaphore = asyncio.Semaphore(batch_size)

            async def process_single_request(request_data):
                async with semaphore:
                    return await async_client.post(**request_data)

            tasks = [process_single_request(req) for req in requests_data]
            return await asyncio.gather(*tasks)

        return async_batch_process

    @staticmethod
    def optimize_headers(headers: Dict[str, str]) -> Dict[str, str]:
        """优化HTTP头"""
        # 移除重复和空的头部
        optimized = {}
        for key, value in headers.items():
            if value and key.lower() not in optimized:
                optimized[key.lower()] = value
        return optimized


class CircuitBreaker:
    """熔断器模式实现"""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        """
        初始化熔断器

        Args:
            failure_threshold: 失败阈值
            recovery_timeout: 恢复超时时间（秒）
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        self.logger = get_logger('circuit_breaker', {})

    def __call__(self, func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if self.state == 'OPEN':
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = 'HALF_OPEN'
                    self.logger.info("Circuit breaker entering HALF_OPEN state")
                else:
                    raise Exception("Circuit breaker is OPEN")

            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            except Exception as e:
                self._on_failure()
                raise
        return wrapper

    def _on_success(self):
        """成功处理"""
        if self.state == 'HALF_OPEN':
            self.state = 'CLOSED'
            self.failure_count = 0
            self.logger.info("Circuit breaker closed after successful request")

    def _on_failure(self):
        """失败处理"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'
            self.logger.warning(f"Circuit breaker opened after {self.failure_count} failures")


def get_performance_stats() -> Dict[str, Any]:
    """获取性能统计信息"""
    return _global_monitor.get_all_stats()


def reset_performance_stats():
    """重置性能统计"""
    _global_monitor.reset()