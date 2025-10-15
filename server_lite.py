"""
轻量级API服务器 - 专注核心代理功能
简单、快速、透明
"""

from flask import Flask, request, jsonify
import os
import requests
import logging
from converter_lite import LiteConverter
from config_lite import LiteConfig

# 只记录错误级别日志
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

# 初始化
app = Flask(__name__)
config = LiteConfig()
converter = LiteConverter()


@app.route('/v1/messages', methods=['POST'])
def messages():
    """Anthropic消息API"""
    try:
        anthropic_request = request.get_json()

        # 验证请求
        if 'messages' not in anthropic_request:
            return jsonify({
                'type': 'error',
                'error': {
                    'type': 'invalid_request_error',
                    'message': 'Missing required field: messages'
                }
            }), 400

        # 转换请求格式
        openai_request = converter.convert_request(anthropic_request)

        # 调用OpenAI API
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {config.get_openai_config()["api_key"]}'
        }

        response = requests.post(
            f'{config.get_openai_config()["base_url"]}/chat/completions',
            headers=headers,
            json=openai_request,
            timeout=60
        )

        if response.status_code == 200:
            openai_response = response.json()
            anthropic_response = converter.convert_response(openai_response)
            anthropic_response['model'] = anthropic_request.get('model', 'claude-3-sonnet-20240229')
            return jsonify(anthropic_response)
        else:
            return jsonify({
                'type': 'error',
                'error': {
                    'type': 'api_error',
                    'message': f'OpenAI API error: {response.text}'
                }
            }), response.status_code

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return jsonify({
            'type': 'error',
            'error': {
                'type': 'server_error',
                'message': str(e)
            }
        }), 500


@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    """OpenAI聊天API"""
    try:
        openai_request = request.get_json()

        # 验证请求
        if 'messages' not in openai_request:
            return jsonify({
                'error': {
                    'message': 'Missing required field: messages',
                    'type': 'invalid_request_error'
                }
            }), 400

        # 直接转发到OpenAI API
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {config.get_openai_config()["api_key"]}'
        }

        response = requests.post(
            f'{config.get_openai_config()["base_url"]}/chat/completions',
            headers=headers,
            json=openai_request,
            timeout=60
        )

        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({
                'error': {
                    'message': f'OpenAI API error: {response.text}',
                    'type': 'api_error'
                }
            }), response.status_code

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return jsonify({
            'error': {
                'message': str(e),
                'type': 'server_error'
            }
        }), 500


@app.route('/v1/models', methods=['GET'])
def list_models():
    """模型列表"""
    try:
        headers = {
            'Authorization': f'Bearer {config.get_openai_config()["api_key"]}'
        }

        response = requests.get(
            f'{config.get_openai_config()["base_url"]}/models',
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            return jsonify(response.json())
        else:
            # 返回默认模型列表
            return jsonify({
                "object": "list",
                "data": [
                    {"id": "gpt-4", "object": "model", "created": 1707879684},
                    {"id": "gpt-3.5-turbo", "object": "model", "created": 1707879684}
                ]
            })
    except:
        return jsonify({"object": "list", "data": []})


@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({"status": "healthy"})


@app.route('/config', methods=['GET'])
def get_config():
    """获取配置"""
    return jsonify(config.config)


@app.route('/config', methods=['POST'])
def update_config():
    """更新配置"""
    try:
        new_config = request.get_json()

        # 更新配置
        if 'openai' in new_config:
            config.update_openai_config(
                api_key=new_config['openai'].get('api_key'),
                base_url=new_config['openai'].get('base_url')
            )

        if 'server' in new_config:
            config.update_server_config(
                host=new_config['server'].get('host'),
                port=new_config['server'].get('port'),
                debug=new_config['server'].get('debug')
            )

        config.save_config()
        return jsonify({"status": "success"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


if __name__ == '__main__':
    server_config = config.get_server_config()

    print(f"启动轻量级API服务器...")
    print(f"地址: http://{server_config['host']}:{server_config['port']}/")
    print(f"支持环境变量配置")

    app.run(
        host=server_config['host'],
        port=server_config['port'],
        debug=server_config['debug']
    )