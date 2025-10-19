"""
优化后的主服务器应用
集成所有性能优化和新架构特性
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app, create_wsgi_app
from app.config import LiteConfig
from app.logger_setup import get_logger
from app.utils.performance import get_performance_stats, reset_performance_stats
from app.utils.cache import get_default_cache, clear_all_caches
from app.utils.http_client import cleanup_clients


def main():
    """
    主函数 - 启动优化后的服务器
    """
    # 加载配置
    config = LiteConfig()
    server_config = config.get_server_config()
    logger = get_logger('server_optimized', config.config.get('logging', {}))

    try:
        # 创建Flask应用
        app = create_app()

        # 启动前性能检查
        logger.info("=== Server Performance Information ===")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Working directory: {os.getcwd()}")

        # 显示缓存状态
        cache_stats = get_default_cache().stats()
        logger.info(f"Memory cache initialized: {cache_stats['size']}/{cache_stats['max_size']} items")

        # 启动服务器
        host = server_config.get('host', '0.0.0.0')
        port = server_config.get('port', 8080)
        debug = server_config.get('debug', False)

        logger.info(f"Starting optimized API server on {host}:{port}")
        logger.info(f"Debug mode: {debug}")
        logger.info(f"Performance monitoring: {'enabled' if config.config.get('features', {}).get('enable_performance_monitoring', True) else 'disabled'}")
        logger.info(f"Caching: {'enabled' if config.config.get('features', {}).get('enable_caching', True) else 'disabled'}")

        # 启动Flask开发服务器
        app.run(
            host=host,
            port=port,
            debug=debug,
            threaded=True  # 启用多线程支持
        )

    except KeyboardInterrupt:
        logger.info("Server shutdown requested by user")
    except Exception as e:
        logger.log_exception(e, "server startup")
        raise
    finally:
        # 清理资源
        cleanup_clients()
        clear_all_caches()
        logger.info("Server shutdown complete")


def run_production():
    """
    生产环境运行函数
    用于WSGI服务器部署
    """
    try:
        app = create_wsgi_app()
        return app
    except Exception as e:
        logger = get_logger('server_production', {})
        logger.log_exception(e, "production server creation")
        raise


def performance_test():
    """
    性能测试函数
    """
    import time
    from app.utils.performance import monitor_performance
    from app.utils.http_client import benchmark_request

    config = LiteConfig()
    logger = get_logger('performance_test', config.config.get('logging', {}))

    logger.info("=== Performance Test Suite ===")

    # 测试基础性能
    @monitor_performance("basic_operation")
    def basic_operation():
        time.sleep(0.001)
        return "test_complete"

    # 运行基准测试
    start_time = time.time()
    for i in range(100):
        basic_operation()
    total_time = time.time() - start_time

    logger.info(f"Basic operation test: {total_time:.3f}s for 100 calls")

    # 显示性能统计
    stats = get_performance_stats()
    for name, data in stats.items():
        if data.get('count', 0) > 0:
            logger.info(f"{name}: {data['count']} calls, avg {data.get('avg_duration', 0):.4f}s")

    # HTTP请求基准测试（如果配置了上游API）
    try:
        openai_config = config.get_openai_config()
        if openai_config.get('base_url'):
            result = benchmark_request(
                f"{openai_config['base_url']}/models",
                method='GET',
                headers={'Authorization': f'Bearer {openai_config["api_key"]}'}
            )
            logger.info(f"HTTP benchmark: {result['duration_ms']:.2f}ms, status: {result['status_code']}")
    except Exception as e:
        logger.warning(f"HTTP benchmark skipped: {str(e)}")


if __name__ == '__main__':
    # 检查命令行参数
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == 'test':
            performance_test()
        elif command == 'production':
            print("Use this module with a WSGI server like Gunicorn:")
            print("gunicorn -w 4 -b 0.0.0.0:8080 'app.server_optimized:run_production()'")
        else:
            print("Usage:")
            print("  python server_optimized.py              # Start development server")
            print("  python server_optimized.py test        # Run performance tests")
            print("  python server_optimized.py production  # Show production deployment info")
    else:
        main()