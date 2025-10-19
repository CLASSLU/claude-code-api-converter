"""
模型API蓝图
提供模型列表和相关功能
"""

import json
from flask import Blueprint, request, jsonify
from app.config import LiteConfig
from app.logger_setup import get_logger
from app.core.exceptions import UpstreamAPIError, handle_upstream_response
from app.core.decorators import monitor_performance, retry, cache_result, rate_limit

# 创建蓝图
models_bp = Blueprint('models', __name__)

# 初始化服务
config = LiteConfig()
logger = get_logger('models_api', config.config.get('logging', {}))


@models_bp.route('/v1/models', methods=['GET'])
@monitor_performance
@rate_limit(calls=50, period=60)
@cache_result(ttl_seconds=300, max_size=64)  # 缓存5分钟
@retry(max_attempts=3, delay=1)
def list_models():
    """
    获取可用模型列表
    """
    try:
        headers = {
            'Authorization': f'Bearer {config.get_openai_config()["api_key"]}'
        }

        logger.info("Fetching models list from upstream API")

        response = requests.get(
            f'{config.get_openai_config()["base_url"]}/models',
            headers=headers,
            timeout=30
        )

        if response.status_code == 200:
            models_data = response.json()
            logger.debug(f"Successfully retrieved {len(models_data.get('data', []))} models")
            return jsonify(models_data)
        else:
            raise handle_upstream_response(response, "Failed to fetch models")

    except UpstreamAPIError as e:
        logger.error(f"Upstream API error in models endpoint: {str(e)}")
        return e.to_dict(), e.status_code

    except Exception as e:
        logger.log_exception(e, "models endpoint")
        return {
            'type': 'error',
            'error': {
                'type': 'server_error',
                'message': 'Failed to fetch models'
            }
        }, 500


@models_bp.route('/v1/models/<model_id>', methods=['GET'])
@monitor_performance
@rate_limit(calls=30, period=60)
@cache_result(ttl_seconds=600, max_size=128)  # 缓存10分钟
@retry(max_attempts=3, delay=1)
def get_model(model_id):
    """
    获取特定模型信息
    """
    try:
        headers = {
            'Authorization': f'Bearer {config.get_openai_config()["api_key"]}'
        }

        logger.info(f"Fetching model details for: {model_id}")

        response = requests.get(
            f'{config.get_openai_config()["base_url"]}/models/{model_id}',
            headers=headers,
            timeout=30
        )

        if response.status_code == 200:
            model_data = response.json()
            logger.debug(f"Successfully retrieved model details for: {model_id}")
            return jsonify(model_data)
        elif response.status_code == 404:
            return {
                'type': 'error',
                'error': {
                    'type': 'not_found_error',
                    'message': f'Model {model_id} not found'
                }
            }, 404
        else:
            raise handle_upstream_response(response, f"Failed to fetch model {model_id}")

    except UpstreamAPIError as e:
        logger.error(f"Upstream API error in get_model endpoint: {str(e)}")
        return e.to_dict(), e.status_code

    except Exception as e:
        logger.log_exception(e, f"get_model endpoint for {model_id}")
        return {
            'type': 'error',
            'error': {
                'type': 'server_error',
                'message': 'Failed to fetch model details'
            }
        }, 500


# 导入requests模块
import requests