"""
Flask应用工厂模式
提供可扩展的应用初始化机制
"""

import sys
import os
from flask import Flask
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import LiteConfig
from app.logger_setup import get_logger
from app.core.exceptions import APIServiceError
from app.core.decorators import monitor_performance
from app.api import api_bp


def create_app(config_object=None):
    """
    Flask应用工厂函数

    Args:
        config_object: 配置对象类，默认使用LiteConfig

    Returns:
        Flask应用实例
    """
    app = Flask(__name__)

    # 加载配置
    config_class = config_object or LiteConfig
    app.config.from_object(config_class().get_flask_config())

    # 初始化扩展和服务
    init_app(app)

    # 注册蓝图
    register_blueprints(app)

    # 注册错误处理器
    register_error_handlers(app)

    # 注册before/after请求钩子
    register_hooks(app)

    return app


def init_app(app):
    """初始化应用服务和扩展"""

    # 设置日志系统
    logger_config = app.config.get('LOGGING_CONFIG', {})
    logger = get_logger('api_server', logger_config)
    app.logger = logger
    logger.info(f"App factory initializing on {app.config.get('SERVER_HOST', '0.0.0.0')}:{app.config.get('SERVER_PORT', 8080)}")

    # 性能监控装饰器绑定到配置的端点上
    from datetime import datetime


def register_blueprints(app):
    """
    注册URL蓝图
    根据配置决定是否启用性能监控
    """
    # 注册主API蓝图
    app.register_blueprint(api_bp)

    # 为性能敏感的端点添加监控装饰器
    if app.config.get('ENABLE_PERFORMANCE_MONITORING', True):
        import functools

        # 包装关键端点
        if hasattr(api_bp, 'view_functions'):
            for endpoint in ['messages', 'list_models']:
                if endpoint in api_bp.view_functions:
                    original_view = api_bp.view_functions[endpoint]
                    api_bp.view_functions[endpoint] = monitor_performance(original_view)


def register_error_handlers(app):
    """
    注册全局错误处理器
    """

    @app.errorhandler(400)
    def bad_request(error):
        app.logger.warning(f"Bad request: {error.description}")
        return {
            'type': 'error',
            'error': {
                'type': 'invalid_request_error',
                'message': error.description or 'Bad request'
            }
        }, 400

    @app.errorhandler(401)
    def unauthorized(error):
        return {
            'type': 'error',
            'error': {
                'type': 'authentication_error',
                'message': 'Authentication required'
            }
        }, 401

    @app.errorhandler(404)
    def not_found(error):
        return {
            'type': 'error',
            'error': {
                'type': 'not_found_error',
                'message': 'Endpoint not found'
            }
        }, 404

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"Internal server error: {str(error)}")
        return {
            'type': 'error',
            'error': {
                'type': 'server_error',
                'message': 'Internal server error'
            }
        }, 500

    # 自定义异常处理器
    @app.errorhandler(APIServiceError)
    def handle_api_service_error(error):
        app.logger.error(f"API Service Error: {error.message}")
        return {
            'type': 'error',
            'error': {
                'type': error.error_code,
                'message': error.message
            }
        }, error.status_code


def register_hooks(app):
    """
    注册请求钩子
    """
    from flask import g, request
    import time
    import uuid

    @app.before_request
    def before_request():
        """请求前处理"""
        # 生成请求ID
        request.request_id = f"req_{uuid.uuid4().hex[:12]}"
        g.request_id = request.request_id

        # 记录开始时间
        request.start_time = time.time()

        # 记录请求日志
        try:
            headers = dict(request.headers)
            if request.is_json:
                body = request.get_json(silent=True)
            else:
                body = None
        except Exception:
            headers = None
            body = None

        if hasattr(app.logger, 'log_request'):
            app.logger.log_request(
                method=request.method,
                path=request.full_path,
                client_ip=request.remote_addr,
                headers=headers,
                body=body,
                request_id=request.request_id
            )

    @app.after_request
    def after_request(response):
        """请求后处理"""
        if hasattr(request, 'start_time') and hasattr(request, 'request_id'):
            end_time = time.time()
            duration = (end_time - request.start_time) * 1000

            if hasattr(app.logger, 'log_response'):
                app.logger.log_response(
                    status_code=response.status_code,
                    duration_ms=duration,
                    response_size=len(response.get_data()) if hasattr(response, 'get_data') else 0,
                    request_id=request.request_id
                )

            app.logger.info(f"[{request.request_id}] Request completed in {duration:.2f}ms")

        return response


def create_wsgi_app():
    """
    为WSGI服务器创建应用实例
    用于生产环境部署
    """
    app = create_app()
    return app
