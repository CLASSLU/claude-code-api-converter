"""
装饰器集合
提供性能监控、缓存、重试等功能
"""

import time
import functools
import json
from datetime import datetime
from app.logger_setup import get_logger


def monitor_performance(func):
    """
    性能监控装饰器
    记录函数执行时间和调用统计
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            status = 'success'
            return result
        except Exception as e:
            status = 'error'
            raise
        finally:
            duration = time.time() - start_time
            logger = get_logger('performance_monitor', {})
            logger.info(f"Performance: {func.__name__} - {status} - {duration:.3f}s")
    return wrapper


def retry(max_attempts=3, delay=1, backoff=2, exceptions=(Exception,)):
    """
    重试装饰器

    Args:
        max_attempts: 最大重试次数
        delay: 初始延迟时间（秒）
        backoff: 退避倍数
        exceptions: 需要重试的异常类型
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            last_exception = None

            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempts += 1
                    last_exception = e

                    if attempts >= max_attempts:
                        logger = get_logger('retry_decorator', {})
                        logger.error(f"Failed after {attempts} attempts: {func.__name__} - {str(e)}")
                        raise

                    wait_time = delay * (backoff ** (attempts - 1))
                    logger = get_logger('retry_decorator', {})
                    logger.warning(f"Attempt {attempts} failed for {func.__name__}: {str(e)}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)

            raise last_exception
        return wrapper
    return decorator


def cache_result(ttl_seconds=300, max_size=128):
    """
    简单的结果缓存装饰器

    Args:
        ttl_seconds: 缓存过期时间（秒）
        max_size: 最大缓存大小
    """
    def decorator(func):
        cache = {}
        cache_timestamps = {}

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 创建缓存键
            cache_key = str(args) + str(sorted(kwargs.items()))
            current_time = time.time()

            # 检查缓存
            if cache_key in cache:
                cache_age = current_time - cache_timestamps[cache_key]
                if cache_age < ttl_seconds:
                    logger = get_logger('cache_decorator', {})
                    logger.debug(f"Cache hit for {func.__name__}: {cache_key}")
                    return cache[cache_key]
                else:
                    # 过期删除
                    del cache[cache_key]
                    del cache_timestamps[cache_key]

            # 执行函数并缓存结果
            result = func(*args, **kwargs)

            # 限制缓存大小
            if len(cache) >= max_size:
                # 删除最旧的缓存项
                oldest_key = min(cache_timestamps.keys(), key=lambda k: cache_timestamps[k])
                del cache[oldest_key]
                del cache_timestamps[oldest_key]

            # 添加新缓存
            cache[cache_key] = result
            cache_timestamps[cache_key] = current_time

            logger = get_logger('cache_decorator', {})
            logger.debug(f"Cache set for {func.__name__}: {cache_key}")

            return result

        # 添加缓存管理方法
        def clear_cache():
            cache.clear()
            cache_timestamps.clear()

        def cache_stats():
            return {
                'size': len(cache),
                'max_size': max_size,
                'ttl_seconds': ttl_seconds
            }

        wrapper.clear_cache = clear_cache
        wrapper.cache_stats = cache_stats
        return wrapper

    return decorator


def validate_json(required_fields=None, optional_fields=None):
    """
    JSON数据验证装饰器

    Args:
        required_fields: 必需字段列表
        optional_fields: 可选字段列表
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 假设第一个参数是包含JSON数据的request对象
            if args and hasattr(args[0], 'get_json'):
                request = args[0]
                data = request.get_json(silent=True) or {}
            else:
                return func(*args, **kwargs)

            # 验证必需字段
            if required_fields:
                missing_fields = [field for field in required_fields if field not in data]
                if missing_fields:
                    from app.core.exceptions import create_validation_error
                    raise create_validation_error(
                        message=f"Missing required fields: {', '.join(missing_fields)}",
                        field='missing_fields'
                    )

            # 验证字段类型
            if optional_fields:
                for field, field_type in optional_fields.items():
                    if field in data and not isinstance(data[field], field_type):
                        from app.core.exceptions import create_validation_error
                        raise create_validation_error(
                            message=f"Field '{field}' must be of type {field_type.__name__}",
                            field=field,
                            value=data[field]
                        )

            return func(*args, **kwargs)
        return wrapper
    return decorator


def rate_limit(calls=10, period=60):
    """
    简单的限流装饰器

    Args:
        calls: 允许的调用次数
        period: 时间周期（秒）
    """
    def decorator(func):
        call_times = []

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_time = time.time()

            # 清理过期的调用记录
            call_times[:] = [call_time for call_time in call_times
                           if current_time - call_time < period]

            # 检查是否超过限制
            if len(call_times) >= calls:
                from app.core.exceptions import RateLimitError
                raise RateLimitError(
                    message=f"Rate limit exceeded: {calls} calls per {period} seconds",
                    retry_after=int(period - (current_time - call_times[0]))
                )

            # 记录当前调用
            call_times.append(current_time)

            return func(*args, **kwargs)
        return wrapper
    return decorator


def async_compatible(func):
    """
    异步兼容性装饰器
    为同步函数提供异步包装
    """
    import asyncio

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        # 如果是协程，直接await
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        # 否则在事件循环中执行同步函数
        else:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))

    # 保留同步版本
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    # 根据调用上下文返回适当的版本
    def wrapper(*args, **kwargs):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                return async_wrapper(*args, **kwargs)
            else:
                return sync_wrapper(*args, **kwargs)
        except RuntimeError:
            return sync_wrapper(*args, **kwargs)

    return wrapper