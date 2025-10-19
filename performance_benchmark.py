#!/usr/bin/env python3
"""
性能基准测试脚本
对比优化前后的性能差异
"""

import time
import json
import statistics
from typing import List, Dict, Any
from pathlib import Path
import sys

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from app.utils.performance import PerformanceMonitor, get_performance_stats, reset_performance_stats
from app.utils.cache import MemoryCache
from app.converter import LiteConverter


class PerformanceBenchmark:
    """性能基准测试类"""

    def __init__(self):
        self.results = {}
        self.monitor = PerformanceMonitor()

    def benchmark_json_serialization(self, iterations=1000):
        """JSON序列化性能测试"""
        print("测试JSON序列化性能...")

        # 创建测试数据
        test_data = {
            "messages": [
                {"role": "user", "content": f"Test message {i}" * 100}
                for i in range(10)
            ],
            "model": "claude-3-5-haiku-20241022",
            "max_tokens": 1024,
            "stream": False
        }

        # 测试标准json
        start_time = time.time()
        for _ in range(iterations):
            json_str = json.dumps(test_data)
        standard_json_time = time.time() - start_time

        # 测试ujson（如果可用）
        ujson_time = None
        try:
            from app.utils.performance import fast_json_dumps
            start_time = time.time()
            for _ in range(iterations):
                json_str = fast_json_dumps(test_data)
            ujson_time = time.time() - start_time
        except ImportError:
            print("ujson不可用，跳过优化JSON测试")

        self.results['json_serialization'] = {
            'standard_json_ms': round(standard_json_time * 1000 / iterations, 4),
            'ujson_ms': round(ujson_time * 1000 / iterations, 4) if ujson_time else None,
            'improvement_percent': round((standard_json_time - ujson_time) / standard_json_time * 100, 2) if ujson_time else None
        }

        print(f"标准JSON: {self.results['json_serialization']['standard_json_ms']:.4f}ms/op")
        if ujson_time:
            print(f"uJSON: {self.results['json_serialization']['ujson_ms']:.4f}ms/op")
            print(f"性能提升: {self.results['json_serialization']['improvement_percent']}%")

    def benchmark_converter_performance(self, iterations=100):
        """转换器性能测试"""
        print("\n测试转换器性能...")

        anthropic_request = {
            "model": "claude-3-5-haiku-20241022",
            "max_tokens": 1024,
            "messages": [
                {
                    "role": "user",
                    "content": "Please process this request with complex data " * 50
                }
            ],
            "stream": False
        }

        mappings = [
            {"anthropic": "claude-3-5-haiku-20241022", "openai": "gpt-4"}
        ]

        converter = LiteConverter(mappings)

        # 测试Anthropic到OpenAI转换
        start_time = time.time()
        for _ in range(iterations):
            result = converter.anthropic_to_openai(anthropic_request)
        conversion_time = time.time() - start_time

        # 防止除零错误
        if conversion_time == 0:
            conversion_time = 0.001

        avg_time_per_conversion = conversion_time / iterations * 1000  # ms

        self.results['converter_performance'] = {
            'avg_conversion_ms': round(avg_time_per_conversion, 4),
            'total_iterations': iterations,
            'throughput_ops_per_sec': round(iterations / conversion_time)
        }

        print(f"转换平均时间: {self.results['converter_performance']['avg_conversion_ms']:.4f}ms")
        print(f"吞吐量: {self.results['converter_performance']['throughput_ops_per_sec']} ops/sec")

    def benchmark_cache_performance(self, operations=10000):
        """缓存性能测试"""
        print("\n测试缓存性能...")

        cache = MemoryCache(max_size=1000, default_ttl=300)

        # 测试写入性能
        start_time = time.time()
        for i in range(operations):
            cache.set(f"key_{i}", {"value": f"data_{i}" * 10})
        write_time = time.time() - start_time

        # 测试读取性能（命中）
        start_time = time.time()
        for i in range(operations):
            result = cache.get(f"key_{i % 1000}")  # 重复读取前1000个key
        read_time = time.time() - start_time

        hits = 0
        for i in range(100):
            if cache.get(f"key_{i % 100}"):
                hits += 1

        self.results['cache_performance'] = {
            'write_ops_per_sec': round(operations / write_time),
            'read_ops_per_sec': round(operations / read_time),
            'avg_write_time_us': round(write_time / operations * 1000000, 2),
            'avg_read_time_us': round(read_time / operations * 1000000, 2),
            'hit_rate': round(hits / 100, 4)
        }

        cache_stats = cache.stats()
        self.results['cache_stats'] = cache_stats

        print(f"写入吞吐量: {self.results['cache_performance']['write_ops_per_sec']} ops/sec")
        print(f"读取吞吐量: {self.results['cache_performance']['read_ops_per_sec']} ops/sec")
        print(f"命中率: {self.results['cache_performance']['hit_rate']}")

    def benchmark_memory_usage(self):
        """内存使用测试"""
        print("\n测试内存使用...")

        try:
            from app.utils.performance import MemoryOptimizer

            # 获取初始内存使用
            initial_memory = MemoryOptimizer.get_memory_usage()

            # 创建大量对象
            large_objects = []
            for i in range(1000):
                large_objects.append({
                    'id': i,
                    'data': 'x' * 1000,
                    'nested': {'value': i * 2}
                })

            # 获取峰值内存使用
            peak_memory = MemoryOptimizer.get_memory_usage()

            # 清理对象
            del large_objects

            # 获取清理后内存使用
            final_memory = MemoryOptimizer.get_memory_usage()

            self.results['memory_usage'] = {
                'initial_mb': initial_memory.get('rss_mb', 0),
                'peak_mb': peak_memory.get('rss_mb', 0),
                'final_mb': final_memory.get('rss_mb', 0),
                'peak_increase_mb': round(
                    peak_memory.get('rss_mb', 0) - initial_memory.get('rss_mb', 0), 2
                )
            }

            print(f"初始内存: {self.results['memory_usage']['initial_mb']:.2f}MB")
            print(f"峰值内存: {self.results['memory_usage']['peak_mb']:.2f}MB")
            print(f"内存增长: {self.results['memory_usage']['peak_increase_mb']:.2f}MB")

        except ImportError:
            print("psutil不可用，跳过内存测试")
            self.results['memory_usage'] = {'error': 'psutil not available'}

    def benchmark_throughput(self, duration_seconds=10):
        """吞吐量测试"""
        print(f"\n测试吞吐量 ({duration_seconds}秒)...")

        reset_performance_stats()
        converter = LiteConverter()

        request = {
            "model": "claude-3-5-haiku-20241022",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": "Test message"}]
        }

        start_time = time.time()
        operations = 0

        while time.time() - start_time < duration_seconds:
            converter.anthropic_to_openai(request)
            operations += 1

        actual_duration = time.time() - start_time
        throughput = operations / actual_duration

        self.results['throughput'] = {
            'operations': operations,
            'duration_seconds': round(actual_duration, 2),
            'ops_per_sec': round(throughput, 2),
            'avg_response_time_ms': round(actual_duration / operations * 1000, 4)
        }

        print(f"操作数: {self.results['throughput']['operations']}")
        print(f"吞吐量: {self.results['throughput']['ops_per_sec']} ops/sec")
        print(f"平均响应时间: {self.results['throughput']['avg_response_time_ms']:.4f}ms")

    def run_all_benchmarks(self):
        """运行所有基准测试"""
        print("=" * 60)
        print("开始性能基准测试")
        print("=" * 60)

        self.benchmark_json_serialization()
        self.benchmark_converter_performance()
        self.benchmark_cache_performance()
        self.benchmark_memory_usage()
        self.benchmark_throughput()

        self.generate_report()

    def generate_report(self):
        """生成性能报告"""
        print("\n" + "=" * 60)
        print("性能基准测试报告")
        print("=" * 60)

        # JSON序列化报告
        if 'json_serialization' in self.results:
            json_res = self.results['json_serialization']
            print(f"\nJSON序列化性能:")
            print(f"  标准库: {json_res['standard_json_ms']:.4f}ms/op")
            if json_res['ujson_ms']:
                print(f"  uJSON: {json_res['ujson_ms']:.4f}ms/op")
                print(f"  性能提升: {json_res['improvement_percent']}%")

        # 转换器性能报告
        if 'converter_performance' in self.results:
            conv_res = self.results['converter_performance']
            print(f"\n转换器性能:")
            print(f"  平均转换时间: {conv_res['avg_conversion_ms']:.4f}ms")
            print(f"  吞吐量: {conv_res['throughput_ops_per_sec']} ops/sec")

        # 缓存性能报告
        if 'cache_performance' in self.results:
            cache_res = self.results['cache_performance']
            print(f"\n缓存性能:")
            print(f"  写入吞吐量: {cache_res['write_ops_per_sec']} ops/sec")
            print(f"  读取吞吐量: {cache_res['read_ops_per_sec']} ops/sec")
            print(f"  命中率: {cache_res['hit_rate']}")

        # 内存使用报告
        if 'memory_usage' in self.results:
            mem_res = self.results['memory_usage']
            if 'error' not in mem_res:
                print(f"\n内存使用:")
                print(f"  初始: {mem_res['initial_mb']:.2f}MB")
                print(f"  峰值: {mem_res['peak_mb']:.2f}MB")
                print(f"  增长: {mem_res['peak_increase_mb']:.2f}MB")

        # 吞吐量报告
        if 'throughput' in self.results:
            through_res = self.results['throughput']
            print(f"\n系统吞吐量:")
            print(f"  总操作数: {through_res['operations']}")
            print(f"  吞吐量: {through_res['ops_per_sec']} ops/sec")
            print(f"  平均响应时间: {through_res['avg_response_time_ms']:.4f}ms")

        # 保存详细报告
        self.save_report()

    def save_report(self):
        """保存详细报告到文件"""
        report_file = Path("performance_report.json")

        # 添加时间戳
        self.results['timestamp'] = time.time()
        self.results['timestamp_iso'] = time.strftime("%Y-%m-%d %H:%M:%S")

        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, indent=2, ensure_ascii=False)
            print(f"\n详细报告已保存到: {report_file}")
        except Exception as e:
            print(f"保存报告失败: {e}")


def main():
    """主函数"""
    try:
        benchmark = PerformanceBenchmark()
        benchmark.run_all_benchmarks()

        print("\n" + "=" * 60)
        print("基准测试完成！")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"\n测试执行出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()