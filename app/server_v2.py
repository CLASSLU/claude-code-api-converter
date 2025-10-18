"""
轻量级API服务器 - 专注核心代理功能
简单、快速、透明
"""

from flask import Flask, request, jsonify, Response, stream_with_context
import os
import requests
import time
import uuid
import json
import threading
from queue import Queue
from datetime import datetime
from .converter import LiteConverter
from .config import LiteConfig
from .logger_setup import get_logger
from .monitoring import get_monitor, get_error_handler
from .claude_code_optimizer import get_claude_code_optimizer

# 初始化配置
config = LiteConfig()

# 初始化日志系统（使用配置文件中的日志设置）
log_config = config.config.get('logging', {})
logger = get_logger('api_server', log_config)

# 初始化
app = Flask(__name__)
converter = LiteConverter(model_mappings=config.config.get('model_mappings', []))

# Claude Code优化器
claude_optimizer = get_claude_code_optimizer()

class SmoothSSEStreamer:
    """平滑SSE数据流，避免脉冲式传输导致界面闪烁"""

    def __init__(self, buffer_size=5, flush_interval=0.03):
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval  # 30ms
        self.buffer = []
        self.last_flush_time = 0
        self.queue = Queue()
        self.logger = get_logger('sse_streamer')

    def add_data(self, data):
        """添加数据到缓冲区"""
        self.buffer.append(data)
        current_time = time.time()

        # 检查是否应该刷新缓冲区
        if (len(self.buffer) >= self.buffer_size or
            current_time - self.last_flush_time >= self.flush_interval or
            '[DONE]' in data):  # 结束标志立即刷新

            self._flush()
            self.last_flush_time = current_time

    def _flush(self):
        """刷新缓冲区"""
        if self.buffer:
            for data in self.buffer:
                self.queue.put(data)
            self.buffer.clear()

    def get_data_stream(self):
        """获取平滑的数据流生成器"""
        while True:
            try:
                data = self.queue.get(timeout=0.1)
                if data is None:  # 结束信号
                    break
                yield data
            except:
                # 超时时继续，这样可以平滑数据流
                continue

# 添加请求日志记录
@app.before_request
def log_request_info():
    """记录所有请求信息"""
    start_time = time.time()
    request.start_time = start_time  # 存储开始时间用于计算耗时

    # 检测Claude Code客户端
    claude_optimizer.detect_claude_code(request.headers)

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
        request_id=request.request_id
    )

@app.after_request
def log_response_info(response):
    """记录响应信息和处理时长"""
    if hasattr(request, 'start_time') and hasattr(request, 'request_id'):
        end_time = time.time()
        duration = (end_time - request.start_time) * 1000  # 转换为毫秒

        # 记录响应信息
        logger.log_response(
            status_code=response.status_code,
            duration_ms=duration,
            response_size=len(response.get_data()) if hasattr(response, 'get_data') else 0,
            request_id=request.request_id
        )

        # 记录请求完成
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

@app.route('/v1/messages', methods=['POST'])
def messages():
    """Anthropic消息API - Claude Code优化版"""
    request_start_time = time.time()
    monitor = get_monitor()
    error_handler = get_error_handler()

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
        if not anthropic_request.get('messages'):
            return jsonify({
                'type': 'error',
                'error': {
                    'type': 'invalid_request_error',
                    'message': 'Missing messages field'
                }
            }), 400

        # 检查是否为Claude Code客户端
        is_claude_code = claude_optimizer.should_optimize_response()

        # 转换为OpenAI格式
        openai_request = converter.anthropic_to_openai(anthropic_request)

        # 调用OpenAI API配置
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {config.get_openai_config()["api_key"]}'
        }

        def claude_code_optimized_sse_passthrough(upstream, first_line=None):
            """Claude Code优化的SSE传输"""
            request_start_time = time.time()
            monitor = get_monitor()
            error_handler = get_error_handler()

            # 使用Claude Code专用的智能流式传输器
            streamer = claude_optimizer.create_optimized_sse_streamer()

            try:
                # 发送标准事件头
                msg_id = f"msg_{uuid.uuid4().hex[:24]}"
                model_name = (anthropic_request.get('model') or '')
                start_data = json.dumps({'type':'message_start','message':{'id':msg_id,'type':'message','role':'assistant','content':[],'model':model_name}}, ensure_ascii=False)
                block_data = json.dumps({'type':'content_block_start','index':0,'content_block':{'type':'text','text':''}}, ensure_ascii=False)

                streamer.add_data(f"data: {start_data}\n\n")
                streamer.add_data(f"data: {block_data}\n\n")

            except Exception as e:
                error_response = error_handler.handle_stream_error(e, {'operation': 'sse_header_init'})
                streamer.add_data(f"data: {json.dumps(error_response, ensure_ascii=False)}\n\n")
                streamer.add_data("data: [DONE]\n\n")

            try:
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
                        streamer.add_data(f"data: [DONE]\n\n")
                        break

                    try:
                        evt = json.loads(payload)
                    except Exception:
                        continue

                    choices = evt.get('choices') or []
                    if choices:
                        delta = choices[0].get('delta') or {}
                        text_delta = delta.get('content') or ''
                        if text_delta:
                            # Claude Code优化：确保平滑传输
                            content_data = json.dumps({'type':'content_block_delta','index':0,'delta':{'type':'text_delta','text': text_delta}}, ensure_ascii=False)
                            streamer.add_data(f"data: {content_data}\n\n")

                # 结束事件序列
                stop_data = json.dumps({'type':'content_block_stop','index':0}, ensure_ascii=False)
                delta_data = json.dumps({'type':'message_delta','delta':{'stop_reason':'end_turn'}}, ensure_ascii=False)
                message_stop_data = json.dumps({'type':'message_stop'}, ensure_ascii=False)

                streamer.add_data(f"data: {stop_data}\n\n")
                streamer.add_data(f"data: {delta_data}\n\n")
                streamer.add_data(f"data: {message_stop_data}\n\n")

            except Exception as e:
                err = {'type': 'error', 'error': {'type': 'stream_error', 'message': str(e)}}
                streamer.add_data(f"data: {json.dumps(err, ensure_ascii=False)}\n\n")
                streamer.add_data("data: [DONE]\n\n")
            finally:
                # 记录性能指标
                request_duration = time.time() - request_start_time
                monitor.record_performance(
                    duration=request_duration,
                    success=True,
                    request_type='claude_code_sse_stream'
                )

                # 确保数据完全输出
                streamer._flush()
                streamer.queue.put(None)  # 结束信号

            # 返回优化的数据流
            return streamer.get_generator()

        # 检查是否需要流式响应
        client_wants_stream = anthropic_request.get('stream') is True

        if client_wants_stream:
            # 流式请求
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

                # 优化响应头
                if is_claude_code:
                    response_headers = claude_optimizer.optimize_response_headers(dict(response.headers))
                else:
                    response_headers = {
                        'Content-Type': 'text/event-stream',
                        'Cache-Control': 'no-cache',
                        'Connection': 'keep-alive'
                    }

                return Response(
                    claude_code_optimized_sse_passthrough(response),
                    headers=response_headers,
                    mimetype='text/event-stream'
                )

            except Exception as e:
                request_duration = time.time() - request_start_time
                monitor.record_error('stream_request_error', str(e), {
                    'duration': request_duration,
                    'is_claude_code': is_claude_code
                })
                monitor.record_performance(request_duration, success=False, request_type='stream')

                error_response = error_handler.handle_stream_error(e, {
                    'endpoint': 'messages_stream',
                    'duration': request_duration,
                    'is_claude_code': is_claude_code
                })

                return jsonify(error_response), 500

        else:
            # 非流式请求处理...
            # [这里保留原有的非流式处理逻辑]
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
                request_duration = time.time() - request_start_time
                monitor.record_error('non_stream_error', str(e), {'duration': request_duration})
                monitor.record_performance(request_duration, success=False, request_type='non_stream')

                error_response = error_handler.handle_stream_error(e, {'endpoint': 'messages_non_stream'})
                return jsonify(error_response), 500

    except Exception as e:
        request_duration = time.time() - request_start_time
        monitor.record_error('messages_endpoint_error', str(e), {
            'duration': request_duration,
            'request_data': anthropic_request
        })
        monitor.record_performance(request_duration, success=False, request_type='messages')

        error_response = error_handler.handle_stream_error(e, {
            'endpoint': 'messages',
            'duration': request_duration
        })

        return jsonify(error_response), 500

@app.route('/monitoring/stats', methods=['GET'])
def monitoring_stats():
    """监控统计信息端点"""
    monitor = get_monitor()
    stats = monitor.get_summary()
    return jsonify(stats), 200

if __name__ == '__main__':
    # 从配置文件读取服务器配置
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