"""
健康检查API蓝图
提供系统状态和健康监控
"""

import time
import psutil
from datetime import datetime
from flask import Blueprint, jsonify
from app.config import LiteConfig
from app.logger_setup import get_logger
from app.core.decorators import monitor_performance, rate_limit

# 创建蓝图
health_bp = Blueprint('health', __name__)

# 初始化服务
config = LiteConfig()
logger = get_logger('health_api', config.config.get('logging', {}))


@health_bp.route('/health', methods=['GET'])
@monitor_performance
@rate_limit(calls=200, period=60)
def health():
    """
    基础健康检查
    """
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '2.0.0',
        'service': 'claude-code-api-converter'
    }), 200


@health_bp.route('/health/detailed', methods=['GET'])
@monitor_performance
@rate_limit(calls=50, period=60)
def detailed_health():
    """
    详细健康检查，包括依赖项状态
    """
    try:
        # 检查上游API连通性
        openai_status = check_openai_connectivity()

        # 获取系统资源信息
        system_info = get_system_info()

        # 计算运行时间（如果有的话）
        uptime_seconds = time.time() - getattr(detailed_health, '_start_time', time.time())

        return jsonify({
            'status': 'healthy' if openai_status.get('accessible', False) else 'degraded',
            'timestamp': datetime.now().isoformat(),
            'version': '2.0.0',
            'service': 'claude-code-api-converter',
            'uptime_seconds': uptime_seconds,
            'dependencies': {
                'openai_api': openai_status
            },
            'system': system_info,
            'performance': {
                'memory_usage_mb': system_info.get('memory_usage_mb', 0),
                'cpu_usage_percent': system_info.get('cpu_usage_percent', 0)
            }
        }), 200

    except Exception as e:
        logger.error(f"Error in detailed health check: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }), 503


@health_bp.route('/health/ready', methods=['GET'])
@monitor_performance
@rate_limit(calls=100, period=60)
def readiness():
    """
    就绪检查 - 确认服务准备好接收请求
    """
    try:
        # 检查上游API是否可访问
        openai_status = check_openai_connectivity()

        if not openai_status.get('accessible', False):
            return jsonify({
                'status': 'not_ready',
                'reason': 'Upstream API not accessible',
                'timestamp': datetime.now().isoformat()
            }), 503

        return jsonify({
            'status': 'ready',
            'timestamp': datetime.now().isoformat()
        }), 200

    except Exception as e:
        return jsonify({
            'status': 'not_ready',
            'reason': str(e),
            'timestamp': datetime.now().isoformat()
        }), 503


@health_bp.route('/health/live', methods=['GET'])
@monitor_performance
@rate_limit(calls=100, period=60)
def liveness():
    """
    存活检查 - 确认服务进程正在运行
    """
    return jsonify({
        'status': 'alive',
        'timestamp': datetime.now().isoformat(),
        'pid': __import__('os').getpid()
    }), 200


def check_openai_connectivity():
    """
    检查上游OpenAI API的连通性
    """
    try:
        import requests

        headers = {
            'Authorization': f'Bearer {config.get_openai_config()["api_key"]}'
        }

        start_time = time.time()
        response = requests.get(
            f'{config.get_openai_config()["base_url"]}/models',
            headers=headers,
            timeout=5
        )
        response_time = (time.time() - start_time) * 1000

        return {
            'accessible': response.status_code == 200,
            'status_code': response.status_code,
            'response_time_ms': round(response_time, 2),
            'url': config.get_openai_config()["base_url"]
        }

    except Exception as e:
        return {
            'accessible': False,
            'error': str(e),
            'url': config.get_openai_config()["base_url"]
        }


def get_system_info():
    """
    获取系统资源信息
    """
    try:
        # 内存使用情况
        memory = psutil.virtual_memory()
        memory_usage_mb = round(memory.used / (1024 * 1024), 2)

        # CPU使用率
        cpu_percent = psutil.cpu_percent(interval=0.1)

        # 进程信息
        process = psutil.Process()
        process_memory_mb = round(process.memory_info().rss / (1024 * 1024), 2)

        return {
            'memory_usage_mb': memory_usage_mb,
            'memory_total_mb': round(memory.total / (1024 * 1024), 2),
            'memory_percent': memory.percent,
            'cpu_usage_percent': cpu_percent,
            'process_memory_mb': process_memory_mb,
            'process_pid': process.pid
        }

    except Exception as e:
        logger.warning(f"Failed to get system info: {str(e)}")
        return {
            'error': str(e)
        }


# 记录服务启动时间
detailed_health._start_time = time.time()