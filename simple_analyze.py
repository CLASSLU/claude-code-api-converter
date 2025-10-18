#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版SSE分析工具
"""

import time
import json
import requests

def analyze_proxy_sse():
    """分析代理API的SSE流"""
    headers = {'Content-Type': 'application/json'}

    data = {
        "model": "claude-3-5-haiku-20241022",
        "max_tokens": 300,
        "messages": [{"role": "user", "content": "简单回答：2+2等于多少？"}],
        "stream": True
    }

    print("开始分析代理API的SSE数据流...")

    try:
        response = requests.post(
            "http://127.0.0.1:8080/v1/messages",
            headers=headers,
            json=data,
            stream=True,
            timeout=15
        )

        if response.status_code != 200:
            print(f"请求失败: {response.status_code}")
            return

        chunks = []
        start_time = time.time()

        for line in response.iter_lines(decode_unicode=True):
            if line and line.startswith('data:'):
                current_time = time.time()
                elapsed = (current_time - start_time) * 1000

                chunks.append({
                    'elapsed_ms': elapsed,
                    'content': line[5:].strip(),
                    'raw': line
                })

                # 显示前10个数据块
                if len(chunks) <= 10:
                    print(f"块{len(chunks)}: {elapsed:6.2f}ms - {line[:60]}")

                if '[DONE]' in line:
                    break

        # 分析间隔
        if len(chunks) >= 2:
            intervals = []
            for i in range(1, len(chunks)):
                interval = chunks[i]['elapsed_ms'] - chunks[i-1]['elapsed_ms']
                intervals.append(interval)

            print(f"\n分析结果:")
            print(f"总数据块: {len(chunks)}")
            print(f"总时间: {chunks[-1]['elapsed_ms']:.2f}ms")
            print(f"平均间隔: {sum(intervals)/len(intervals):.2f}ms")
            print(f"最大间隔: {max(intervals):.2f}ms")
            print(f"最小间隔: {min(intervals):.2f}ms")

            # 检查异常间隔
            large_gaps = [i for i in intervals if i > 100]
            small_gaps = [i for i in intervals if i < 10]

            print(f"大间隔(>100ms): {len(large_gaps)}个")
            print(f"小间隔(<10ms): {len(small_gaps)}个")

            if large_gaps:
                print(f"大间隔详情: {large_gaps[:5]}")

            # 判断可能的闪烁原因
            print(f"\n闪烁问题诊断:")
            if len(large_gaps) > 1:
                print("WARNING: 发现多个大间隔，可能导致界面闪烁")
            if max(intervals) > 200:
                print(f"WARNING: 最大间隔{max(intervals):.2f}ms过长，影响平滑性")
            if len(small_gaps) > len(intervals) * 0.5:
                print("WARNING: 过多小间隔，可能造成数据轰炸")

    except Exception as e:
        print(f"分析异常: {e}")

if __name__ == "__main__":
    print("SSE数据流分析工具")
    print("=" * 40)
    analyze_proxy_sse()