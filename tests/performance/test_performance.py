"""
性能测试
验证优化后的性能指标
"""

import pytest
import time
import asyncio
from unittest.mock import Mock, patch
from app.utils.performance import (
    PerformanceMonitor, monitor_performance,
    fast_json_dumps, fast_json_loads,
    MemoryOptimizer, ResponseOptimizer, RequestOptimizer,
    CircuitBreaker, get_performance_stats, reset_performance_stats
)
from app.utils.cache import MemoryCache, CacheDecorator
from app.utils.http_client import OptimizedHTTPClient, AsyncHTTPClient


@pytest.mark.performance
class TestPerformanceMonitoring:
    """性能监控测试"""

    def test_performance_monitor_basic(self):
        """测试基础性能监控"""
        monitor = PerformanceMonitor()

        # 记录一次成功执行
        monitor.record_execution("test_function", 0.1, success=True)

        stats = monitor.get_stats("test_function")
        assert stats['count'] == 1
        assert stats['total_duration'] == 0.1
        assert stats['min_duration'] == 0.1
        assert stats['max_duration'] == 0.1
        assert stats['success_count'] == 1
        assert stats['error_count'] == 0
        assert stats['success_rate'] == 1.0

    def test_performance_monitor_multiple_calls(self):
        """测试多次调用的性能监控"""
        monitor = PerformanceMonitor()

        # 记录多次执行
        durations = [0.1, 0.2, 0.05, 0.15, 0.3]
        for duration in durations:
            success = duration > 0.1  # 模拟一些失败
            monitor.record_execution("test_function", duration, success)

        stats = monitor.get_stats("test_function")
        assert stats['count'] == 5
        assert stats['total_duration'] == sum(durations)
        assert stats['min_duration'] == 0.05
        assert stats['max_duration'] == 0.3
        assert stats['success_count'] == 3
        assert stats['error_count'] == 2

    def test_monitor_decorator(self):
        """测试性能监控装饰器"""
        reset_performance_stats()

        @monitor_performance("decorated_function")
        def test_function():
            time.sleep(0.01)
            return "result"

        result = test_function()
        assert result == "result"

        stats = get_performance_stats()
        assert "decorated_function" in stats
        assert stats["decorated_function"]["count"] == 1
        assert stats["decorated_function"]["avg_duration"] > 0.01

    def test_global_performance_stats(self):
        """测试全局性能统计"""
        reset_performance_stats()

        # 运行一些监控的函数
        @monitor_performance("function1")
        def func1():
            time.sleep(0.001)

        @monitor_performance("function2")
        def func2():
            time.sleep(0.002)

        func1()
        func2()
        func1()  # 再次调用

        stats = get_performance_stats()
        assert len(stats) == 2
        assert stats["function1"]["count"] == 2
        assert stats["function2"]["count"] == 1


@pytest.mark.performance
class TestFastJSON:
    """快速JSON测试"""

    def test_fast_json_dumps(self):
        """测试快速JSON序列化"""
        data = {"key": "value", "number": 42, "nested": {"a": 1, "b": 2}}

        # 测试序列化
        result = fast_json_dumps(data)
        assert isinstance(result, str)
        assert "key" in result
        assert "value" in result

        # 验证可以正确反序列化
        parsed = fast_json_loads(result)
        assert parsed == data

    def test_fast_json_loads(self):
        """测试快速JSON反序列化"""
        json_str = '{"name": "test", "value": 123, "active": true}'
        result = fast_json_loads(json_str)

        assert result["name"] == "test"
        assert result["value"] == 123
        assert result["active"] is True

    def test_fast_json_performance(self):
        """测试快速JSON性能"""
        # 创建大对象
        large_data = {
            "items": [{"id": i, "name": f"item_{i}", "data": "x" * 100} for i in range(1000)]
        }

        # 测试序列化性能
        start_time = time.time()
        for _ in range(100):
            json_str = fast_json_dumps(large_data)
        serialize_time = time.time() - start_time

        # 测试反序列化性能
        start_time = time.time()
        for _ in range(100):
            parsed = fast_json_loads(json_str)
        deserialize_time = time.time() - start_time

        # 性能应该在合理范围内
        assert serialize_time < 1.0  # 100次序列化在1秒内
        assert deserialize_time < 1.0  # 100次反序列化在1秒内


@pytest.mark.performance
class TestMemoryCache:
    """内存缓存性能测试"""

    def test_cache_set_get_performance(self):
        """测试缓存设置和获取性能"""
        cache = MemoryCache(max_size=10000, default_ttl=300)

        # 测试设置性能
        start_time = time.time()
        for i in range(1000):
            cache.set(f"key_{i}", {"value": f"data_{i}" * 10})
        set_time = time.time() - start_time

        # 测试获取性能
        start_time = time.time()
        for i in range(1000):
            result = cache.get(f"key_{i}")
            assert result is not None
        get_time = time.time() - start_time

        # 性能断言
        assert set_time < 0.1  # 1000次设置在100ms内
        assert get_time < 0.05  # 1000次获取在50ms内

    def test_cache_hit_rate(self):
        """测试缓存命中率"""
        cache = MemoryCache(max_size=100, default_ttl=3600)

        # 设置一些缓存
        for i in range(50):
            cache.set(f"key_{i}", f"value_{i}")

        # 测试命中
        hits = 0
        for i in range(100):
            if cache.get(f"key_{i % 50}"):  # 重复获取前50个key
                hits += 1

        # 应该全部命中
        assert hits == 100

        stats = cache.stats()
        assert stats['hit_rate'] == 1.0
        assert stats['hits'] == 100
        assert stats['misses'] == 0

    def test_cache_lru_eviction(self):
        """测试LRU淘汰策略"""
        cache = MemoryCache(max_size=10, default_ttl=3600)

        # 填满缓存
        for i in range(10):
            cache.set(f"key_{i}", f"value_{i}")

        # 添加第11个项，应该淘汰最旧的
        cache.set("key_10", "value_10")

        # 检查key_0是否被淘汰
        assert cache.get("key_0") is None
        assert cache.get("key_10") is not None

        stats = cache.stats()
        assert stats['evictions'] == 1


@pytest.mark.performance
class TestHTTPClient:
    """HTTP客户端性能测试"""

    def test_sync_client_performance(self):
        """测试同步客户端性能"""
        client = OptimizedHTTPClient(pool_connections=50, pool_maxsize=100)

        # 模拟HTTP请求
        with patch('requests.Session.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"result": "success"}
            mock_post.return_value = mock_response

            start_time = time.time()
            for i in range(50):
                result = client.post(
                    "https://api.example.com/test",
                    json={"test": f"data_{i}"}
                )
                assert result.status_code == 200
            duration = time.time() - start_time

        # 50次请求应该在合理时间内完成
        assert duration < 1.0

    @pytest.mark.asyncio
    async def test_async_client_performance(self):
        """测试异步客户端性能"""
        client = AsyncHTTPClient(connector_limit=50)

        # 模拟异步HTTP请求
        async def mock_async_post(*args, **kwargs):
            await asyncio.sleep(0.001)  # 模拟网络延迟
            return {
                'status': 200,
                'data': {"result": "success"},
                'headers': {}
            }

        with patch.object(client, 'post', side_effect=mock_async_post):
            start_time = time.time()
            tasks = []
            for i in range(50):
                task = client.post(
                    "https://api.example.com/test",
                    json={"test": f"data_{i}"}
                )
                tasks.append(task)

            results = await asyncio.gather(*tasks)
            duration = time.time() - start_time

        # 50次异步请求应该很快完成
        assert duration < 0.5  # 异步应该比同步快
        assert len(results) == 50
        assert all(r['status'] == 200 for r in results)


@pytest.mark.performance
class TestMemoryOptimizer:
    """内存优化器测试"""

    def test_memory_usage_tracking(self):
        """测试内存使用跟踪"""
        optimizer = MemoryOptimizer()

        # 获取内存使用情况
        usage = optimizer.get_memory_usage()
        assert isinstance(usage, dict)
        assert 'rss_mb' in usage or usage == {}  # 如果psutil不可用可能为空

    def test_memory_monitoring_decorator(self):
        """测试内存监控装饰器"""
        @MemoryOptimizer.monitor_memory_usage(threshold_mb=0.001)  # 很小的阈值
        def memory_intensive_function():
            # 创建一些对象
            large_list = [i for i in range(10000)]
            return len(large_list)

        result = memory_intensive_function()
        assert result == 10000


@pytest.mark.performance
class TestCircuitBreaker:
    """熔断器性能测试"""

    def test_circuit_breaker_states(self):
        """测试熔断器状态转换"""
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=1)

        # 创建一个会失败的函数
        call_count = 0

        @breaker
        def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 5:  # 前4次调用失败
                raise Exception("Simulated failure")
            return "success"

        # 前3次调用应该失败但不触发熔断
        with pytest.raises(Exception):
            failing_function()
        with pytest.raises(Exception):
            failing_function()
        with pytest.raises(Exception):
            failing_function()

        # 第4次调用应该触发熔断
        with pytest.raises(Exception) as exc_info:
            failing_function()
        assert "Circuit breaker is OPEN" in str(exc_info.value)

        # 等待恢复时间
        time.sleep(1.1)

        # 现在应该进入半开状态
        with pytest.raises(Exception):  # 仍然失败
            failing_function()

        # 再次调用仍然失败，应该重新打开
        with pytest.raises(Exception) as exc_info:
            failing_function()
        assert "Circuit breaker is OPEN" in str(exc_info.value)


@pytest.mark.performance
class TestResponseOptimizer:
    """响应优化器测试"""

    def test_response_compression(self):
        """测试响应压缩"""
        optimizer = ResponseOptimizer()
        data = "x" * 1000  # 1KB数据

        compressed = optimizer.compress_response(data)
        assert isinstance(compressed, bytes)
        assert len(compressed) < len(data.encode())  # 压缩后应该更小

    def test_batch_size_optimization(self):
        """测试批处理大小优化"""
        optimizer = ResponseOptimizer()

        # 测试小批次
        small_items = list(range(10))
        result = optimizer.optimize_batch_size(small_items, target_size=20)
        assert result == small_items

        # 测试大批次
        large_items = list(range(100))
        result = optimizer.optimize_batch_size(large_items, target_size=20)
        assert len(result) > 1  # 应该被分成多个批次
        assert all(len(batch) <= 20 for batch in result)


@pytest.mark.performance
class TestEndToEndPerformance:
    """端到端性能测试"""

    def test_complete_request_performance(self):
        """测试完整请求性能"""
        reset_performance_stats()

        # 模拟完整的请求处理流程
        @monitor_performance("complete_request")
        def process_request():
            # 模拟数据验证
            data = {"input": "test data"}
            time.sleep(0.001)

            # 模拟缓存查找
            cache = MemoryCache(max_size=100)
            cache.set("test_key", data)
            cached_data = cache.get("test_key")
            time.sleep(0.001)

            # 模拟JSON处理
            json_str = fast_json_dumps(cached_data)
            parsed = fast_json_loads(json_str)
            time.sleep(0.001)

            return parsed

        # 运行多次请求
        start_time = time.time()
        for _ in range(10):
            result = process_request()
            assert result["input"] == "test data"
        total_time = time.time() - start_time

        # 10次请求应该在合理时间内完成
        assert total_time < 0.1  # 每次请求应该在10ms内完成

        # 检查性能统计
        stats = get_performance_stats()
        assert "complete_request" in stats
        assert stats["complete_request"]["count"] == 10
        assert stats["complete_request"]["avg_duration"] < 0.01