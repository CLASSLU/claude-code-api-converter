"""
轻量级API服务器 - 专注核心代理功能
简单、快速、透明
包含SSE流式传输优化，解决Claude Code界面闪烁问题
"""

from flask import Flask, request, jsonify, Response
import os
import requests
import time
import uuid
import json
from .converter import LiteConverter
from .config import LiteConfig
from .logger_setup import get_logger
from .sse_optimizer import get_sse_optimizer

# 初始化配置
config = LiteConfig()
logger = get_logger('api_server', config.config.get('logging', {}))
sse_optimizer = get_sse_optimizer()

app = Flask(__name__)
converter = LiteConverter(model_mappings=config.config.get('model_mappings', []))

@app.before_request
def log_request_info():
    """记录请求信息"""
    start_time = time.time()
    request.start_time = start_time
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    request.request_id = request_id

    try:
        headers = dict(request.headers)
        if request.is_json:
            body = request.get_json(silent=True)
    except Exception:
        headers = None
        body = None

    logger.log_request(
        method=request.method,
        path=request.full_path,
        client_ip=request.remote_addr,
        headers=headers,
        body=body,
        request_id=request.request_id
    )

@app.after_request
def log_response_info(response):
    """记录响应信息"""
    if hasattr(request, 'start_time') and hasattr(request, 'request_id'):
        end_time = time.time()
        duration = (end_time - request.start_time) * 1000
        logger.log_response(
            status_code=response.status_code,
            duration_ms=duration,
            response_size=len(response.get_data()) if hasattr(response, 'get_data') else 0,
            request_id=request.request_id
        )
        logger.info(f"[{request.request_id}] Request completed in {duration:.2f}ms")
    return response

@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    }), 200

def create_optimized_sse_generator(upstream, request_headers):
    """创建优化的SSE生成器，保持工具调用兼容性"""

    def original_sse_passthrough():
        """原始SSE传输逻辑，保持完整功能"""
        msg_id = f"msg_{uuid.uuid4().hex[:24]}"
        model_name = request.get_json().get('model', '')

        # 发送标准事件头
        yield f"data: {json.dumps({'type':'message_start','message':{'id':msg_id,'type':'message','role':'assistant','content':[],'model':model_name}}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type':'content_block_start','index':0,'content_block':{'type':'text','text':''}}, ensure_ascii=False)}\n\n"

        try:
            tool_started = False
            tool_id = None
            tool_name = None

            # 处理流式数据
            for raw in upstream.iter_lines(decode_unicode=False):
                if not raw:
                    continue

                # 简化编码处理
                if isinstance(raw, bytes):
                    line = raw.decode('utf-8', errors='replace').strip()
                else:
                    line = raw.strip()

                if not line.startswith('data:'):
                    continue
                payload = line[5:].strip()
                if payload == '[DONE]':
                    break

                try:
                    evt = json.loads(payload)
                except Exception:
                    continue

                choices = evt.get('choices') or []
                if choices:
                    delta = choices[0].get('delta') or {}

                    # 完整的工具调用支持
                    tool_calls = delta.get('tool_calls', [])
                    if tool_calls:
                        for tool_call_delta in tool_calls:
                            if not tool_started:
                                tool_started = True
                                tool_id = tool_call_delta.get('id', f"tool_{uuid.uuid4().hex[:24]}")
                                function_delta = tool_call_delta.get('function', {})
                                tool_name = function_delta.get('name', '')

                                if tool_name:
                                    start_evt = {
                                        'type': 'content_block_start',
                                        'index': 0,
                                        'content_block': {
                                            'type': 'tool_use',
                                            'id': tool_id,
                                            'name': tool_name,
                                            'input': {}
                                        }
                                    }
                                    yield f"data: {json.dumps(start_evt, ensure_ascii=False)}\n\n"

                            # 处理参数片段
                            args_chunk = function_delta.get('arguments', '') if 'function_delta' in locals() else tool_call_delta.get('function', {}).get('arguments', '')
                            if args_chunk:
                                yield f"data: {json.dumps({'type':'input_json_delta','index':0,'delta': args_chunk}, ensure_ascii=False)}\n\n"

                    elif delta.get('function_call'):  # 兼容旧格式
                        fc = delta.get('function_call') or {}
                        if fc.get('name'):
                            if not tool_started:
                                tool_started = True
                                tool_id = f"tool_{uuid.uuid4().hex[:24]}"
                                tool_name = fc.get('name')
                                start_evt = {
                                    'type': 'content_block_start',
                                    'index': 0,
                                    'content_block': {
                                        'type': 'tool_use',
                                        'id': tool_id,
                                        'name': tool_name,
                                        'input': {}
                                    }
                                }
                                yield f"data: {json.dumps(start_evt, ensure_ascii=False)}\n\n"
                            args_chunk = fc.get('arguments') or ''
                            if args_chunk:
                                yield f"data: {json.dumps({'type':'input_json_delta','index':0,'delta': args_chunk}, ensure_ascii=False)}\n\n"

                    else:
                        # 普通文本内容
                        text_delta = delta.get('content') or ''
                        if text_delta:
                            yield f"data: {json.dumps({'type':'content_block_delta','index':0,'delta':{'type':'text_delta','text': text_delta}}, ensure_ascii=False)}\n\n"

            # 结束事件序列
            if tool_started:
                yield f"data: {json.dumps({'type':'content_block_stop','index':0}, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {json.dumps({'type':'content_block_stop','index':0}, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'type':'message_delta','delta':{'stop_reason':'end_turn'}}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type':'message_stop'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            err = {'type': 'error', 'error': {'type': 'stream_error', 'message': str(e)}}
            yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    # 检查是否需要优化
    if sse_optimizer.should_optimize(request_headers):
        return sse_optimizer.create_optimized_generator(original_sse_passthrough())
    else:
        return original_sse_passthrough()

@app.route('/v1/messages', methods=['POST'])
def messages():
    """Anthropic消息API - 包含流式优化"""
    try:
        anthropic_request = request.get_json(silent=True)
        if not isinstance(anthropic_request, dict):
            return jsonify({
                'type': 'error',
                'error': {
                    'type': 'invalid_request_error',
                    'message': 'Invalid JSON body'
                }
            }), 400

        if not anthropic_request.get('messages'):
            return jsonify({
                'type': 'error',
                'error': {
                    'type': 'invalid_request_error',
                    'message': 'Missing messages field'
                }
            }), 400

        # 转换为OpenAI格式
        openai_request = converter.anthropic_to_openai(anthropic_request)

        # API调用配置
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {config.get_openai_config()["api_key"]}'
        }

        # 检查是否需要流式响应
        client_wants_stream = anthropic_request.get('stream') is True

        if client_wants_stream:
            # 流式请求处理
            try:
                response = requests.post(
                    f'{config.get_openai_config()["base_url"]}/chat/completions',
                    headers=headers,
                    json=openai_request,
                    stream=True,
                    timeout=60
                )

                if response.status_code != 200:
                    return jsonify({
                        'type': 'error',
                        'error': {
                            'type': 'api_error',
                            'message': response.text
                        }
                    }), response.status_code

                # 创建优化的SSE流
                return Response(
                    create_optimized_sse_generator(response, request.headers),
                    headers={
                        'Content-Type': 'text/event-stream',
                        'Cache-Control': 'no-cache',
                        'Connection': 'keep-alive'
                    },
                    mimetype='text/event-stream'
                )

            except Exception as e:
                logger.log_exception(e, "stream messages endpoint")
                return jsonify({
                    'type': 'error',
                    'error': {
                        'type': 'stream_error',
                        'message': str(e)
                    }
                }), 500

        else:
            # 非流式请求处理
            try:
                response = requests.post(
                    f'{config.get_openai_config()["base_url"]}/chat/completions',
                    headers=headers,
                    json=openai_request,
                    timeout=60
                )

                if response.status_code == 200:
                    # 转换回Anthropic格式
                    openai_response = response.json()
                    anthropic_response = converter.openai_to_anthropic(openai_response)
                    return jsonify(anthropic_response)
                else:
                    return jsonify({
                        'type': 'error',
                        'error': {
                            'type': 'api_error',
                            'message': response.text
                        }
                    }), response.status_code

            except Exception as e:
                logger.log_exception(e, "non-stream messages endpoint")
                return jsonify({
                    'type': 'error',
                    'error': {
                        'type': 'api_error',
                        'message': str(e)
                    }
                }), 500

    except Exception as e:
        logger.log_exception(e, "messages endpoint")
        return jsonify({
            'type': 'error',
            'error': {
                'type': 'server_error',
                'message': str(e)
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
            timeout=30
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
        logger.log_exception(e, "models endpoint")
        return jsonify({
            'error': {
                'message': str(e),
                'type': 'server_error'
            }
        }), 500

@app.route('/v1/messages/count_tokens', methods=['POST'])
def count_tokens():
    """Token计数"""
    try:
        request_data = request.get_json()
        if not request_data:
            return jsonify({'error': 'No data provided'}), 400

        # 简单估算：约4个字符=1个token
        text_content = ""
        if 'messages' in request_data:
            for msg in request_data['messages']:
                if isinstance(msg.get('content'), str):
                    text_content += msg['content']
        elif 'text' in request_data:
            text_content = request_data['text']

        # 这里可以使用更精确的token计算方法
        estimated_tokens = max(1, len(text_content) // 4)

        return jsonify({
            'model': request_data.get('model', 'claude-3-5-haiku-20241022'),
            'usage': {
                'input_tokens': estimated_tokens,
                'output_tokens': 0
            }
        })

    except Exception as e:
        logger.log_exception(e, "count_tokens endpoint")
        return jsonify({'error': str(e)}), 500

@app.route('/config', methods=['GET', 'POST'])
def config_endpoint():
    """配置管理端点"""
    if request.method == 'GET':
        return jsonify(config.config), 200
    elif request.method == 'POST':
        try:
            new_config = request.get_json()
            if new_config:
                config.update_config(new_config)
                return jsonify({'status': 'success', 'message': 'Configuration updated'}), 200
            else:
                return jsonify({'error': 'No configuration provided'}), 400
        except Exception as e:
            return jsonify({'error': str(e)}), 500

# 从datetime导入
from datetime import datetime

if __name__ == '__main__':
    server_config = config.config.get('server', {
        'host': '0.0.0.0',
        'port': 8080,
        'debug': False
    })

    logger.info(f"Starting API server on {server_config['host']}:{server_config['port']}")

    try:
        app.run(
            host=server_config['host'],
            port=server_config['port'],
            debug=server_config['debug']
        )
    except Exception as e:
        logger.log_exception(e, "server startup")
        raise