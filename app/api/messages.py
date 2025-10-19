"""
消息处理API蓝图
处理Anthropic消息格式转换和流式响应
"""

import json
import uuid
import time
from flask import Blueprint, request, jsonify, Response
from app.converter import LiteConverter
from app.config import LiteConfig
from app.logger_setup import get_logger
from app.core.exceptions import (
    ConversionError, UpstreamAPIError, ValidationError,
    StreamingError, handle_upstream_response
)
from app.core.decorators import (
    validate_json, monitor_performance, retry,
    cache_result, rate_limit
)

# 创建蓝图
messages_bp = Blueprint('messages', __name__)

# 初始化服务
config = LiteConfig()
converter = LiteConverter(model_mappings=config.config.get('model_mappings', []))
logger = get_logger('messages_api', config.config.get('logging', {}))


@messages_bp.route('/v1/messages', methods=['POST'])
@monitor_performance
@rate_limit(calls=100, period=60)
@validate_json(
    required_fields=['messages'],
    optional_fields={
        'model': str,
        'max_tokens': int,
        'stream': bool,
        'temperature': (int, float),
        'top_p': (int, float),
        'stop': (str, list)
    }
)
def messages():
    """
    Anthropic消息API端点
    支持流式和非流式响应
    """
    try:
        anthropic_request = request.get_json(silent=True)
        if not isinstance(anthropic_request, dict):
            raise ValidationError("Invalid JSON body")

        # 验证消息格式
        messages = anthropic_request.get('messages', [])
        if not messages or not isinstance(messages, list):
            raise ValidationError("Messages field must be a non-empty array")

        for i, msg in enumerate(messages):
            if not isinstance(msg, dict):
                raise ValidationError(f"Message {i} must be an object")
            if 'role' not in msg or 'content' not in msg:
                raise ValidationError(f"Message {i} must have 'role' and 'content' fields")

        # 转换为OpenAI格式
        try:
            openai_request = converter.anthropic_to_openai(anthropic_request)
            logger.debug(f"Successfully converted Anthropic request to OpenAI format")
        except Exception as e:
            raise ConversionError(f"Request format conversion failed: {str(e)}")

        # 检查是否需要流式响应
        client_wants_stream = anthropic_request.get('stream', False)

        if client_wants_stream:
            return handle_stream_request(openai_request, request.headers)
        else:
            return handle_non_stream_request(openai_request)

    except (ValidationError, ConversionError) as e:
        logger.error(f"Validation/Conversion error in messages endpoint: {str(e)}")
        return e.to_dict(), e.status_code

    except Exception as e:
        logger.log_exception(e, "messages endpoint")
        return {
            'type': 'error',
            'error': {
                'type': 'server_error',
                'message': 'Internal server error'
            }
        }, 500


@retry(max_attempts=3, delay=1)
def handle_stream_request(openai_request, request_headers):
    """
    处理流式请求
    """
    try:
        # API调用配置
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {config.get_openai_config()["api_key"]}'
        }

        logger.info(f"Initiating stream request to upstream API")

        # 发送流式请求
        response = requests.post(
            f'{config.get_openai_config()["base_url"]}/chat/completions',
            headers=headers,
            json=openai_request,
            stream=True,
            timeout=60
        )

        if response.status_code != 200:
            raise handle_upstream_response(response, "Stream API call failed")

        # 创建优化的SSE流
        return Response(
            create_optimized_sse_generator(response, request_headers),
            headers={
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Cache-Control'
            },
            mimetype='text/event-stream'
        )

    except Exception as e:
        if isinstance(e, (UpstreamAPIError, StreamingError)):
            raise
        else:
            raise StreamingError(f"Stream processing failed: {str(e)}")


@retry(max_attempts=2, delay=0.5)
def handle_non_stream_request(openai_request):
    """
    处理非流式请求
    """
    try:
        # API调用配置
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {config.get_openai_config()["api_key"]}'
        }

        logger.info(f"Initiating non-stream request to upstream API")

        # 发送请求
        response = requests.post(
            f'{config.get_openai_config()["base_url"]}/chat/completions',
            headers=headers,
            json=openai_request,
            timeout=60
        )

        if response.status_code == 200:
            # 转换回Anthropic格式
            try:
                openai_response = response.json()
                anthropic_response = converter.openai_to_anthropic(openai_response)
                logger.debug(f"Successfully converted OpenAI response to Anthropic format")
                return jsonify(anthropic_response)
            except Exception as e:
                raise ConversionError(f"Response format conversion failed: {str(e)}")
        else:
            raise handle_upstream_response(response, "Non-stream API call failed")

    except (ConversionError, UpstreamAPIError) as e:
        raise
    except Exception as e:
        raise UpstreamAPIError(f"Non-stream request failed: {str(e)}")


def create_optimized_sse_generator(upstream, request_headers):
    """
    创建优化的SSE生成器
    保持工具调用兼容性和性能优化
    """
    msg_id = f"msg_{uuid.uuid4().hex[:24]}"
    model_name = request.get_json().get('model', '') if request.get_json() else 'unknown'

    def sse_generator():
        """SSE流生成器"""
        try:
            # 发送标准事件头
            yield f"data: {json.dumps({'type':'message_start','message':{'id':msg_id,'type':'message','role':'assistant','content':[],'model':model_name}}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type':'content_block_start','index':0,'content_block':{'type':'text','text':''}}, ensure_ascii=False)}\n\n"

            tool_started = False
            tool_id = None
            tool_name = None
            content_buffer = []

            # 处理流式数据
            for raw in upstream.iter_lines(decode_unicode=False):
                if not raw:
                    continue

                # 安全编码处理
                try:
                    line_str = raw.decode('utf-8', errors='replace').strip()
                except Exception:
                    line_str = raw.decode('latin1', errors='replace').strip()

                if not line_str.startswith('data:'):
                    continue

                payload = line_str[5:].strip()
                if payload == '[DONE]':
                    break

                try:
                    event = json.loads(payload)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse SSE payload: {payload[:100]}...")
                    continue

                choices = event.get('choices', [])
                if not choices:
                    continue

                delta = choices[0].get('delta', {})

                # 处理工具调用
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
                        args_chunk = function_delta.get('arguments', '')
                        if args_chunk:
                            yield f"data: {json.dumps({'type':'input_json_delta','index':0,'delta': args_chunk}, ensure_ascii=False)}\n\n"

                elif delta.get('function_call'):  # 兼容旧格式
                    fc = delta.get('function_call', {})
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
                        args_chunk = fc.get('arguments', '')
                        if args_chunk:
                            yield f"data: {json.dumps({'type':'input_json_delta','index':0,'delta': args_chunk}, ensure_ascii=False)}\n\n"

                else:
                    # 普通文本内容
                    text_delta = delta.get('content', '')
                    if text_delta:
                        # 缓冲内容以提高性能
                        content_buffer.append(text_delta)
                        if len(''.join(content_buffer)) > 100:  # 每100字符发送一次
                            content_text = ''.join(content_buffer)
                            yield f"data: {json.dumps({'type':'content_block_delta','index':0,'delta':{'type':'text_delta','text': content_text}}, ensure_ascii=False)}\n\n"
                            content_buffer.clear()

                    # 发送缓冲的剩余内容
                    if content_buffer and choices[0].get('finish_reason'):
                        content_text = ''.join(content_buffer)
                        if content_text:
                            yield f"data: {json.dumps({'type':'content_block_delta','index':0,'delta':{'type':'text_delta','text': content_text}}, ensure_ascii=False)}\n\n"

            # 结束事件序列
            if tool_started:
                yield f"data: {json.dumps({'type':'content_block_stop','index':0}, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {json.dumps({'type':'content_block_stop','index':0}, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'type':'message_delta','delta':{'stop_reason':'end_turn'}}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type':'message_stop'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"SSE stream error: {str(e)}")
            err = {'type': 'error', 'error': {'type': 'stream_error', 'message': str(e)}}
            yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return sse_generator()


# 导入requests模块（在文件顶部导入）
import requests