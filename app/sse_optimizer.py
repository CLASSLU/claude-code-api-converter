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
        self.logger = get_logger('sse_optimizer')
        self.enable_optimization = True
        self.target_interval = 30.0  # 目标间隔30ms

    def should_optimize(self, request_headers=None, user_agent=None):
        """判断是否应该优化"""
        if not self.enable_optimization:
            return False

        # 检测Claude Code客户端
        user_agent = user_agent or (request_headers.get('User-Agent', '') if request_headers else '')

        claude_indicators = [
            'claude-code',
            'claude-code-router',
            'anthropic-claude-code'
        ]

        return any(indicator.lower() in user_agent.lower() for indicator in claude_indicators)

    def create_optimized_generator(self, original_generator):
        """创建优化的生成器"""
        if not self.enable_optimization:
            return original_generator

        def optimized_generator():
            buffer_queue = Queue()
            last_emit_time = 0

            def buffer_worker():
                """缓冲工作线程"""
                for data in original_generator:
                    buffer_queue.put(data)
                buffer_queue.put(None)  # 结束标志

            # 启动缓冲线程
            buffer_thread = threading.Thread(target=buffer_worker, daemon=True)
            buffer_thread.start()

            # 优化输出
            while True:
                try:
                    data = buffer_queue.get(timeout=0.1)
                    if data is None:
                        break

                    current_time = time.time()
                    if last_emit_time > 0:
                        # 计算应该等待的时间
                        elapsed = (current_time - last_emit_time) * 1000
                        if elapsed < self.target_interval:
                            time.sleep((self.target_interval - elapsed) / 1000.0)

                    yield data
                    last_emit_time = time.time()

                except:
                    continue

        return optimized_generator()

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