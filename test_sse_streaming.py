#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SSE流式传输测试 - 验证平滑流式处理
专门测试Claude Code界面闪烁问题的修复效果
"""

import time
import json
import requests
import threading
from queue import Queue

def test_sse_streaming_smoothness():
    """测试SSE流式传输的平滑性"""
    base_url = "http://127.0.0.1:8080"

    # 模拟Claude Code请求
    anthropic_request = {
        "model": "claude-3-5-haiku-20241022",
        "max_tokens": 1000,
        "messages": [
            {"role": "user", "content": "请详细解释SSE流式传输的工作原理，包括数据格式、连接管理和错误处理机制。"}
        ],
        "stream": True
    }

    print("🧪 开始SSE流式传输平滑性测试...")

    try:
        response = requests.post(
            f"{base_url}/v1/messages",
            json=anthropic_request,
            stream=True,
            timeout=30
        )

        if response.status_code != 200:
            print(f"❌ 请求失败: {response.status_code}")
            return False

        chunk_times = []
        chunk_count = 0
        start_time = time.time()

        print("📡 接收流式数据...")

        for line in response.iter_lines(decode_unicode=True):
            if line and line.startswith('data:'):
                chunk_time = time.time()
                chunk_times.append(chunk_time)
                chunk_count += 1

                if chunk_count == 1:
                    print(f"⏱️ 首个数据块到达时间: {(chunk_time - start_time)*1000:.2f}ms")

                # 检查数据间隔
                if len(chunk_times) >= 2:
                    interval = chunk_times[-1] - chunk_times[-2] * 1000
                    if chunk_count <= 10:  # 只显示前10个间隔
                        print(f"  数据块 {chunk_count}: 间隔 {interval:.2f}ms")

                if '[DONE]' in line:
                    break

        end_time = time.time()
        total_duration = end_time - start_time

        # 分析数据流平滑性
        if len(chunk_times) >= 2:
            intervals = [(chunk_times[i] - chunk_times[i-1]) * 1000
                        for i in range(1, min(20, len(chunk_times)))]  # 分析前20个间隔

            avg_interval = sum(intervals) / len(intervals)
            max_interval = max(intervals)
            min_interval = min(intervals)

            print(f"\n📊 流式传输分析:")
            print(f"   总数据块数: {chunk_count}")
            print(f"   总传输时间: {total_duration:.2f}s")
            print(f"   平均间隔: {avg_interval:.2f}ms")
            print(f"   最大间隔: {max_interval:.2f}ms")
            print(f"   最小间隔: {min_interval:.2f}ms")

            # 评估平滑性
            if max_interval - min_interval < 100:  # 间隔差异小于100ms
                print("✅ 流式传输平滑性: 良好")
                return True
            elif max_interval - min_interval < 200:
                print("⚠️ 流式传输平滑性: 一般")
                return True
            else:
                print("❌ 流式传输平滑性: 需要改进")
                return False

        print("❌ 数据不足，无法评估")
        return False

    except Exception as e:
        print(f"❌ 测试异常: {e}")
        return False

def test_multiple_concurrent_requests():
    """测试并发请求处理"""
    base_url = "http://127.0.0.1:8080"

    def make_request(request_id):
        """单个请求"""
        try:
            anthropic_request = {
                "model": "claude-3-5-haiku-20241022",
                "max_tokens": 500,
                "messages": [{"role": "user", "content": f"并发请求 #{request_id}: 简要回答"}],
                "stream": True
            }

            response = requests.post(
                f"{base_url}/v1/messages",
                json=anthropic_request,
                stream=True,
                timeout=15
            )

            if response.status_code == 200:
                chunks = 0
                for line in response.iter_lines():
                    if line and line.startswith('data:'):
                        chunks += 1
                        if '[DONE]' in line:
                            break

                return f"请求#{request_id}: {chunks}个数据块 ✅"
            else:
                return f"请求#{request_id}: 失败 ❌"

        except Exception as e:
            return f"请求#{request_id}: 异常 {str(e)[:50]} ❌"

    print("\n🔄 开始并发请求测试 (3个并发)...")

    threads = []
    results = []

    for i in range(3):
        thread = threading.Thread(target=lambda rq=i: results.append(make_request(rq+1)))
        threads.append(thread)
        thread.start()

    # 启动并发请求
    start_time = time.time()
    for thread in threads:
        thread.join()

    total_time = time.time() - start_time

    print(f"   并发完成时间: {total_time:.2f}s")
    for result in results:
        print(f"   {result}")

    success_count = sum(1 for r in results if "✅" in r)
    return success_count == 3

def main():
    """主测试函数"""
    print("🚀 Claude Code 界面闪烁修复测试")
    print("=" * 50)

    # 检查服务是否运行
    try:
        response = requests.get("http://127.0.0.1:8080/health", timeout=5)
        if response.status_code != 200:
            print("❌ 服务未运行或不健康")
            return
    except Exception:
        print("❌ 无法连接到服务，请确保服务器在 http://127.0.0.1:8080 运行")
        return

    print("✅ 服务连接正常")

    # 运行测试
    test_results = []

    # 测试1: SSE流式平滑性
    result1 = test_sse_streaming_smoothness()
    test_results.append(("SSE流式平滑性", result1))

    # 测试2: 并发请求处理
    result2 = test_multiple_concurrent_requests()
    test_results.append(("并发请求处理", result2))

    # 测试3: 监控端点
    try:
        response = requests.get("http://127.0.0.1:8080/monitoring/stats", timeout=5)
        result3 = response.status_code == 200
        test_results.append(("监控端点", result3))
    except Exception:
        test_results.append(("监控端点", False))

    # 总结
    print("\n" + "=" * 50)
    print("📋 测试结果总结:")

    passed = 0
    total = len(test_results)

    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   {test_name}: {status}")
        if result:
            passed += 1

    print(f"\n🎯 总体结果: {passed}/{total} 测试通过")

    if passed == total:
        print("🎉 所有测试通过！Claude Code 界面闪烁问题应该已修复")
    else:
        print("⚠️ 部分测试失败，需要进一步调试")

if __name__ == "__main__":
    main()