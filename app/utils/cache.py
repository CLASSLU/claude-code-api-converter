"""
缓存工具模块
提供多种缓存策略和实现
"""

import time
import functools
import threading
from typing import Any, Optional, Dict, Callable, Union
from abc import ABC, abstractmethod
from app.logger_setup import get_logger


class CacheBackend(ABC):
    """缓存后端抽象基类"""

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """删除缓存"""
        pass

    @abstractmethod
    def clear(self) -> bool:
        """清空缓存"""
        pass

    @abstractmethod
    def stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        pass


class MemoryCache(CacheBackend):
    """内存缓存实现"""

    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        """
        初始化内存缓存

        Args:
            max_size: 最大缓存项数量
            default_ttl: 默认过期时间（秒）
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'evictions': 0
        }
        self.logger = get_logger('memory_cache', {})

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self._lock:
            if key not in self._cache:
                self._stats['misses'] += 1
                return None

            entry = self._cache[key]
            current_time = time.time()

            # 检查是否过期
            if entry.get('expires_at') and current_time > entry['expires_at']:
                del self._cache[key]
                self._stats['misses'] += 1
                self.logger.debug(f"Cache entry expired: {key}")
                return None

            self._stats['hits'] += 1
            entry['last_accessed'] = current_time
            return entry['value']

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        with self._lock:
            try:
                current_time = time.time()
                ttl = ttl or self.default_ttl
                expires_at = current_time + ttl if ttl > 0 else None

                # 如果缓存已满，使用LRU策略清理
                if len(self._cache) >= self.max_size and key not in self._cache:
                    self._evict_lru()

                self._cache[key] = {
                    'value': value,
                    'created_at': current_time,
                    'last_accessed': current_time,
                    'expires_at': expires_at,
                    'ttl': ttl
                }

                self._stats['sets'] += 1
                self.logger.debug(f"Cache set: {key} (TTL: {ttl}s)")
                return True
            except Exception as e:
                self.logger.error(f"Cache set error for {key}: {str(e)}")
                return False

    def delete(self, key: str) -> bool:
        """删除缓存"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._stats['deletes'] += 1
                self.logger.debug(f"Cache delete: {key}")
                return True
            return False

    def clear(self) -> bool:
        """清空缓存"""
        with self._lock:
            size = len(self._cache)
            self._cache.clear()
            self.logger.info(f"Cache cleared: {size} items removed")
            return True

    def _evict_lru(self):
        """使用LRU策略清理最久未访问的缓存项"""
        if not self._cache:
            return

        # 找到最久未访问的项
        lru_key = min(self._cache.keys(), key=lambda k: self._cache[k]['last_accessed'])
        del self._cache[lru_key]
        self._stats['evictions'] += 1
        self.logger.debug(f"LRU eviction: {lru_key}")

    def stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self._lock:
            total_requests = self._stats['hits'] + self._stats['misses']
            hit_rate = self._stats['hits'] / total_requests if total_requests > 0 else 0

            return {
                **self._stats,
                'size': len(self._cache),
                'max_size': self.max_size,
                'hit_rate': round(hit_rate, 4),
                'memory_usage_mb': self._estimate_memory_usage()
            }

    def _estimate_memory_usage(self) -> float:
        """估算内存使用量（MB）"""
        import sys
        total_size = 0
        for entry in self._cache.values():
            total_size += sys.getsizeof(entry)
        return round(total_size / (1024 * 1024), 2)


class CacheDecorator:
    """缓存装饰器"""

    def __init__(self, backend: CacheBackend, ttl: Optional[int] = None,
                 key_prefix: str = '', key_builder: Optional[Callable] = None):
        """
        初始化缓存装饰器

        Args:
            backend: 缓存后端
            ttl: 过期时间
            key_prefix: 键前缀
            key_builder: 自定义键构建函数
        """
        self.backend = backend
        self.ttl = ttl
        self.key_prefix = key_prefix
        self.key_builder = key_builder or self._default_key_builder
        self.logger = get_logger('cache_decorator', {})

    def __call__(self, func: Callable) -> Callable:
        """装饰器调用"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 构建缓存键
            cache_key = self.key_builder(func, args, kwargs)

            # 尝试从缓存获取
            cached_result = self.backend.get(cache_key)
            if cached_result is not None:
                self.logger.debug(f"Cache hit for function {func.__name__}: {cache_key}")
                return cached_result

            # 执行函数并缓存结果
            result = func(*args, **kwargs)
            self.backend.set(cache_key, result, self.ttl)
            self.logger.debug(f"Cache set for function {func.__name__}: {cache_key}")

            return result

        # 添加缓存管理方法
        wrapper.cache_clear = lambda: self.backend.clear()
        wrapper.cache_delete = lambda *args, **kwargs: self.backend.delete(
            self.key_builder(func, args, kwargs)
        )
        wrapper.cache_stats = lambda: self.backend.stats()

        return wrapper

    def _default_key_builder(self, func: Callable, args: tuple, kwargs: dict) -> str:
        """默认键构建方法"""
        import hashlib
        import pickle

        # 创建函数唯一标识
        key_parts = [
            self.key_prefix,
            func.__module__,
            func.__name__,
        ]

        # 添加参数标识
        if args or kwargs:
            try:
                # 使用序列化创建参数的稳定哈希
                params = {'args': args, 'kwargs': kwargs}
                params_hash = hashlib.md5(pickle.dumps(params, protocol=2)).hexdigest()
                key_parts.append(params_hash)
            except (TypeError, pickle.PicklingError):
                # 回退到字符串表示
                key_parts.append(str(args) + str(kwargs))

        return ':'.join(str(part) for part in key_parts)


# 预定义缓存装饰器
def cache_result(ttl: int = 300, max_size: int = 1000, key_prefix: str = ''):
    """
    简单的内存缓存装饰器

    Args:
        ttl: 过期时间（秒）
        max_size: 最大缓存项数量
        key_prefix: 键前缀
    """
    cache = MemoryCache(max_size=max_size, default_ttl=ttl)
    return CacheDecorator(cache, ttl=ttl, key_prefix=key_prefix)


def cache_api_response(ttl: int = 300):
    """
    API响应专用缓存装饰器

    Args:
        ttl: 过期时间（秒）
    """
    cache = MemoryCache(max_size=500, default_ttl=ttl)
    return CacheDecorator(cache, ttl=ttl, key_prefix='api')


class CacheWarmer:
    """缓存预热器"""

    def __init__(self, cache_backend: CacheBackend):
        self.cache = cache_backend
        self.logger = get_logger('cache_warmer', {})

    def warm_model_mapping(self, mappings: list):
        """预热模型映射缓存"""
        for mapping in mappings:
            key = f"model_mapping:{mapping.get('anthropic')}"
            self.cache.set(key, mapping.get('openai'), ttl=3600)
            self.logger.debug(f"Warmed model mapping cache: {key}")

    def warm_config(self, config_data: dict):
        """预热配置缓存"""
        for section, data in config_data.items():
            if isinstance(data, dict):
                key = f"config:{section}"
                self.cache.set(key, data, ttl=1800)
                self.logger.debug(f"Warmed config cache: {key}")

    def warm_health_status(self, status: dict):
        """预热健康状态缓存"""
        self.cache.set('health:status', status, ttl=60)
        self.logger.debug("Warmed health status cache")


# 全局缓存实例
_default_cache = None


def get_default_cache() -> MemoryCache:
    """获取默认缓存实例"""
    global _default_cache
    if _default_cache is None:
        _default_cache = MemoryCache(max_size=1000, default_ttl=300)
    return _default_cache


def clear_all_caches():
    """清空所有缓存"""
    global _default_cache
    if _default_cache:
        _default_cache.clear()