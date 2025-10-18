#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SSE数据流深度分析工具
对比直接Anthropic API与本项目的响应差异
"""

import time
import json
import requests
import threading
from datetime import datetime
from collections import defaultdict
import sys

class SSEAnalyzer:
    """SSE数据流分析器"""

    def __init__(self):
        self.chunks = []
        self.timings = []
        self.start_time = None

    def analyze_sse_stream(self, response, source_name):
        """分析SSE数据流"""
        self.chunks = []
        self.timings = []
        self.start_time = time.time()

        print(f"\n🔍 分析 {source_name} 的SSE数据流...")

        for line in response.iter_lines(decode_unicode=True):
            if line and line.startswith('data:'):
                current_time = time.time()
                elapsed = (current_time - self.start_time) * 1000

                chunk_data = {
                    'timestamp': current_time,
                    'elapsed_ms': elapsed,
                    'raw_line': line,
                    'content': line[5:].strip(),  # 移除 "data: " 前缀
                    'size': len(line.encode('utf-8'))
                }

                self.chunks.append(chunk_data)
                self.timings.append(elapsed)

                # 打印前几个数据块
                if len(self.chunks) <= 5:
                    print(f"  块 {len(self.chunks)}: {elapsed:.2f}ms - {line[:80]}...")

                if '[DONE]' in line:
                    break

        return self.get_analysis(source_name)

    def get_analysis(self, source_name):
        """获取分析结果"""
        if not self.chunks:
            return {"error": "无数据"}

        # 计算时间间隔
        intervals = []
        for i in range(1, len(self.chunks)):
            interval = self.chunks[i]['elapsed_ms'] - self.chunks[i-1]['elapsed_ms']
            intervals.append(interval)

        # 分析数据块类型
        block_types = defaultdict(int)
        for chunk in self.chunks:
            try:
                if chunk['content'] == '[DONE]':
                    block_types['DONE'] += 1
                else:
                    data = json.loads(chunk['content'])
                    if isinstance(data, dict):
                        msg_type = data.get('type', 'unknown')
                        block_types[msg_type] += 1
            except:
                block_types['parse_error'] += 1

        analysis = {
            'source': source_name,
            'total_chunks': len(self.chunks),
            'total_time_ms': self.chunks[-1]['elapsed_ms'] if self.chunks else 0,
            'avg_chunk_size': sum(c['size'] for c in self.chunks) / len(self.chunks),
            'block_types': dict(block_types)
        }

        if intervals:
            analysis.update({
                'avg_interval_ms': sum(intervals) / len(intervals),
                'max_interval_ms': max(intervals),
                'min_interval_ms': min(intervals),
                'interval_std': self._std(intervals),
                'large_intervals': [i for i in intervals if i > 100],  # 超过100ms的间隔
                'small_intervals': [i for i in intervals if i < 10],   # 小于10ms的间隔
            })

        return analysis

    def _std(self, values):
        """计算标准差"""
        if not values:
            return 0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5

def test_direct_anthropic_api():
    """测试直接Anthropic API"""
    print("\n🚀 测试直接Anthropic API...")

    # 这里需要真实的API密钥
    headers = {
        'Content-Type': 'application/json',
        'x-api-key': 'sk-ant-api03-...',  # 需要真实的密钥
        'anthropic-version': '2023-06-01'
    }

    data = {
        "model": "claude-3-5-haiku-20241022",
        "max_tokens": 500,
        "messages": [
            {"role": "user", "content": "请简要回答1+1等于多少？"}
        ],
        "stream": True
    }

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=data,
            stream=True,
            timeout=30
        )

        if response.status_code == 200:
            analyzer = SSEAnalyzer()
            return analyzer.analyze_sse_stream(response, "Direct Anthropic API")
        else:
            print(f"❌ 直接API请求失败: {response.status_code}")
            return None

    except Exception as e:
        print(f"❌ 直接API测试异常: {e}")
        return None

def test_proxy_api():
    """测试本项目代理API"""
    print("\n🔄 测试本项目代理API...")

    headers = {
        'Content-Type': 'application/json'
    }

    data = {
        "model": "claude-3-5-haiku-20241022",
        "max_tokens": 500,
        "messages": [
            {"role": "user", "content": "请简要回答1+1等于多少？"}
        ],
        "stream": True
    }

    try:
        response = requests.post(
            "http://127.0.0.1:8080/v1/messages",
            headers=headers,
            json=data,
            stream=True,
            timeout=30
        )

        if response.status_code == 200:
            analyzer = SSEAnalyzer()
            return analyzer.analyze_sse_stream(response, "Proxy API")
        else:
            print(f"❌ 代理API请求失败: {response.status_code}")
            return None

    except Exception as e:
        print(f"❌ 代理API测试异常: {e}")
        return None

def compare_and_analyze(direct_result, proxy_result):
    """对比分析结果"""
    print("\n" + "="*60)
    print("📊 SSE数据流对比分析")
    print("="*60)

    if not direct_result and not proxy_result:
        print("❌ 两个API都无法访问")
        return

    if direct_result:
        print(f"\n🔵 直接Anthropic API分析:")
        print(f"   总数据块数: {direct_result['total_chunks']}")
        print(f"   总传输时间: {direct_result['total_time_ms']:.2f}ms")
        if 'avg_interval_ms' in direct_result:
            print(f"   平均间隔: {direct_result['avg_interval_ms']:.2f}ms")
            print(f"   最大间隔: {direct_result['max_interval_ms']:.2f}ms")
            print(f"   最小间隔: {direct_result['min_interval_ms']:.2f}ms")
            print(f"   间隔标准差: {direct_result['interval_std']:.2f}ms")
            print(f"   大间隔(>100ms): {len(direct_result['large_intervals'])}个")
            print(f"   小间隔(<10ms): {len(direct_result['small_intervals'])}个")
        print(f"   数据块类型: {direct_result['block_types']}")

    if proxy_result:
        print(f"\n🟡 本项目代理API分析:")
        print(f"   总数据块数: {proxy_result['total_chunks']}")
        print(f"   总传输时间: {proxy_result['total_time_ms']:.2f}ms")
        if 'avg_interval_ms' in proxy_result:
            print(f"   平均间隔: {proxy_result['avg_interval_ms']:.2f}ms")
            print(f"   最大间隔: {proxy_result['max_interval_ms']:.2f}ms")
            print(f"   最小间隔: {proxy_result['min_interval_ms']:.2f}ms")
            print(f"   间隔标准差: {proxy_result['interval_std']:.2f}ms")
            print(f"   大间隔(>100ms): {len(proxy_result['large_intervals'])}个")
            print(f"   小间隔(<10ms): {len(proxy_result['small_intervals'])}个")
        print(f"   数据块类型: {proxy_result['block_types']}")

    # 对比分析
    if direct_result and proxy_result:
        print(f"\n🔍 关键差异分析:")

        # 数据块数量对比
        chunk_diff = proxy_result['total_chunks'] - direct_result['total_chunks']
        print(f"   数据块数量差异: {chunk_diff:+d} ({'代理更多' if chunk_diff > 0 else '代理更少'})")

        # 时间对比
        if 'avg_interval_ms' in direct_result and 'avg_interval_ms' in proxy_result:
            interval_diff = proxy_result['avg_interval_ms'] - direct_result['avg_interval_ms']
            print(f"   平均间隔差异: {interval_diff:+.2f}ms ({'代理更慢' if interval_diff > 0 else '代理更快'})")

            std_diff = proxy_result['interval_std'] - direct_result['interval_std']
            print(f"   间隔稳定性差异: {std_diff:+.2f}ms ({'代理更不稳定' if std_diff > 0 else '代理更稳定'})")

        # 数据块类型对比
        direct_types = set(direct_result['block_types'].keys())
        proxy_types = set(proxy_result['block_types'].keys())
        type_diff = proxy_types - direct_types
        if type_diff:
            print(f"   代理特有数据块类型: {type_diff}")

        # 闪烁问题可能的原因
        print(f"\n🚨 闪烁问题可能原因:")
        if 'large_intervals' in proxy_result and len(proxy_result['large_intervals']) > 2:
            print(f"   ⚠️ 代理API存在过多大间隔传输 ({len(proxy_result['large_intervals'])}个 >100ms)")
        if 'interval_std' in proxy_result and proxy_result['interval_std'] > 50:
            print(f"   ⚠️ 代理API传输间隔不稳定 (标准差: {proxy_result['interval_std']:.2f}ms)")
        if chunk_diff > 5:
            print(f"   ⚠️ 代理API生成了过多数据块 (多{chunk_diff}个)")
        if proxy_result['total_time_ms'] > direct_result.get('total_time_ms', 0) * 1.5:
            print(f"   ⚠️ 代理API传输时间过长")

def main():
    """主函数"""
    print("🔬 SSE数据流深度分析 - 定位Claude Code闪烁真正原因")
    print("="*60)

    # 测试代理API
    proxy_result = test_proxy_api()

    # 直接Anthropic API测试需要真实密钥，这里只做示例
    # 如果你有密钥，可以取消注释下面的代码
    # direct_result = test_direct_anthropic_api()
    direct_result = None

    # 对比分析
    compare_and_analyze(direct_result, proxy_result)

    # 如果只有代理API数据，也进行深入分析
    if proxy_result and not direct_result:
        print(f"\n🔬 代理API深入分析:")
        if 'large_intervals' in proxy_result and proxy_result['large_intervals']:
            print(f"   发现 {len(proxy_result['large_intervals'])} 个大间隔 (>100ms):")
            for i, interval in enumerate(proxy_result['large_intervals'][:5]):
                print(f"     第{i+1}个大间隔: {interval:.2f}ms")

        if 'interval_std' in proxy_result and proxy_result['interval_std'] > 30:
            print(f"   ⚠️ 传输间隔不稳定，标准差: {proxy_result['interval_std']:.2f}ms")
            print("   这可能是导致Claude Code界面闪烁的主要原因")

        print(f"\n💡 建议修复方向:")
        print("   1. 进一步优化数据流的时间间隔控制")
        print("   2. 实现更精确的定时刷新机制")
        print("   3. 添加数据流缓冲，确保平滑输出")
        print("   4. 考虑模拟直接API的传输模式")

if __name__ == "__main__":
    main()