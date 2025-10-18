# -*- coding: utf-8 -*-
"""
增强错误处理和监控模块
用于提升系统稳定性和可观测性
"""

import time
import json
import threading
from datetime import datetime
from collections import defaultdict, deque
from .logger_setup import get_logger

class ErrorMonitor:
    """错误监控器，收集和分析错误信息"""

    def __init__(self):
        self.error_counts = defaultdict(int)
        self.error_history = deque(maxlen=1000)  # 保留最近1000个错误
        self.performance_metrics = deque(maxlen=500)  # 保留最近500个请求的性能数据
        self.lock = threading.Lock()
        self.logger = get_logger('error_monitor')

    def record_error(self, error_type, error_msg, context=None):
        """记录错误信息"""
        timestamp = datetime.now().isoformat()

        with self.lock:
            self.error_counts[error_type] += 1
            self.error_history.append({
                'timestamp': timestamp,
                'type': error_type,
                'message': error_msg,
                'context': context or {}
            })

        self.logger.error(f"错误记录 - 类型: {error_type}, 消息: {error_msg}, 上下文: {context}")

    def record_performance(self, duration, success=True, request_type=None):
        """记录性能指标"""
        timestamp = datetime.now().isoformat()

        with self.lock:
            self.performance_metrics.append({
                'timestamp': timestamp,
                'duration': duration,
                'success': success,
                'request_type': request_type
            })

        # 性能预警
        if duration > 5.0:  # 超过5秒的请求记录警告
            self.logger.warning(f"慢请求检测 - 耗时: {duration:.2f}s, 类型: {request_type}")

    def get_summary(self):
        """获取监控摘要"""
        with self.lock:
            if not self.performance_metrics:
                return {"status": "no_data"}

            recent_metrics = list(self.performance_metrics)[-50:]  # 最近50个请求
            total_requests = len(recent_metrics)
            successful_requests = sum(1 for m in recent_metrics if m['success'])

            if total_requests > 0:
                avg_duration = sum(m['duration'] for m in recent_metrics) / total_requests
                max_duration = max(m['duration'] for m in recent_metrics)
                min_duration = min(m['duration'] for m in recent_metrics)
            else:
                avg_duration = max_duration = min_duration = 0

            return {
                'timestamp': datetime.now().isoformat(),
                'requests_last_50': {
                    'total': total_requests,
                    'successful': successful_requests,
                    'failed': total_requests - successful_requests,
                    'success_rate': (successful_requests / total_requests) * 100 if total_requests > 0 else 0,
                    'avg_duration': avg_duration,
                    'max_duration': max_duration,
                    'min_duration': min_duration
                },
                'error_counts': dict(self.error_counts),
                'recent_errors': list(self.error_history)[-10:]  # 最近10个错误
            }

class EnhancedErrorHandler:
    """增强的错误处理器"""

    def __init__(self, monitor=None):
        self.monitor = monitor or ErrorMonitor()
        self.logger = get_logger('error_handler')

    def handle_stream_error(self, error, context=None):
        """处理流式错误"""
        error_type = 'stream_error'
        self.monitor.record_error(error_type, str(error), context)

        # 创建优雅的错误响应
        error_response = {
            'type': 'error',
            'error': {
                'type': 'stream_error',
                'message': '数据流处理异常，正在恢复...',
                'code': 'STREAM_ERROR',
                'timestamp': datetime.now().isoformat()
            }
        }
        return error_response

    def handle_encoding_error(self, error, context=None):
        """处理编码错误"""
        error_type = 'encoding_error'
        self.monitor.record_error(error_type, str(error), context)

        self.logger.warning(f"编码错误处理: {error}, 使用安全编码")
        return 'encoding_error_handled'

    def handle_timeout_error(self, error, context=None):
        """处理超时错误"""
        error_type = 'timeout_error'
        self.monitor.record_error(error_type, str(error), context)

        error_response = {
            'type': 'error',
            'error': {
                'type': 'timeout',
                'message': '请求超时，请重试',
                'code': 'TIMEOUT_ERROR',
                'timestamp': datetime.now().isoformat()
            }
        }
        return error_response

# 全局监控实例
global_monitor = ErrorMonitor()
global_error_handler = EnhancedErrorHandler(global_monitor)

def get_monitor():
    """获取全局监控实例"""
    return global_monitor

def get_error_handler():
    """获取全局错误处理器"""
    return global_error_handler