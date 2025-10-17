"""
轻量级API服务器 - 专注核心代理功能
简单、快速、透明
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

# 初始化配置
config = LiteConfig()

# 初始化日志系统（使用配置文件中的日志设置）
log_config = config.config.get('logging', {})
logger = get_logger('api_server', log_config)

# 初始化
app = Flask(__name__)
converter = LiteConverter(model_mappings=config.config.get('model_mappings', []))

# 添加请求日志记录
@app.before_request
def log_request_info():
    """记录所有请求信息"""
    start_time = time.time()
    request.start_time = start_time  # 存储开始时间用于计算耗时
    
    # 生成请求链路追踪ID
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    request.request_id = request_id

    headers = None
    body = None

    # 在INFO和DEBUG级别都记录请求信息
    try:
        headers = dict(request.headers)
        if request.is_json:
            body = request.get_json(silent=True)
    except Exception:
        pass

    logger.log_request(
        method=request.method,
        path=request.full_path,
        client_ip=request.remote_addr,
        headers=headers,
        body=body,
        request_id=request_id
    )

@app.after_request
def log_response_info(response):
    """记录响应信息"""
    try:
        # 计算请求耗时
        duration_ms = (time.time() - request.start_time) * 1000 if hasattr(request, 'start_time') else None

        response_data = None
        # 在INFO和DEBUG级别都记录响应信息
        try:
            if response.content_type and 'json' in response.content_type:
                response_data = response.get_json(silent=True)
        except Exception:
            pass

        logger.log_response(
            status_code=response.status_code,
            response_data=response_data
        )

        if duration_ms:
            logger.info("Request completed in {:.2f}ms".format(duration_ms))

    except Exception:
        pass  # 静默处理日志异常

    return response


@app.route('/v1/messages', methods=['POST'])
def messages():
    """Anthropic消息API"""
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

        # 验证请求
        if 'messages' not in anthropic_request:
            return jsonify({
                'type': 'error',
                'error': {
                    'type': 'invalid_request_error',
                    'message': 'Missing required field: messages'
                }
            }), 400

        # 记录Anthropic请求
        logger.log_anthropic_request(anthropic_request, getattr(request, 'request_id', None))

        # 转换请求格式
        openai_request = converter.convert_request(anthropic_request)
        
        # 记录转换后的OpenAI请求
        logger.log_openai_request(openai_request, getattr(request, 'request_id', None))

        # 调用OpenAI API配置
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {config.get_openai_config()["api_key"]}'
        }

        def sse_passthrough(upstream, first_line=None):
            """将上游SSE转换为Anthropic Messages兼容事件序列"""
            # 发送标准事件头
            msg_id = f"msg_{uuid.uuid4().hex[:24]}"
            model_name = (anthropic_request.get('model') or '')
            yield f"data: {json.dumps({'type':'message_start','message':{'id':msg_id,'type':'message','role':'assistant','content':[],'model':model_name}}, ensure_ascii=False).encode('utf-8').decode('utf-8')}\n\n"
            yield f"data: {json.dumps({'type':'content_block_start','index':0,'content_block':{'type':'text','text':''}}, ensure_ascii=False).encode('utf-8').decode('utf-8')}\n\n"
            try:
                # 工具流式上下文
                tool_started = False
                tool_id = None
                tool_name = None
                # 若有首帧，先处理
                if first_line:
                    line = first_line.strip()
                    if line.startswith('data:'):
                        payload = line[5:].strip()
                        if payload != '[DONE]':
                            try:
                                evt = json.loads(payload)
                            except Exception:
                                evt = None
                            if isinstance(evt, dict):
                                choices = evt.get('choices') or []
                                if choices:
                                    delta = choices[0].get('delta') or {}

                                    # 优先处理 tool_calls（新格式），其次是 function_call（旧格式）
                                    tool_calls = delta.get('tool_calls', [])
                                    if tool_calls:
                                        for tool_call_delta in tool_calls:
                                            if not tool_started:
                                                tool_started = True
                                                tool_id = tool_call_delta.get('id', f"tool_{uuid.uuid4().hex[:24]}")

                                                # 获取函数信息
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
                                                    yield f"data: {json.dumps(start_evt, ensure_ascii=False).encode('utf-8').decode('utf-8')}\n\n"

                                                # 处理参数片段
                                                args_chunk = function_delta.get('arguments', '')
                                                if args_chunk:
                                                    yield f"data: {json.dumps({'type':'input_json_delta','index':0,'delta': args_chunk}, ensure_ascii=False).encode('utf-8').decode('utf-8')}\n\n"
                                    else:
                                        # 兼容旧的 function_call 格式
                                        fc = delta.get('function_call') or {}
                                        if fc.get('name'):
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
                                            yield f"data: {json.dumps(start_evt, ensure_ascii=False).encode('utf-8').decode('utf-8')}\n\n"
                                            args_chunk = fc.get('arguments') or ''
                                            if args_chunk:
                                                yield f"data: {json.dumps({'type':'input_json_delta','index':0,'delta': args_chunk}, ensure_ascii=False).encode('utf-8').decode('utf-8')}\n\n"
                                        else:
                                            text_delta = delta.get('content') or ''
                                            if text_delta:
                                                yield f"data: {json.dumps({'type':'content_block_delta','index':0,'delta':{'type':'text_delta','text': text_delta}}, ensure_ascii=False).encode('utf-8').decode('utf-8')}\n\n"
                # 继续读取其余帧
                for raw in upstream.iter_lines(decode_unicode=False):
                    if not raw:
                        continue
                    if isinstance(raw, bytes):
                        try:
                            line = raw.decode('utf-8', errors='replace').strip()
                        except Exception:
                            line = raw.decode('latin1', errors='replace').strip()
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
                        try:
                            evt = json.loads(payload.encode('latin1').decode('utf-8', errors='replace'))
                        except Exception:
                            continue
                    choices = evt.get('choices') or []
                    if choices:
                        delta = choices[0].get('delta') or {}

                        # 优先处理 tool_calls（新格式），其次是 function_call（旧格式）
                        tool_calls = delta.get('tool_calls', [])
                        if tool_calls:
                            for tool_call_delta in tool_calls:
                                if not tool_started:
                                    tool_started = True
                                    tool_id = tool_call_delta.get('id', f"tool_{uuid.uuid4().hex[:24]}")

                                    # 获取函数信息
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
                                        yield f"data: {json.dumps(start_evt, ensure_ascii=False).encode('utf-8').decode('utf-8')}\n\n"

                                    # 处理参数片段
                                    args_chunk = function_delta.get('arguments', '')
                                    if args_chunk:
                                        yield f"data: {json.dumps({'type':'input_json_delta','index':0,'delta': args_chunk}, ensure_ascii=False).encode('utf-8').decode('utf-8')}\n\n"
                        else:
                            # 兼容旧的 function_call 格式
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
                                    yield f"data: {json.dumps(start_evt, ensure_ascii=False).encode('utf-8').decode('utf-8')}\n\n"
                                args_chunk = fc.get('arguments') or ''
                                if args_chunk:
                                    yield f"data: {json.dumps({'type':'input_json_delta','index':0,'delta': args_chunk}, ensure_ascii=False).encode('utf-8').decode('utf-8')}\n\n"
                            else:
                                text_delta = delta.get('content') or ''
                                if text_delta:
                                    yield f"data: {json.dumps({'type':'content_block_delta','index':0,'delta':{'type':'text_delta','text': text_delta}}, ensure_ascii=False).encode('utf-8').decode('utf-8')}\n\n"
                # 结束事件序列
                if tool_started:
                    yield f"data: {json.dumps({'type':'content_block_stop','index':0}, ensure_ascii=False).encode('utf-8').decode('utf-8')}\n\n"
                else:
                    yield f"data: {json.dumps({'type':'content_block_stop','index':0}, ensure_ascii=False).encode('utf-8').decode('utf-8')}\n\n"
                yield f"data: {json.dumps({'type':'message_delta','delta':{'stop_reason':'end_turn'}}, ensure_ascii=False).encode('utf-8').decode('utf-8')}\n\n"
                yield f"data: {json.dumps({'type':'message_stop'}, ensure_ascii=False).encode('utf-8').decode('utf-8')}\n\n"
                yield "data: [DONE]\n\n"
            except GeneratorExit:
                return
            except Exception as e:
                err = {'type': 'error', 'error': {'type': 'stream_error', 'message': str(e)}}
                yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"

        # 🔥 关键修复：对于非流式请求，使用非流式方式调用上游
        # 只有在客户端明确请求流式时才使用stream=True
        client_wants_stream = anthropic_request.get('stream') is True
        ua = (request.headers.get('User-Agent') or '')
        is_claude_code = ('claude' in ua.lower() and ('code' in ua.lower() or 'editor' in ua.lower()))

        # 对 Claude Code 客户端，除非明确请求 stream=true，否则强制走非流式JSON
        if is_claude_code and not client_wants_stream:
            client_wants_stream = False

        if client_wants_stream:
            # 流式请求：使用stream=True
            sse_headers = dict(headers)
            sse_headers['Accept'] = 'text/event-stream'
            sse_headers['Accept-Charset'] = 'utf-8'
            try:
                upstream = requests.post(
                    f'{config.get_openai_config()["base_url"]}/chat/completions',
                    headers=sse_headers,
                    json=openai_request,
                    timeout=60,
                    stream=True
                )
            except Exception as e:
                return jsonify({'type':'error','error':{'type':'api_connection_error','message':str(e)}}), 502

            # 检查流式响应状态
            if upstream.status_code != 200:
                # 流式错误处理
                def sse_err():
                    try:
                        error_msg = upstream.text
                    except RuntimeError:
                        error_msg = f"Upstream server returned error status code: {upstream.status_code}"
                    err = {'type':'error','error':{'type':'api_error','message': error_msg}}
                    yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                return Response(sse_err(), mimetype='text/event-stream', headers={'Cache-Control':'no-cache','Connection':'keep-alive','X-Accel-Buffering':'no'})

            # 直接返回流式响应
            return Response(
                sse_passthrough(upstream),
                mimetype='text/event-stream',
                headers={'Content-Type':'text/event-stream; charset=utf-8','Cache-Control':'no-cache','Connection':'keep-alive','X-Accel-Buffering':'no'}
            )

        else:
            # 非流式请求：先尝试非流式方式，如果上游返回SSE则自动处理
            try:
                # 明确请求非流式响应
                headers_no_stream = dict(headers)
                headers_no_stream['Accept'] = 'application/json'

                nonstream_resp = requests.post(
                    f'{config.get_openai_config()["base_url"]}/chat/completions',
                    headers=headers_no_stream,
                    json=openai_request,
                    timeout=60
                )
            except Exception as e:
                return jsonify({'type':'error','error':{'type':'api_connection_error','message':str(e)}}), 502

            if nonstream_resp.status_code != 200:
                return jsonify({'type':'error','error':{'type':'api_error','message': nonstream_resp.text}}), nonstream_resp.status_code

            # 检查上游是否返回了SSE流
            content_type = (nonstream_resp.headers.get('Content-Type') or '').lower()

            if 'event-stream' in content_type:
                # 上游返回SSE，我们需要消费流式响应并聚合为JSON
                logger.debug("Upstream returned SSE, starting aggregation")
                text_content = ''
                tool_calls_dict = {}  # 使用字典按索引聚合工具调用

                try:
                    for line in nonstream_resp.iter_lines(decode_unicode=False):
                        if not line or not line.startswith(b'data:'):
                            continue

                        # 安全解码字节行
                        try:
                            line_str = line.decode('utf-8', errors='replace')
                        except Exception:
                            line_str = line.decode('latin1', errors='replace')

                        payload = line_str[5:].strip()
                        if payload == '[DONE]':
                            break

                        try:
                            event_data = json.loads(payload)
                            choices = event_data.get('choices', [])
                            if choices:
                                delta = choices[0].get('delta', {})

                                # 处理文本内容
                                content = delta.get('content', '')
                                if content:
                                    text_content += content

                                # 处理工具调用 - 正确聚合流式片段
                                if 'tool_calls' in delta:
                                    for tool_call_delta in delta['tool_calls']:
                                        index = tool_call_delta.get('index', 0)

                                        # 初始化工具调用条目
                                        if index not in tool_calls_dict:
                                            tool_calls_dict[index] = {
                                                'id': '',
                                                'type': 'function',
                                                'function': {
                                                    'name': '',
                                                    'arguments': ''
                                                }
                                            }

                                        # 聚合各个字段
                                        current_call = tool_calls_dict[index]

                                        if 'id' in tool_call_delta:
                                            current_call['id'] = tool_call_delta['id']

                                        if 'function' in tool_call_delta:
                                            function_delta = tool_call_delta['function']
                                            if 'name' in function_delta:
                                                current_call['function']['name'] = function_delta['name']
                                            if 'arguments' in function_delta:
                                                current_call['function']['arguments'] += function_delta['arguments']

                        except json.JSONDecodeError:
                            continue

                    # 转换字典为列表并排序
                    tool_calls_data = [tool_calls_dict[i] for i in sorted(tool_calls_dict.keys())]

                    # 构造OpenAI格式的响应
                    openai_response = {
                        'id': f"chatcmpl-{uuid.uuid4().hex[:12]}",
                        'object': 'chat.completion',
                        'created': int(time.time()),
                        'model': openai_request.get('model', 'gpt-4'),
                        'choices': [{
                            'index': 0,
                            'message': {
                                'role': 'assistant',
                                'content': text_content if text_content else None,
                                'tool_calls': tool_calls_data if tool_calls_data else []
                            },
                            'finish_reason': 'tool_calls' if tool_calls_data else 'stop'
                        }],
                        'usage': {
                            'prompt_tokens': 0,
                            'completion_tokens': len(text_content) // 4,
                            'total_tokens': len(text_content) // 4
                        }
                    }

                except Exception as e:
                    logger.error(f"Error processing SSE response: {e}")
                    return jsonify({'type':'error','error':{'type':'sse_processing_error','message': str(e)}}), 500

            else:
                # 正常JSON响应
                try:
                    openai_response = nonstream_resp.json()
                except Exception as e:
                    logger.error(f"Failed to parse JSON response: {e}, response content: {nonstream_resp.text[:200]}")
                    return jsonify({'type':'error','error':{'type':'invalid_response_format','message': 'Upstream returned non-JSON'}}), 500

            # 记录OpenAI原始响应
            logger.log_openai_response(openai_response, getattr(request, 'request_id', None))

            anthropic_response = converter.convert_response(openai_response)
            anthropic_response['model'] = anthropic_request.get('model', 'claude-3-sonnet-20240229')
            
            # 记录转换后的Anthropic响应
            logger.log_anthropic_response(anthropic_response, getattr(request, 'request_id', None))
            
            return jsonify(anthropic_response)


    except Exception as e:
        logger.log_exception(e, "messages endpoint")
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
        openai_request = request.get_json(silent=True)
        if not isinstance(openai_request, dict):
            return jsonify({
                'error': {
                    'message': 'Invalid JSON body',
                    'type': 'invalid_request_error'
                }
            }), 400

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
        logger.log_exception(e, "messages endpoint")
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
    except Exception as e:
        logger.log_exception(e, "models endpoint")
        # 确保即使出错也返回有效的结构
        return jsonify({
            "object": "list",
            "data": [
                {"id": "gpt-4", "object": "model", "created": 1707879684},
                {"id": "gpt-3.5-turbo", "object": "model", "created": 1707879684}
            ]
        })


@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({"status": "healthy"})


@app.route('/config', methods=['GET'])
def get_config():
    """获取配置"""
    return jsonify(config.config)


@app.route('/v1/messages/count_tokens', methods=['POST'])
def count_tokens():
    """计算token数量（Anthropic API兼容）"""
    try:
        anthropic_request = request.get_json()

        # 验证必需字段
        if 'messages' not in anthropic_request and 'text' not in anthropic_request:
            return jsonify({
                'type': 'error',
                'error': {
                    'type': 'invalid_request_error',
                    'message': 'Missing required field: messages or text'
                }
            }), 400

        # 简单的token估算（实际应该使用tiktoken）
        text = ""
        if 'messages' in anthropic_request:
            for message in anthropic_request['messages']:
                if isinstance(message.get('content'), str):
                    text += message['content']
                elif isinstance(message.get('content'), list):
                    for content in message['content']:
                        if content.get('type') == 'text':
                            text += content.get('text', '')
        elif 'text' in anthropic_request:
            text = anthropic_request['text']

        # 简单估算：大约4个字符 = 1个token
        estimated_tokens = max(1, len(text) // 4)

        return jsonify({
            "input_tokens": estimated_tokens
        })

    except Exception as e:
        return jsonify({
            'type': 'error',
            'error': {
                'type': 'token_calculation_error',
                'message': str(e)
            }
        }), 500


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


@app.route('/shutdown', methods=['POST'])
def shutdown():
    shutdown_server = request.environ.get('werkzeug.server.shutdown')
    if shutdown_server is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    shutdown_server()
    return 'Server shutting down...'


if __name__ == '__main__':
    server_config = config.get_server_config()

    logger.info("Starting lightweight API server...")
    logger.info("Address: http://{}:{}/".format(server_config['host'], server_config['port']))
    logger.info("Environment: {}", os.getenv('FLASK_ENV', 'production'))
    logger.info("Log level: {}", logger.level)
    logger.info("Environment variable configuration supported")

    try:
        app.run(
            host=server_config['host'],
            port=server_config['port'],
            debug=server_config['debug']
        )
    except Exception as e:
        logger.log_exception(e, "server startup")
        raise
