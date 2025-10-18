#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高级SSE分析 - 定位真正闪烁根因
"""

import time
import json
import requests
import threading
from collections import defaultdict

def capture_detailed_sse_stream():
    """捕获详细的SSE流数据"""
    headers = {'Content-Type': 'application/json'}

    # 使用一个简单的测试请求
    data = {
        "model": "claude-3-haiku-20240307",  # 使用配置中的模型
        "max_tokens": 200,
        "messages": [{"role": "user", "content": "Hi"}],
        "stream": True
    }

    print("详细捕获SSE数据流...")
    print("-" * 60)

    events = []
    start_time = time.time()

    try:
        response = requests.post(
            "http://127.0.0.1:8080/v1/messages",
            headers=headers,
            json=data,
            stream=True,
            timeout=20
        )

        if response.status_code != 200:
            print(f"API请求失败: {response.status_code}")
            return events

        for i, line in enumerate(response.iter_lines(decode_unicode=True)):
            current_time = time.time()
            elapsed = (current_time - start_time) * 1000

            if line:
                # 详细记录每一条数据
                event = {
                    'index': i + 1,
                    'timestamp': current_time,
                    'elapsed_ms': elapsed,
                    'raw_line': line,
                    'is_data': line.startswith('data:'),
                    'content': line[5:].strip() if line.startswith('data:') else line,
                    'size_bytes': len(line.encode('utf-8'))
                }
                events.append(event)

                # 逐条打印详细信息
                print(f"{event['index']:3d} | {event['elapsed_ms']:6.2f}ms | {event['size_bytes']:3d}B | {line}")

                if '[DONE]' in line:
                    break

    except Exception as e:
        print(f"捕获异常: {e}")

    return events

def analyze_timing_patterns(events):
    """分析时间模式"""
    if len(events) < 2:
        print("数据不足，无法分析时间模式")
        return

    print("\n" + "=" * 60)
    print("时间模式分析")
    print("=" * 60)

    # 计算相邻事件的间隔
    intervals = []
    for i in range(1, len(events)):
        interval = events[i]['elapsed_ms'] - events[i-1]['elapsed_ms']
        intervals.append(interval)

    if intervals:
        # 基本统计
        avg_interval = sum(intervals) / len(intervals)
        max_interval = max(intervals)
        min_interval = min(intervals)

        print(f"总事件数: {len(events)}")
        print(f"间隔统计:")
        print(f"  平均: {avg_interval:.2f}ms")
        print(f"  最大: {max_interval:.2f}ms")
        print(f"  最小: {min_interval:.2f}ms")
        print(f"  标准差: {calculate_std(intervals):.2f}ms")

        # 分段分析
        print(f"\n间隔分段分析:")
        segments = [
            (0, 5, "瞬时"),
            (5, 20, "快速"),
            (20, 50, "正常"),
            (50, 100, "较慢"),
            (100, float('inf'), "异常慢")
        ]

        for min_val, max_val, label in segments:
            count = sum(1 for x in intervals if min_val <= x < max_val)
            percentage = count / len(intervals) * 100
            print(f"  {label}[{min_val}-{max_val if max_val != float('inf') else '∞'}ms): {count}个 ({percentage:.1f}%)")

        # 识别问题模式
        print(f"\n问题检测:")

        # 连续小块检测（数据轰炸）
        consecutive_small = find_consecutive_small(intervals, threshold=10, min_consecutive=3)
        if consecutive_small:
            print(f"  🚨 连续小块(数据轰炸模式): 找到{len(consecutive_small)}组")
            for start_pos, length in consecutive_small[:3]:
                print(f"    位置{start_pos}-{start_pos+length-1}: {length}个连续小块")

        # 大间隔检测（卡顿模式）
        large_intervals = [(i, interval) for i, interval in enumerate(intervals) if interval > 100]
        if large_intervals:
            print(f"  🚨 大间隔(卡顿模式): {len(large_intervals)}个")
            for pos, interval in large_intervals[:5]:
                print(f"    位置{pos}: {interval:.2f}ms")

        # 间隔突变检测（不稳定传输）
        jumps = detect_interval_jumps(intervals, threshold=5.0)
        if jumps:
            print(f"  🚨 间隔突变(不稳定传输): {len(jumps)}次")

    return intervals

def analyze_content_patterns(events):
    """分析内容模式"""
    print(f"\n" + "=" * 60)
    print("内容模式分析")
    print("=" * 60)

    content_types = defaultdict(int)
    message_start_events = []
    content_block_events = []
    delta_events = []

    for event in events:
        if event['is_data']:
            content = event['content']
            if content == '[DONE]':
                content_types['DONE'] += 1
            else:
                try:
                    data = json.loads(content)
                    msg_type = data.get('type', 'unknown')
                    content_types[msg_type] += 1

                    if msg_type == 'message_start':
                        message_start_events.append(event)
                    elif 'content_block' in msg_type:
                        content_block_events.append(event)
                    elif 'delta' in msg_type:
                        delta_events.append(event)

                except json.JSONDecodeError:
                    content_types['invalid_json'] += 1

    print(f"数据块类型统计:")
    for content_type, count in sorted(content_types.items()):
        print(f"  {content_type}: {count}")

    # 分析时间分布
    if delta_events:
        print(f"\n内容增量分析:")
        delta_intervals = []
        for i in range(1, len(delta_events)):
            interval = delta_events[i]['elapsed_ms'] - delta_events[i-1]['elapsed_ms']
            delta_intervals.append(interval)

        if delta_intervals:
            print(f"  平均增量间隔: {sum(delta_intervals)/len(delta_intervals):.2f}ms")
            print(f"  增量间隔标准差: {calculate_std(delta_intervals):.2f}ms")

def calculate_std(values):
    """计算标准差"""
    if not values:
        return 0
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return variance ** 0.5

def find_consecutive_small(intervals, threshold=10, min_consecutive=3):
    """查找连续的小间隔"""
    consecutive = []
    current_start = None
    current_length = 0

    for i, interval in enumerate(intervals):
        if interval < threshold:
            if current_start is None:
                current_start = i
            current_length += 1
        else:
            if current_length >= min_consecutive:
                consecutive.append((current_start, current_length))
            current_start = None
            current_length = 0

    # 检查最后一组
    if current_length >= min_consecutive:
        consecutive.append((current_start, current_length))

    return consecutive

def detect_interval_jumps(intervals, threshold=5.0):
    """检测间隔突变"""
    jumps = []
    for i in range(1, len(intervals)):
        if intervals[i-1] > 0:
            ratio = intervals[i] / intervals[i-1]
            if ratio > threshold or ratio < 1/threshold:
                jumps.append((i-1, intervals[i-1], intervals[i], ratio))
    return jumps

def diagnose_flicker_cause(events, intervals):
    """诊断闪烁原因"""
    print(f"\n" + "=" * 60)
    print("闪烁问题诊断")
    print("=" * 60)

    issues = []

    # 检查数据轰炸模式
    consecutive_small = find_consecutive_small(intervals, threshold=5, min_consecutive=5)
    if consecutive_small:
        issues.append("数据轰炸模式: 连续多个小间隔(5ms以下)的快速数据传输")

    # 检查卡顿模式
    large_intervals = [i for i in intervals if i > 150]
    if len(large_intervals) > 2:
        issues.append("卡顿模式: 多个超过150ms的大间隔")

    # 检查不稳定传输
    if intervals and calculate_std(intervals) > 50:
        issues.append("不稳定传输: 间隔标准差过大，传输节奏不均匀")

    # 检查数据块数量
    if len(events) > 50:
        issues.append("数据块过多: 生成的数据块数量过多，可能导致处理负担")

    # 检查总传输时间
    if events and events[-1]['elapsed_ms'] > 5000:
        issues.append("传输时间过长: 总传输时间超过5秒")

    if issues:
        print("🚨 发现的问题:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
    else:
        print("✅ 未发现明显的闪烁问题")

    # 给出修复建议
    print(f"\n💡 修复建议:")
    if consecutive_small:
        print("  - 实现更严格的缓冲控制，避免数据轰炸")
        print("  - 增加最小间隔限制，确保平滑输出")
    if large_intervals:
        print("  - 优化上游API调用，减少大间隔")
        print("  - 实现心跳机制，保持连接活跃")
    if intervals and calculate_std(intervals) > 50:
        print("  - 实现定时器控制，确保均匀传输")
        print("  - 添加自适应缓冲，根据传输速度调整")

def main():
    """主函数"""
    print("高级SSE分析 - 定位闪烁真正根因")
    print("=" * 60)

    # 捕获详细数据
    events = capture_detailed_sse_stream()

    if not events:
        print("无法获取SSE数据，请检查服务状态")
        return

    # 分析时间模式
    intervals = analyze_timing_patterns(events)

    # 分析内容模式
    analyze_content_patterns(events)

    # 诊断闪烁原因
    diagnose_flicker_cause(events, intervals)

if __name__ == "__main__":
    main()