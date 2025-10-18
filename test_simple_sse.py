#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SSE流式传输测试 - 简化版
"""

import time
import requests

def test_sse_streaming():
    """测试SSE流式传输的平滑性"""
    base_url = "http://127.0.0.1:8080"

    anthropic_request = {
        "model": "claude-3-5-haiku-20241022",
        "max_tokens": 1000,
        "messages": [
            {"role": "user", "content": "请简要回答1+1等于多少？"}
        ],
        "stream": True
    }

    print("开始SSE流式传输测试...")

    try:
        response = requests.post(
            f"{base_url}/v1/messages",
            json=anthropic_request,
            stream=True,
            timeout=30
        )

        if response.status_code != 200:
            print(f"请求失败: {response.status_code}")
            return False

        chunk_times = []
        chunk_count = 0
        start_time = time.time()

        print("接收流式数据...")

        for line in response.iter_lines(decode_unicode=True):
            if line and line.startswith('data:'):
                chunk_time = time.time()
                chunk_times.append(chunk_time)
                chunk_count += 1

                if chunk_count == 1:
                    print(f"首个数据块到达时间: {(chunk_time - start_time)*1000:.2f}ms")

                if '[DONE]' in line:
                    break

        end_time = time.time()
        total_duration = end_time - start_time

        print(f"\n流式传输分析:")
        print(f"   总数据块数: {chunk_count}")
        print(f"   总传输时间: {total_duration:.2f}s")

        if len(chunk_times) >= 2:
            intervals = [(chunk_times[i] - chunk_times[i-1]) * 1000
                        for i in range(1, min(10, len(chunk_times)))]

            if intervals:
                avg_interval = sum(intervals) / len(intervals)
                print(f"   平均间隔: {avg_interval:.2f}ms")

        return chunk_count > 0

    except Exception as e:
        print(f"测试异常: {e}")
        return False

def test_health_endpoint():
    """测试健康检查端点"""
    try:
        response = requests.get("http://127.0.0.1:8080/health", timeout=5)
        return response.status_code == 200
    except Exception:
        return False

def test_monitoring_endpoint():
    """测试监控端点"""
    try:
        response = requests.get("http://127.0.0.1:8080/monitoring/stats", timeout=5)
        return response.status_code == 200
    except Exception:
        return False

if __name__ == "__main__":
    print("Claude Code 界面闪烁修复测试")
    print("=" * 50)

    # 测试1: 健康检查
    health_ok = test_health_endpoint()
    print(f"健康检查: {'通过' if health_ok else '失败'}")

    if not health_ok:
        print("服务未运行，无法继续测试")
        exit(1)

    # 测试2: 监控端点
    monitor_ok = test_monitoring_endpoint()
    print(f"监控端点: {'通过' if monitor_ok else '失败'}")

    # 测试3: SSE流式传输
    sse_ok = test_sse_streaming()
    print(f"SSE流式传输: {'通过' if sse_ok else '失败'}")

    print("\n总结:")
    tests_passed = sum([health_ok, monitor_ok, sse_ok])
    print(f"测试通过: {tests_passed}/3")

    if tests_passed == 3:
        print("所有测试通过！")
    else:
        print("部分测试失败")