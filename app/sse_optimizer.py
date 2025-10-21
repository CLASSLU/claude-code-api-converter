# -*- coding: utf-8 -*-
"""
SSE流式传输优化器
专门用于解决Claude Code界面闪烁问题
保持向后兼容，不影响现有功能包括工具调用
"""

import time
import json
import threading
from queue import Queue
from datetime import datetime
from .logger_setup import get_logger

class SSEOptimizer:
    """SSE流式传输优化器"""

    def __init__(self):
        # 使用与主服务器相同的logger配置，确保DEBUG日志能正确输出
        self.logger = get_logger('api_server')  # 改为使用api_server的logger
        self.enable_optimization = False  # 临时禁用优化进行测试
        self.target_interval = 30.0  # 改为30ms目标间隔，提高响应速度

    def should_optimize(self, request_headers=None, user_agent=None):
        """判断是否应该优化"""
        if not self.enable_optimization:
            self.logger.debug("SSE optimization disabled")
            return False

        # 检测Claude Code客户端
        user_agent = user_agent or (request_headers.get('User-Agent', '') if request_headers else '')

        claude_indicators = [
            'claude-code',
            'claude-code-router',
            'anthropic-claude-code',
            'claude-cli'  # 添加真实的Claude Code CLI客户端标识
        ]

        should_opt = any(indicator.lower() in user_agent.lower() for indicator in claude_indicators)
        self.logger.debug(f"SSE optimization check - User-Agent: {user_agent}, Should optimize: {should_opt}")
        return should_opt

    def create_optimized_generator(self, original_generator):
        """创建智能优化的生成器 - 针对工具调用的特殊优化"""
        if not self.enable_optimization:
            self.logger.debug("SSE optimization disabled, returning original generator")
            return original_generator

        def optimized_generator():
            event_buffer = []
            last_emit_time = 0
            total_events = 0
            buffer_start_time = time.time()

            # 智能检测变量
            tool_call_detected = False
            tool_content_buffer = ""
            normal_text_events = []

            # 分层优化策略
            NORMAL_MODE_INTERVAL = 30.0      # 普通文本：30ms
            TOOL_CALL_INTERVAL = 100.0      # 工具调用：100ms（更温和）
            MAX_BUFFER_TIME_NORMAL = 0.3     # 普通模式：0.3秒
            MAX_BUFFER_TIME_TOOL = 0.8       # 工具调用：0.8秒（减少闪烁）

            current_interval = NORMAL_MODE_INTERVAL
            current_max_buffer = MAX_BUFFER_TIME_NORMAL

            self.logger.debug("Starting超级智能SSE generator - 工具调用优化模式")

            for data in original_generator:
                current_time = time.time()
                total_events += 1

                # 检测是否为工具调用相关事件
                is_tool_event = self._detect_tool_event(data)
                if is_tool_event:
                    tool_call_detected = True
                    current_interval = TOOL_CALL_INTERVAL
                    current_max_buffer = MAX_BUFFER_TIME_TOOL
                    self.logger.debug("检测到工具调用，切换到工具优化模式")

                # 智能缓冲策略
                if tool_call_detected and is_tool_event:
                    # 工具调用期间：累积更多数据，减少发送频率
                    event_buffer.append(data)
                else:
                    # 普通文本：正常处理
                    if tool_call_detected and event_buffer:
                        # 工具调用结束，立即刷新缓冲区
                        self._flush_buffer_smoothly(event_buffer, current_interval)
                        event_buffer.clear()
                        tool_call_detected = False
                        current_interval = NORMAL_MODE_INTERVAL
                        current_max_buffer = MAX_BUFFER_TIME_NORMAL

                    event_buffer.append(data)

                # 检查是否需要发送
                buffer_time = current_time - buffer_start_time
                should_emit = (
                    buffer_time >= current_max_buffer or  # 时间到
                    len(event_buffer) >= 5 or  # 缓冲足够多
                    (not tool_call_detected and len(event_buffer) >= 1)  # 普通模式立即发送
                )

                if should_emit and event_buffer:
                    self._flush_buffer_smoothly(event_buffer, current_interval)
                    event_buffer.clear()
                    buffer_start_time = time.time()

            # 最终刷新
            if event_buffer:
                self._flush_buffer_smoothly(event_buffer, current_interval)

            self.logger.debug(f"超级智能优化完成：处理 {total_events} 个事件")

        return optimized_generator()

    def _detect_tool_event(self, data):
        """检测是否为工具调用相关事件"""
        if not data or not isinstance(data, str):
            return False

        # 检测工具调用特征
        tool_indicators = [
            'tool_use',
            'tool_result',
            'tool_call',
            '"type": "tool_use"',
            '"type": "tool_result"',
            'function_call',
            'arguments',
            'Task tool',
            'agent tool'
        ]

        data_lower = data.lower()
        return any(indicator.lower() in data_lower for indicator in tool_indicators)

    def _flush_buffer_smoothly(self, buffer, interval):
        """平滑刷新缓冲区"""
        if not buffer:
            return

        self.logger.debug(f"平滑刷新缓冲区: {len(buffer)} 个事件, 间隔 {interval}ms")

        last_emit_time = time.time()
        for i, data in enumerate(buffer):
            current_time = time.time()
            if i == 0:
                # 第一个立即发送
                yield data
                last_emit_time = current_time
            else:
                # 后续按间隔发送
                elapsed = (current_time - last_emit_time) * 1000
                if elapsed < interval:
                    time.sleep(max(0, (interval - elapsed) / 1000.0))
                yield data
                last_emit_time = time.time()

    def smooth_sse_stream(self, upstream_data):
        """平滑SSE流式传输"""
        if not self.enable_optimization:
            return upstream_data

        smoothed_data = []
        current_time = time.time()

        for data in upstream_data:
            smoothed_data.append(data)
            current_time = time.time()

        return smoothed_data

# 全局优化器实例
_global_optimizer = SSEOptimizer()

def get_sse_optimizer():
    """获取SSE优化器实例"""
    return _global_optimizer