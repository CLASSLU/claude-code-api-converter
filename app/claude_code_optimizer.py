# -*- coding: utf-8 -*-
"""
Claude Code 专用优化器
针对Claude Code界面的特殊需求进行优化
"""

import time
import json
import threading
from queue import Queue, Empty
from datetime import datetime
from .logger_setup import get_logger

class ClaudeCodeOptimizer:
    """Claude Code专用优化器"""

    def __init__(self):
        self.logger = get_logger('claude_optimizer')
        self.is_claude_code = False
        self.optimization_enabled = True

    def detect_claude_code(self, request_headers, user_agent=None):
        """检测是否为Claude Code客户端"""
        user_agent = user_agent or request_headers.get('User-Agent', '')

        # Claude Code的特征标识
        claude_code_indicators = [
            'claude-code',
            'claude-code-router',
            'anthropic-claude-code',
            'claude/desktop'
        ]

        self.is_claude_code = any(indicator.lower() in user_agent.lower()
                                 for indicator in claude_code_indicators)

        if self.is_claude_code:
            self.logger.info(f"检测到Claude Code客户端: {user_agent}")

        return self.is_claude_code

    def should_optimize_response(self, request_headers=None):
        """判断是否应该进行优化"""
        if not self.optimization_enabled:
            return False

        if request_headers:
            self.detect_claude_code(request_headers)

        return self.is_claude_code

class IntelligentSSEStreamer:
    """智能SSE流式传输器 - Claude Code专用版本"""

    def __init__(self, claude_optimizer=None, target_interval=25.0):
        self.claude_optimizer = claude_optimizer or ClaudeCodeOptimizer()
        self.target_interval = target_interval  # 目标间隔25ms，模拟真实API
        self.buffer = []
        self.queue = Queue()
        self.last_flush_time = 0
        self.is_running = False
        self.thread = None
        self.logger = get_logger('intelligent_sse')

    def add_data(self, data):
        """添加数据到智能缓冲器"""
        if not self.claude_optimizer.should_optimize_response():
            # 非Claude Code客户端，直接输出
            self.queue.put(data)
            return

        # Claude Code客户端，使用智能缓冲
        self.buffer.append(data)

        # 立即输出结束标志
        if '[DONE]' in data:
            self._flush_buffer()
            self.queue.put(data)
            return

        # 智能刷新策略
        current_time = time.time()
        should_flush = (
            len(self.buffer) >= 1 or  # 单个数据块立即刷新，避免延迟
            current_time - self.last_flush_time >= self.target_interval / 1000.0
        )

        if should_flush:
            self._flush_buffer()
            self.last_flush_time = current_time

    def _flush_buffer(self):
        """刷新缓冲区"""
        if self.buffer:
            for data in self.buffer:
                self.queue.put(data)
            self.buffer.clear()

    def get_generator(self):
        """获取生成器"""
        if not self.claude_optimizer.is_claude_code:
            # 非Claude Code客户端，简单直接输出
            while True:
                try:
                    data = self.queue.get(timeout=0.1)
                    if data is None:
                        break
                    yield data
                except Empty:
                    continue
        else:
            # Claude Code客户端，使用定时输出线程
            return self._get_timed_generator()

    def _get_timed_generator(self):
        """Claude Code专用的定时生成器"""
        self.is_running = True

        def timer_thread():
            """定时器线程，确保平滑输出"""
            while self.is_running:
                time.sleep(self.target_interval / 1000.0)
                self._flush_buffer()

        # 启动定时器线程
        self.thread = threading.Thread(target=timer_thread, daemon=True)
        self.thread.start()

        try:
            while True:
                try:
                    data = self.queue.get(timeout=0.1)
                    if data is None:
                        break
                    yield data
                except Empty:
                    # 超时继续，确保定时器能正常工作
                    continue
        finally:
            self.is_running = False

class ClaudeCodeResponseOptimizer:
    """Claude Code响应优化器"""

    def __init__(self):
        self.logger = get_logger('response_optimizer')
        self.claude_optimizer = ClaudeCodeOptimizer()

    def optimize_response_headers(self, original_headers):
        """优化响应头"""
        if not self.claude_optimizer.is_claude_code:
            return original_headers

        # Claude Code专用响应头优化
        optimized = dict(original_headers)
        optimized.update({
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
            'X-Accel-Buffering': 'no'  # 禁用nginx缓冲
        })

        return optimized

    def create_optimized_sse_streamer(self):
        """创建优化的SSE流式传输器"""
        return IntelligentSSEStreamer(
            claude_optimizer=self.claude_optimizer,
            target_interval=25.0  # 25ms，接近真实API的传输间隔
        )

    def optimize_data_chunk(self, data, chunk_type):
        """优化数据块"""
        if not self.claude_optimizer.is_claude_code:
            return data

        # Claude Code专用数据优化
        try:
            if chunk_type == 'message_start':
                # 确保message_start立即发送
                return data
            elif chunk_type == 'content_block_delta':
                # 内容增量可以适当缓冲
                return data
            elif chunk_type == 'message_stop':
                # 确保结束标志立即发送
                return data
            else:
                return data
        except Exception as e:
            self.logger.warning(f"数据优化失败: {e}")
            return data

# 全局优化器实例
global_optimizer = ClaudeCodeResponseOptimizer()

def get_claude_code_optimizer():
    """获取Claude Code优化器实例"""
    return global_optimizer

# 向后兼容的别名
ClaudeCodeOptimizer = ClaudeCodeResponseOptimizer