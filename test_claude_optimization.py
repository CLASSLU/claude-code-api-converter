#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Claude Code优化效果测试
"""

import time
import json
import requests

def test_claude_code_detection():
    """测试Claude Code客户端检测"""
    print("测试Claude Code客户端检测...")

    # 模拟Claude Code请求
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'claude-code-router/1.0.0'
    }

    data = {
        "model": "claude-3-haiku-20240307",
        "max_tokens": 100,
        "messages": [{"role": "user", "content": "Hi"}],
        "stream": True
    }

    try:
        response = requests.post(
            "http://127.0.0.1:8080/v1/messages",
            headers=headers,
            json=data,
            stream=True,
            timeout=15
        )

        if response.status_code == 200:
            print("✅ Claude Code模式请求成功")

            # 分析SSE流
            chunks = []
            start_time = time.time()

            for line in response.iter_lines(decode_unicode=True):
                if line and line.startswith('data:'):
                    current_time = time.time()
                    elapsed = (current_time - start_time) * 1000
                    chunks.append({
                        'elapsed': elapsed,
                        'content': line
                    })
                    print(f"  {elapsed:6.2f}ms: {line[:60]}")

                    if '[DONE]' in line:
                        break

            # 分析间隔
            if len(chunks) >= 2:
                intervals = []
                for i in range(1, len(chunks)):
                    interval = chunks[i]['elapsed'] - chunks[i-1]['elapsed']
                    intervals.append(interval)

                avg_interval = sum(intervals) / len(intervals) if intervals else 0
                max_interval = max(intervals) if intervals else 0
                min_interval = min(intervals) if intervals else 0

                print(f"\nClaude Code优化效果:")
                print(f"  数据块数: {len(chunks)}")
                print(f"  平均间隔: {avg_interval:.2f}ms (目标: 25ms)")
                print(f"  最大间隔: {max_interval:.2f}ms")
                print(f"  最小间隔: {min_interval:.2f}ms")

                # 评估优化效果
                if 20 <= avg_interval <= 30:
                    print("✅ 传输间隔符合预期")
                elif 10 <= avg_interval <= 40:
                    print("⚠️ 传输间隔基本正常")
                else:
                    print("❌ 传输间隔需要进一步优化")

                if max_interval - min_interval < 50:
                    print("✅ 传输稳定性良好")
                else:
                    print("⚠️ 传输稳定性有待改进")

        else:
            print(f"❌ 请求失败: {response.status_code}")

    except Exception as e:
        print(f"❌ 测试异常: {e}")

def test_regular_client():
    """测试常规客户端（非Claude Code）"""
    print("\n测试常规客户端...")

    # 常规客户端请求
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    data = {
        "model": "claude-3-haiku-20240307",
        "max_tokens": 100,
        "messages": [{"role": "user", "content": "Hi"}],
        "stream": True
    }

    try:
        response = requests.post(
            "http://127.0.0.1:8080/v1/messages",
            headers=headers,
            json=data,
            stream=True,
            timeout=15
        )

        if response.status_code == 200:
            print("✅ 常规客户端请求成功")
            chunks = 0
            for line in response.iter_lines(decode_unicode=True):
                if line and line.startswith('data:'):
                    chunks += 1
                    if '[DONE]' in line:
                        break

            print(f"  接收到 {chunks} 个数据块")
        else:
            print(f"❌ 请求失败: {response.status_code}")

    except Exception as e:
        print(f"❌ 测试异常: {e}")

def test_monitoring_endpoint():
    """测试监控端点"""
    print("\n测试监控端点...")

    try:
        response = requests.get("http://127.0.0.1:8080/monitoring/stats", timeout=5)
        if response.status_code == 200:
            stats = response.json()
            print("✅ 监控端点正常")
            if 'requests_last_50' in stats:
                req_stats = stats['requests_last_50']
                print(f"  最近请求数: {req_stats.get('total', 0)}")
                print(f"  成功率: {req_stats.get('success_rate', 0):.1f}%")
                print(f"  平均耗时: {req_stats.get('avg_duration', 0):.2f}ms")
        else:
            print(f"❌ 监控端点失败: {response.status_code}")

    except Exception as e:
        print(f"❌ 监控测试异常: {e}")

def main():
    """主测试函数"""
    print("Claude Code专用优化效果测试")
    print("=" * 50)

    # 启动服务
    print("启动优化后的服务...")
    import subprocess
    import signal
    import os

    # 启动服务进程
    proc = subprocess.Popen(
        ["python", "svc.py", "start", "-b"],
        cwd=".",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    try:
        # 等待服务启动
        time.sleep(3)

        # 运行测试
        test_claude_code_detection()
        test_regular_client()
        test_monitoring_endpoint()

        print("\n" + "=" * 50)
        print("测试完成！")
        print("如果Claude Code模式下的传输间隔接近25ms且稳定，说明优化有效。")

    finally:
        # 清理服务
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except:
            proc.kill()

if __name__ == "__main__":
    main()