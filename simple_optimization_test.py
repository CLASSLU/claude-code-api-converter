#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版Claude Code优化测试
"""

import time
import json
import requests
import subprocess
import sys

def test_claude_optimization():
    """测试Claude Code优化效果"""
    print("Claude Code优化效果测试")
    print("=" * 40)

    # 启动服务
    print("启动优化后的服务...")
    proc = subprocess.Popen(
        ["python", "svc.py", "start", "-b"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    try:
        time.sleep(3)  # 等待服务启动

        # 测试1: Claude Code客户端
        print("\n1. 测试Claude Code客户端:")
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

        response = requests.post(
            "http://127.0.0.1:8080/v1/messages",
            headers=headers,
            json=data,
            stream=True,
            timeout=15
        )

        if response.status_code == 200:
            print("   请求成功")
            chunks = []
            start_time = time.time()

            for line in response.iter_lines(decode_unicode=True):
                if line and line.startswith('data:'):
                    current_time = time.time()
                    elapsed = (current_time - start_time) * 1000
                    chunks.append(elapsed)
                    if len(chunks) <= 5:
                        print(f"   块{len(chunks)}: {elapsed:6.2f}ms")
                    if '[DONE]' in line:
                        break

            if len(chunks) >= 2:
                intervals = [chunks[i] - chunks[i-1] for i in range(1, len(chunks))]
                avg_interval = sum(intervals) / len(intervals)

                print(f"   结果: {len(chunks)}个数据块, 平均间隔{avg_interval:.2f}ms")
                if 20 <= avg_interval <= 30:
                    print("   评分: 优秀间隔控制")
                else:
                    print(f"   评分: 需要改进 (目标25ms)")
        else:
            print(f"   请求失败: {response.status_code}")

        # 测试2: 常规客户端
        print("\n2. 测试常规客户端:")
        headers['User-Agent'] = 'Mozilla/5.0 (compatible; TestClient/1.0)'

        response = requests.post(
            "http://127.0.0.1:8080/v1/messages",
            headers=headers,
            json=data,
            stream=True,
            timeout=15
        )

        if response.status_code == 200:
            print("   请求成功")
            chunks = sum(1 for line in response.iter_lines(decode_unicode=True)
                        if line and line.startswith('data:'))
            print(f"   结果: {chunks}个数据块")
        else:
            print(f"   请求失败: {response.status_code}")

        # 测试3: 监控端点
        print("\n3. 测试监控端点:")
        try:
            response = requests.get("http://127.0.0.1:8080/monitoring/stats", timeout=5)
            if response.status_code == 200:
                stats = response.json()
                print("   监控端点正常")
                if 'requests_last_50' in stats:
                    req_stats = stats['requests_last_50']
                    print(f"   最近请求: {req_stats.get('total', 0)}个")
            else:
                print(f"   监控失败: {response.status_code}")
        except Exception as e:
            print(f"   监控异常: {str(e)[:30]}")

        print("\n测试完成！")
        print("优化要点:")
        print("- Claude Code客户端使用25ms目标间隔")
        print("- 智能缓冲和定时输出")
        print("- 检测并专门优化Claude Code请求")

    finally:
        # 停止服务
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except:
            proc.kill()

if __name__ == "__main__":
    test_claude_optimization()