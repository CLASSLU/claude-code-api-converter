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
from .simple_sse_optimizer import get_simple_sse_optimizer
from .fixed_sse_generator import create_fixed_sse_generator

# 初始化配置
config = LiteConfig()
logger = get_logger('api_server', config.config.get('logging', {}))
sse_optimizer = get_simple_sse_optimizer()

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
        body = None
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
    """记录响应信息并拦截449错误"""
    if hasattr(request, 'start_time') and hasattr(request, 'request_id'):
        end_time = time.time()
        duration = (end_time - request.start_time) * 1000

        # 终极449拦截 - 确保没有任何449能泄漏出去
        if response.status_code == 449:
            logger.info(f"[449_DEBUG] **** FINAL 449 INTERCEPTION **** Caught 449 in after_request, forcing conversion to 429")

            # 强制转换为429速率限制错误
            from flask import jsonify
            error_response = jsonify({
                'type': 'error',
                'error': {
                    'type': 'rate_limit_error',
                    'message': 'You exceeded your current rate limit'
                }
            })
            error_response.status_code = 429
            error_response.headers['retry-after'] = '60'
            error_response.headers['anthropic-ratelimit-requests-limit'] = '60'
            error_response.headers['anthropic-ratelimit-requests-remaining'] = '0'

            # 记录转换
            logger.info(f"[{request.request_id}] HTTP Response - Status: 429 (converted from 449)")
            logger.info(f"[{request.request_id}] Request completed in {duration:.2f}ms")
            return error_response

        # 简化日志调用，避免参数错误
        try:
            logger.log_response(
                status_code=response.status_code,
                duration_ms=duration,
                response_size=len(response.get_data()) if hasattr(response, 'get_data') else 0,
                request_id=request.request_id
            )
        except Exception as e:
            logger.info(f"[{request.request_id}] HTTP Response - Status: {response.status_code} (logging error: {e})")
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

def create_optimized_sse_generator(upstream, request_headers, model_name, input_tokens=0):
    """创建修复后的SSE生成器，解决UI闪烁问题"""

    logger.info(f"[SSE_DEBUG] Creating optimized SSE generator for model: {model_name}")

    # 检查是否需要优化（暂时禁用，使用修复后的生成器）
    should_opt = sse_optimizer.should_optimize(request_headers)
    enable_delay = should_opt  # 只在需要优化时启用延迟

    logger.info(f"[SSE_DEBUG] SSE optimization enabled: {enable_delay} for User-Agent: {request_headers.get('User-Agent', 'Unknown')}")

    try:
        # 使用修复后的SSE生成器
        logger.info(f"[SSE_DEBUG] Calling create_fixed_sse_generator...")
        result = create_fixed_sse_generator(
            upstream_response=upstream,
            model_name=model_name,
            input_tokens=input_tokens,
            enable_delay=enable_delay
        )
        logger.info(f"[SSE_DEBUG] Fixed SSE generator created successfully")
        return result
    except Exception as e:
        logger.error(f"[SSE_DEBUG] Error creating fixed SSE generator: {e}")
        # 降级到原始流
        logger.info(f"[SSE_DEBUG] Falling back to original stream")
        return upstream.iter_lines(decode_unicode=False)

@app.route('/v1/messages', methods=['POST'])
def messages():
    """Anthropic消息API - 包含流式优化"""
    # 强制记录所有请求开始
    logger.info(f"[449_DEBUG] ===== /v1/messages request started =====")
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

                logger.debug(f"[SERVER_DEBUG] Upstream response status code: {response.status_code}")

                if response.status_code != 200:
                    # 特殊处理429和449速率限制错误，使用SSE流格式返回
                    if response.status_code in [429, 449]:
                        converted_status = 429
                        logger.debug(f"[SERVER_DEBUG] Got {response.status_code} rate limit error from upstream, converting to SSE stream with status {converted_status}")

                        # 尝试解析上游错误消息
                        error_message = 'Your account has hit a rate limit.'
                        try:
                            error_data = response.json()
                            if isinstance(error_data, dict):
                                error_message = error_data.get('msg') or error_data.get('message', error_message)
                        except:
                            error_message = response.text or error_message

                        logger.info(f"[SERVER_DEBUG] Creating rate limit SSE stream for: {error_message}")

                        # 创建SSE格式的错误流响应
                        def generate_rate_limit_sse():
                            from app.fixed_sse_generator import FixedSSEGenerator
                            generator = FixedSSEGenerator(anthropic_request.get('model', ''))

                            # 发送message_start
                            yield generator._create_message_start()

                            # 发送错误内容
                            yield generator._create_content_block_start('text')
                            yield generator._create_content_block_delta(0, 'text_delta', f"[速率限制] {error_message}，请稍后重试")
                            yield generator._create_content_block_stop(0)

                            # 发送结束事件
                            yield generator._create_message_delta("end_turn", 0)
                            yield generator._create_message_stop()
                            yield generator._create_done()

                        sse_response = Response(
                            stream_with_context(generate_rate_limit_sse()),
                            mimetype='text/event-stream',
                            headers={
                                'Cache-Control': 'no-cache',
                                'Connection': 'keep-alive',
                                'Access-Control-Allow-Origin': '*',
                                'Access-Control-Allow-Headers': 'Content-Type, Authorization, Anthropic-Version',
                                # 添加符合Anthropic规范的retry-after头
                                'retry-after': '60',
                                'anthropic-ratelimit-requests-limit': '60',
                                'anthropic-ratelimit-requests-remaining': '0'
                            }
                        )
                        return sse_response, converted_status  # 返回转换后的429状态码，而不是200
                    else:
                        return jsonify({
                            'type': 'error',
                            'error': {
                                'type': 'api_error',
                                'message': response.text
                            }
                        }), response.status_code

                # 强制检查上游响应状态码
                logger.info(f"[449_DEBUG] Stream upstream response status: {response.status_code}")
                if response.status_code in [429, 449]:
                    converted_status = 429
                    logger.info(f"[449_DEBUG] **** CATCHING 449 IN STREAM PROCESSING **** Converting {response.status_code} to SSE stream with status {converted_status}")

                    # 尝试解析上游错误消息
                    error_message = 'Your account has hit a rate limit.'
                    try:
                        error_data = response.json()
                        if isinstance(error_data, dict):
                            error_message = error_data.get('msg') or error_data.get('message', error_message)
                    except:
                        error_message = response.text or error_message

                    logger.info(f"[SERVER_DEBUG] Creating rate limit SSE stream for: {error_message}")

                    # 创建SSE格式的错误流响应
                    def generate_rate_limit_sse():
                        from app.fixed_sse_generator import FixedSSEGenerator
                        generator = FixedSSEGenerator(anthropic_request.get('model', ''))

                        # 发送message_start
                        yield generator._create_message_start()

                        # 发送错误内容
                        yield generator._create_content_block_start('text')
                        yield generator._create_content_block_delta(0, 'text_delta', f"[速率限制] {error_message}，请稍后重试")
                        yield generator._create_content_block_stop(0)

                        # 发送结束事件
                        yield generator._create_message_delta("end_turn", 0)
                        yield generator._create_message_stop()
                        yield generator._create_done()

                    sse_response = Response(
                        stream_with_context(generate_rate_limit_sse()),
                        mimetype='text/event-stream',
                        headers={
                            'Cache-Control': 'no-cache',
                            'Connection': 'keep-alive',
                            'Access-Control-Allow-Origin': '*',
                            'Access-Control-Allow-Headers': 'Content-Type, Authorization, Anthropic-Version',
                            # 添加符合Anthropic规范的retry-after头
                            'retry-after': '60',
                            'anthropic-ratelimit-requests-limit': '60',
                            'anthropic-ratelimit-requests-remaining': '0'
                        }
                    )
                    return sse_response, converted_status  # 返回转换后的429状态码

                # 创建优化的SSE流
                model_name = anthropic_request.get('model', '')
                logger.debug(f"[SERVER_DEBUG] Creating optimized SSE generator for model: {model_name}")

                # 计算input_tokens（简单估算）
                input_tokens = 0
                if 'messages' in anthropic_request:
                    for msg in anthropic_request['messages']:
                        if isinstance(msg.get('content'), str):
                            input_tokens += len(msg['content']) // 4
                        elif isinstance(msg.get('content'), list):
                            for item in msg.get('content', []):
                                if item.get('type') == 'text':
                                    input_tokens += len(item.get('text', '')) // 4

                if 'system' in anthropic_request:
                    input_tokens += len(anthropic_request['system']) // 4

                input_tokens = max(1, input_tokens)  # 至少1个token

                # 检查是否是速率限制错误，如果是则返回429状态码
                response_status = 429 if response.status_code in [429, 449] else 200

                return Response(
                    create_optimized_sse_generator(response, request.headers, model_name, input_tokens),
                    headers={
                        'Content-Type': 'text/event-stream',
                        'Cache-Control': 'no-cache',
                        'Connection': 'keep-alive'
                    },
                    mimetype='text/event-stream'
                ), response_status

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

                try:
                    openai_response = response.json()
                except:
                    openai_response = {'error': {'message': response.text}}

                # 检查响应体中的状态字段（某些API使用这种方式）
                api_status = openai_response.get('status')
                if api_status and api_status != '200':
                    # API返回了错误状态，直接传递给下游
                    return jsonify(openai_response), int(api_status)

                if response.status_code == 200:
                    # 检查是否为错误响应（没有choices字段）
                    if not openai_response.get('choices'):
                        # 检查是否有状态字段，如果有则使用该状态码
                        error_status = openai_response.get('status', 500)
                        return jsonify(openai_response), int(error_status)

                    # 转换回Anthropic格式
                    anthropic_response = converter.openai_to_anthropic(openai_response)
                    return jsonify(anthropic_response)
                else:
                    # 强制检查非流式响应状态码
                    logger.info(f"[449_DEBUG] Non-stream upstream response status: {response.status_code}")
                    # 对于HTTP错误状态码，特殊处理429和449速率限制错误
                    if response.status_code in [429, 449]:
                        converted_status = 429
                        logger.info(f"[449_DEBUG] **** CATCHING 449 IN NON-STREAM PROCESSING **** Converting {response.status_code} to status {converted_status}")
                        # 尝试解析上游错误消息
                        error_message = 'Your account has hit a rate limit.'
                        try:
                            error_data = response.json()
                            if isinstance(error_data, dict):
                                error_message = error_data.get('msg') or error_data.get('message', error_message)
                        except:
                            error_message = response.text or error_message

                        error_response = jsonify({
                            'type': 'error',
                            'error': {
                                'type': 'rate_limit_error',
                                'message': error_message
                            }
                        })
                        # 添加符合Anthropic规范的retry-after头
                        error_response.headers['retry-after'] = '60'  # 60秒后重试
                        error_response.headers['anthropic-ratelimit-requests-limit'] = '60'
                        error_response.headers['anthropic-ratelimit-requests-remaining'] = '0'
                        return error_response, converted_status
                    else:
                        # 其他HTTP错误，检查是否包含449错误信息
                        if response.status_code == 449 or 'status' in str(openai_response):
                            # 检查响应内容是否包含449错误
                            response_str = str(openai_response)
                            if '449' in response_str or 'rate limit' in response_str.lower():
                                logger.info(f"[SERVER_DEBUG] Detected 449 error in response, converting to proper error format")
                                error_message = 'You exceeded your current rate limit'
                                try:
                                    if isinstance(openai_response, dict):
                                        error_message = openai_response.get('msg') or openai_response.get('message', error_message)
                                except:
                                    pass

                                error_response = jsonify({
                                    'type': 'error',
                                    'error': {
                                        'type': 'rate_limit_error',
                                        'message': error_message
                                    }
                                })
                                error_response.headers['retry-after'] = '60'
                                error_response.headers['anthropic-ratelimit-requests-limit'] = '60'
                                error_response.headers['anthropic-ratelimit-requests-remaining'] = '0'
                                return error_response, 429

                        # 其他HTTP错误，检查状态码并做相应处理
                        if response.status_code == 449:
                            # 明确处理449状态码，转换为标准的429速率限制错误
                            logger.info(f"[449_DEBUG] **** CATCHING 449 IN FALLBACK PROCESSING **** Converting HTTP 449 status to 429 rate limit error")
                            error_response = jsonify({
                                'type': 'error',
                                'error': {
                                    'type': 'rate_limit_error',
                                    'message': 'You exceeded your current rate limit'
                                }
                            })
                            error_response.headers['retry-after'] = '60'
                            error_response.headers['anthropic-ratelimit-requests-limit'] = '60'
                            error_response.headers['anthropic-ratelimit-requests-remaining'] = '0'
                            return error_response, 429
                        else:
                            # 其他HTTP错误，直接返回原始响应和状态码，让下游处理
                            return jsonify(openai_response), response.status_code

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