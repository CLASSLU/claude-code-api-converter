"""
配置管理API蓝图
提供配置查看和更新功能
"""

from flask import Blueprint, request, jsonify
from app.config import LiteConfig
from app.logger_setup import get_logger
from app.core.exceptions import ConfigurationError, ValidationError
from app.core.decorators import monitor_performance, rate_limit, validate_json

# 创建蓝图
config_bp = Blueprint('config', __name__)

# 初始化服务
config = LiteConfig()
logger = get_logger('config_api', config.config.get('logging', {}))


@config_bp.route('/config', methods=['GET'])
@monitor_performance
@rate_limit(calls=50, period=60)
def get_config():
    """
    获取当前配置信息（敏感信息已脱敏）
    """
    try:
        # 获取配置副本并脱敏敏感信息
        config_data = config.get_safe_config()

        logger.debug("Configuration retrieved")
        return jsonify({
            'status': 'success',
            'config': config_data,
            'timestamp': __import__('datetime').datetime.now().isoformat()
        }), 200

    except Exception as e:
        logger.error(f"Error retrieving configuration: {str(e)}")
        return {
            'type': 'error',
            'error': {
                'type': 'configuration_error',
                'message': 'Failed to retrieve configuration'
            }
        }, 500


@config_bp.route('/config', methods=['POST'])
@monitor_performance
@rate_limit(calls=10, period=60)
@validate_json(
    optional_fields={
        'openai': dict,
        'server': dict,
        'logging': dict,
        'features': dict,
        'model_mappings': list
    }
)
def update_config():
    """
    更新配置信息
    """
    try:
        new_config = request.get_json(silent=True)
        if not new_config:
            raise ValidationError("No configuration provided")

        # 验证配置格式
        validation_errors = validate_config_format(new_config)
        if validation_errors:
            raise ValidationError(
                message="Invalid configuration format",
                details={'validation_errors': validation_errors}
            )

        # 更新配置
        try:
            config.update_config(new_config)
            logger.info("Configuration updated successfully")
        except Exception as e:
            raise ConfigurationError(
                message=f"Failed to update configuration: {str(e)}",
                config_key='update'
            )

        return jsonify({
            'status': 'success',
            'message': 'Configuration updated successfully',
            'timestamp': __import__('datetime').datetime.now().isoformat()
        }), 200

    except (ValidationError, ConfigurationError) as e:
        logger.error(f"Configuration update error: {str(e)}")
        return e.to_dict(), e.status_code

    except Exception as e:
        logger.error(f"Unexpected error in config update: {str(e)}")
        return {
            'type': 'error',
            'error': {
                'type': 'server_error',
                'message': 'Failed to update configuration'
            }
        }, 500


@config_bp.route('/config/validate', methods=['POST'])
@monitor_performance
@rate_limit(calls=20, period=60)
@validate_json()
def validate_config():
    """
    验证配置格式而不实际更新
    """
    try:
        config_data = request.get_json(silent=True)
        if not config_data:
            raise ValidationError("No configuration provided")

        # 执行详细验证
        validation_result = validate_config_format(config_data)

        if validation_result:
            return jsonify({
                'status': 'error',
                'valid': False,
                'errors': validation_result,
                'timestamp': __import__('datetime').datetime.now().isoformat()
            }), 400
        else:
            return jsonify({
                'status': 'success',
                'valid': True,
                'message': 'Configuration format is valid',
                'timestamp': __import__('datetime').datetime.now().isoformat()
            }), 200

    except ValidationError as e:
        return e.to_dict(), e.status_code

    except Exception as e:
        logger.error(f"Error validating configuration: {str(e)}")
        return {
            'type': 'error',
            'error': {
                'type': 'server_error',
                'message': 'Failed to validate configuration'
            }
        }, 500


@config_bp.route('/config/reload', methods=['POST'])
@monitor_performance
@rate_limit(calls=5, period=60)
def reload_config():
    """
    重新从文件加载配置
    """
    try:
        config.reload_from_file()
        logger.info("Configuration reloaded from file")
        return jsonify({
            'status': 'success',
            'message': 'Configuration reloaded from file',
            'timestamp': __import__('datetime').datetime.now().isoformat()
        }), 200

    except Exception as e:
        logger.error(f"Error reloading configuration: {str(e)}")
        return {
            'type': 'error',
            'error': {
                'type': 'configuration_error',
                'message': 'Failed to reload configuration'
            }
        }, 500


def validate_config_format(config_data):
    """
    验证配置格式的详细规则
    返回错误列表，空列表表示验证通过
    """
    errors = []

    # 验证服务器配置
    if 'server' in config_data:
        server_config = config_data['server']
        if isinstance(server_config, dict):
            # 验证端口号
            if 'port' in server_config:
                port = server_config['port']
                if not isinstance(port, int) or not (1 <= port <= 65535):
                    errors.append("server.port must be an integer between 1 and 65535")

            # 验证主机地址
            if 'host' in server_config:
                host = server_config['host']
                if not isinstance(host, str) or not host.strip():
                    errors.append("server.host must be a non-empty string")

            # 验证debug模式
            if 'debug' in server_config:
                debug = server_config['debug']
                if not isinstance(debug, bool):
                    errors.append("server.debug must be a boolean")

    # 验证OpenAI配置
    if 'openai' in config_data:
        openai_config = config_data['openai']
        if isinstance(openai_config, dict):
            # API密钥验证
            if 'api_key' in openai_config:
                api_key = openai_config['api_key']
                if not isinstance(api_key, str) or len(api_key.strip()) < 10:
                    errors.append("openai.api_key must be a string with at least 10 characters")

            # base_url验证
            if 'base_url' in openai_config:
                base_url = openai_config['base_url']
                if not isinstance(base_url, str) or not base_url.strip():
                    errors.append("openai.base_url must be a non-empty string")
                elif not (base_url.startswith('http://') or base_url.startswith('https://')):
                    errors.append("openai.base_url must start with http:// or https://")

    # 验证日志配置
    if 'logging' in config_data:
        logging_config = config_data['logging']
        if isinstance(logging_config, dict):
            # 日志级别
            if 'level' in logging_config:
                level = logging_config['level']
                valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR']
                if level not in valid_levels:
                    errors.append(f"logging.level must be one of {valid_levels}")

            # 文件大小限制
            if 'max_file_size' in logging_config:
                size = logging_config['max_file_size']
                if not isinstance(size, int) or size < 1024:  # 最小1KB
                    errors.append("logging.max_file_size must be an integer >= 1024")

            # 备份文件数量
            if 'backup_count' in logging_config:
                count = logging_config['backup_count']
                if not isinstance(count, int) or count < 1 or count > 20:
                    errors.append("logging.backup_count must be an integer between 1 and 20")

    # 验证模型映射
    if 'model_mappings' in config_data:
        model_mappings = config_data['model_mappings']
        if isinstance(model_mappings, list):
            for i, mapping in enumerate(model_mappings):
                if not isinstance(mapping, dict):
                    errors.append(f"model_mappings[{i}] must be an object")
                else:
                    if not isinstance(mapping.get('anthropic'), str) or not mapping['anthropic'].strip():
                        errors.append(f"model_mappings[{i}].anthropic must be a non-empty string")
                    if not isinstance(mapping.get('openai'), str) or not mapping['openai'].strip():
                        errors.append(f"model_mappings[{i}].openai must be a non-empty string")

    return errors