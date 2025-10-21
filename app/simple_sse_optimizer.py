# -*- coding: utf-8 -*-
"""
简化的SSE优化器 - 用于调试
"""

import time
from .logger_setup import get_logger

class SimpleSSEOptimizer:
    """简化的SSE优化器"""

    def __init__(self):
        self.logger = get_logger('api_server')
        self.enabled = True  # 启用修复后的SSE生成器
        self.interval_ms = 50.0  # 50ms间隔

    def should_optimize(self, request_headers=None, user_agent=None):
        """判断是否应该优化"""
        if not self.enabled:
            self.logger.info("Simple SSE optimization disabled")
            return False
        else:
            self.logger.info("Simple SSE optimization ENABLED for Claude Code")

        user_agent = user_agent or (request_headers.get('User-Agent', '') if request_headers else '')

        # 更精确的Claude Code检测
        claude_indicators = [
            'claude-cli',
            'claude-code',
            'claude-code-router',
            'anthropic-claude-code'
        ]

        should_opt = any(indicator in user_agent.lower() for indicator in claude_indicators)
        self.logger.debug(f"SSE optimization check - User-Agent: {user_agent}, Should optimize: {should_opt}")

        return should_opt

    def optimize_stream(self, original_generator):
        """简单的流优化 - 只添加时间间隔"""
        if not self.enabled:
            return original_generator

        def optimized_generator():
            self.logger.debug("Starting simple SSE optimization")
            count = 0
            start_time = time.time()

            for data in original_generator:
                count += 1
                current_time = time.time()

                # 发送数据
                yield data

                # 如果不是最后一个，添加间隔
                if count < 10:  # 假设最多10个事件
                    sleep_time = self.interval_ms / 1000.0
                    time.sleep(sleep_time)
                    self.logger.debug(f"Event {count}: added {self.interval_ms}ms delay")

            total_time = time.time() - start_time
            self.logger.debug(f"Simple SSE optimization completed: {count} events in {total_time:.2f}s")

        return optimized_generator()

# 全局实例
_simple_optimizer = SimpleSSEOptimizer()

def get_simple_sse_optimizer():
    return _simple_optimizer