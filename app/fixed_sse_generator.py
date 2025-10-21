# -*- coding: utf-8 -*-
"""
修复后的SSE生成器 - 解决Claude Code UI闪烁问题
主要修复：
1. 正确的content_block_index管理
2. 完整的事件序列
3. 符合Anthropic官方规范的事件格式
4. 适当的事件延迟控制
"""

import json
import time
import uuid
from typing import Generator, Dict, Any, Optional
from .logger_setup import get_logger

class FixedSSEGenerator:
    """修复后的SSE生成器"""

    def __init__(self, model_name: str, enable_delay: bool = True):
        self.model_name = model_name
        self.enable_delay = enable_delay
        self.content_block_index = 0
        self.current_text_block = None
        self.current_tool_block = None
        self.logger = get_logger()  # 使用主logger确保日志输出

    def _create_message_start(self, input_tokens: int = 0) -> str:
        """创建符合规范的message_start事件"""
        msg_id = f"msg_{uuid.uuid4().hex[:24]}"
        event = {
            'type': 'message_start',
            'message': {
                'id': msg_id,
                'type': 'message',
                'role': 'assistant',
                'content': [],
                'model': self.model_name,
                'stop_reason': None,
                'stop_sequence': None,
                'usage': {
                    'input_tokens': input_tokens,
                    'output_tokens': 0
                }
            }
        }
        return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    def _create_content_block_start(self, block_type: str, **kwargs) -> str:
        """创建content_block_start事件"""
        content_block = {'type': block_type}

        if block_type == 'text':
            content_block['text'] = ''
            self.current_text_block = self.content_block_index
        elif block_type == 'tool_use':
            content_block.update({
                'id': kwargs.get('id', f"tool_{uuid.uuid4().hex[:24]}"),
                'name': kwargs.get('name', ''),
                'input': kwargs.get('input', {})
            })
            self.current_tool_block = self.content_block_index

        event = {
            'type': 'content_block_start',
            'index': self.content_block_index,
            'content_block': content_block
        }

        self.content_block_index += 1
        return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    def _create_content_block_delta(self, index: int, delta_type: str, content: str) -> str:
        """创建content_block_delta事件"""
        delta = {'type': delta_type}

        if delta_type == 'text_delta':
            delta['text'] = content
        elif delta_type == 'input_json_delta':
            delta['partial_json'] = content

        event = {
            'type': 'content_block_delta',
            'index': index,
            'delta': delta
        }
        return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    def _create_content_block_stop(self, index: int) -> str:
        """创建content_block_stop事件"""
        event = {
            'type': 'content_block_stop',
            'index': index
        }
        return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    def _create_message_delta(self, stop_reason: str, output_tokens: int) -> str:
        """创建符合规范的message_delta事件"""
        event = {
            'type': 'message_delta',
            'delta': {
                'stop_reason': stop_reason,
                'stop_sequence': None
            },
            'usage': {
                'output_tokens': output_tokens
            }
        }
        return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    def _create_message_stop(self) -> str:
        """创建message_stop事件"""
        event = {'type': 'message_stop'}
        return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    def _create_done(self) -> str:
        """创建DONE标记"""
        return "data: [DONE]\n\n"

    def _add_delay(self):
        """添加适当的延迟"""
        if self.enable_delay:
            time.sleep(0.01)  # 10ms延迟

    def get_delay_config(self) -> bool:
        """获取延迟配置状态"""
        return self.enable_delay

    def _create_error_response(self, status_code: int, message: str) -> str:
        """创建错误响应事件"""
        error_event = {
            'type': 'error',
            'error': {
                'type': 'rate_limit_error' if status_code == 429 else 'api_error',
                'message': message,
                'status_code': status_code
            }
        }
        return f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"

    def _create_rate_limit_error_stream(self, message: str = "Rate limit exceeded") -> Generator[str, None, None]:
        """创建完整的429错误SSE流，避免UI闪烁"""
        # 1. 创建content_block_start
        yield self._create_content_block_start('text')

        # 2. 创建包含错误信息的content_block_delta
        error_text = f"[错误] {message}，请稍后重试"
        yield self._create_content_block_delta(0, 'text_delta', error_text)

        # 3. 创建content_block_stop
        yield self._create_content_block_stop(self.current_text_block)

        # 4. 创建message_delta
        yield self._create_message_delta(stop_reason="end_turn", output_tokens=1)

        # 5. 创建message_stop
        yield self._create_message_stop()

        # 6. 创建[DONE]
        yield self._create_done()

    def generate_fixed_sse_stream(self, upstream_response, input_tokens: int = 0) -> Generator[str, None, None]:
        """生成修复后的SSE流"""

        # 强制调试输出
        self.logger.info(f"[FIXED_SSE_DEBUG] Starting generate_fixed_sse_stream with model={self.model_name}, input_tokens={input_tokens}")

        # 1. 发送message_start
        message_start = self._create_message_start(input_tokens)
        self.logger.info(f"[FIXED_SSE_DEBUG] Yielding: {message_start.strip()}")
        yield message_start
        self._add_delay()

        try:
            # 状态跟踪
            text_started = False
            text_finished = False
            tool_started = False
            tool_name = None
            tool_id = None
            accumulated_text = ""
            accumulated_tool_args = ""

            # 2. 处理上游流式数据
            event_count = 0
            self.logger.info(f"[FIXED_SSE_DEBUG] Starting upstream data processing loop")

            # 添加上游响应错误检查
            if hasattr(upstream_response, 'status_code'):
                status_code = upstream_response.status_code
                if status_code != 200:
                    self.logger.info(f"[FIXED_SSE_DEBUG] Upstream API returned status code: {status_code}")
                    # 处理上游API错误情况
                    # 429和449都视为限流错误，统一转换为429
                    if status_code in [429, 449]:
                        converted_status = 429
                        self.logger.info(f"[FIXED_SSE_DEBUG] Converting {status_code} to {converted_status} error stream to avoid UI flicker")
                        for event in self._create_rate_limit_error_stream():
                            yield event
                        return
                    else:
                        yield self._create_error_response(status_code, "Upstream API error")
                        return

            for raw in upstream_response.iter_lines(decode_unicode=False):
                if not raw:
                    continue

                # 解码处理
                if isinstance(raw, bytes):
                    line = raw.decode('utf-8', errors='replace').strip()
                else:
                    line = raw.strip()

                self.logger.info(f"[FIXED_SSE_DEBUG] Raw line: {line}")

                # 检查是否是直接的响应（不以data:开头）
                if not line.startswith('data:'):
                    # 检查是否是429或449错误格式（上游限流错误）
                    rate_limit_patterns = [
                        '"status":"429"', '"status": "429"',
                        '"status":"449"', '"status": "449"',
                        'rate limit', 'Rate limit',
                        'exceeded.*limit', 'limit.*exceeded'
                    ]

                    is_rate_limit_error = any(pattern in line for pattern in rate_limit_patterns)

                    if is_rate_limit_error:
                        self.logger.info(f"[FIXED_SSE_DEBUG] Detected rate limit error in non-SSE format: {line}")
                        # 尝试解析JSON
                        try:
                            error_data = json.loads(line)
                            message = error_data.get('msg', 'Rate limit exceeded')
                            status = error_data.get('status', '429')

                            # 统一转换为429错误
                            if status in ['429', '449']:
                                self.logger.info(f"[FIXED_SSE_DEBUG] Converting {status} to 429 error stream for non-SSE response")
                                for event in self._create_rate_limit_error_stream(message):
                                    yield event
                                return
                        except Exception as e:
                            self.logger.info(f"[FIXED_SSE_DEBUG] Failed to parse rate limit error: {e}")
                            # 使用默认错误消息
                            for event in self._create_rate_limit_error_stream():
                                yield event
                            return

                    # 检查是否是正常的OpenAI非流式响应
                    elif '"choices"' in line and '"message"' in line:
                        self.logger.info(f"[FIXED_SSE_DEBUG] Detected OpenAI non-streaming response: {line[:100]}...")
                        try:
                            response_data = json.loads(line)
                            choices = response_data.get('choices', [])
                            if choices:
                                choice = choices[0]
                                message = choice.get('message', {})

                                # 处理文本内容
                                content = message.get('content', '') or message.get('reasoning_content', '')
                                if content:
                                    self.logger.info(f"[FIXED_SSE_DEBUG] Processing non-streaming content: {content[:50]}...")
                                    # 创建完整的文本SSE流
                                    yield self._create_content_block_start('text')
                                    yield self._create_content_block_delta(0, 'text_delta', content)
                                    yield self._create_content_block_stop(self.current_text_block)

                                # 处理工具调用
                                tool_calls = message.get('tool_calls', [])
                                if tool_calls:
                                    for tool_call in tool_calls:
                                        # 修复工具调用参数错误
                                        function_info = tool_call.get('function', {})
                                        yield self._create_content_block_start(
                                            'tool_use',
                                            id=tool_call.get('id', f"tool_{uuid.uuid4().hex[:24]}"),
                                            name=function_info.get('name', ''),
                                            input={}
                                        )
                                        # 处理工具参数
                                        args_str = function_info.get('arguments', '{}')
                                        if args_str:
                                            yield self._create_content_block_delta(
                                                self.current_tool_block,
                                                'input_json_delta',
                                                args_str
                                            )
                                        yield self._create_content_block_stop(self.current_tool_block)

                                # 结束消息
                                usage = response_data.get('usage', {})
                                output_tokens = usage.get('completion_tokens', 1)
                                yield self._create_message_delta(choice.get('finish_reason', 'end_turn'), output_tokens)
                                yield self._create_message_stop()
                                yield self._create_done()
                                return

                        except Exception as e:
                            self.logger.info(f"[FIXED_SSE_DEBUG] Failed to process non-streaming response: {e}")
                            continue
                    else:
                        continue

                payload = line[5:].strip()
                if payload == '[DONE]':
                    self.logger.info(f"[FIXED_SSE_DEBUG] Received [DONE] after {event_count} events")
                    break

                # 检查是否是错误响应
                try:
                    evt = json.loads(payload)
                    self.logger.info(f"[FIXED_SSE_DEBUG] Parsed JSON: {evt}")
                except Exception as e:
                    self.logger.info(f"[FIXED_SSE_DEBUG] Failed to parse JSON: {e}, payload: {payload}")
                    continue

                # 检查是否是错误格式的响应
                if 'status' in evt and ('msg' in evt or 'message' in evt):
                    status = evt.get('status', '429')
                    message = evt.get('msg') or evt.get('message', 'Rate limit exceeded')
                    self.logger.info(f"[FIXED_SSE_DEBUG] Detected error response: {evt}")

                    # 处理限流错误：429、449都转换为429
                    rate_limit_statuses = ['429', '449']
                    is_rate_limit = (
                        status in rate_limit_statuses or
                        'rate limit' in message.lower() or
                        'exceeded' in message.lower() and 'limit' in message.lower()
                    )

                    if is_rate_limit:
                        # 统一转换为标准的429限流错误
                        converted_status = '429'
                        self.logger.info(f"[FIXED_SSE_DEBUG] Converting {status} to {converted_status} rate limit error stream")
                        for event in self._create_rate_limit_error_stream(message):
                            yield event
                        return
                    else:
                        # 其他错误类型
                        yield self._create_error_response(int(status), message)
                        yield self._create_done()
                        return
                else:
                    self.logger.info(f"[FIXED_SSE_DEBUG] Not an error response, processing normally")

                choices = evt.get('choices') or []
                if not choices:
                    self.logger.debug(f"[FIXED_SSE_DEBUG] No choices in event: {evt}")
                    continue

                choice = choices[0]

                # 检查是否是流式响应还是非流式响应
                if 'delta' in choice:
                    # 流式响应
                    delta = choice.get('delta') or {}
                    self.logger.info(f"[FIXED_SSE_DEBUG] Processing streaming delta: {delta}")
                elif 'message' in choice:
                    # 非流式响应 - 转换为流式格式
                    message = choice.get('message', {})
                    content = message.get('content', '') or message.get('reasoning_content', '')

                    if content:
                        self.logger.info(f"[FIXED_SSE_DEBUG] Processing non-streaming message content: {content[:50]}...")

                        # 将完整内容作为一个delta处理
                        delta = {'content': content}
                    else:
                        delta = {}
                else:
                    delta = {}

                event_count += 1
                self.logger.info(f"[FIXED_SSE_DEBUG] Event {event_count}: delta={delta}")

                # 处理工具调用
                tool_calls = delta.get('tool_calls', [])
                if tool_calls:
                    for tool_call_delta in tool_calls:
                        # 如果还没开始文本块，先结束文本块
                        if text_started and not text_finished:
                            yield self._create_content_block_stop(self.current_text_block)
                            text_finished = True
                            self._add_delay()

                        # 开始工具调用块
                        if not tool_started:
                            tool_started = True
                            function_delta = tool_call_delta.get('function', {})
                            tool_name = function_delta.get('name', '')
                            tool_id = tool_call_delta.get('id', f"tool_{uuid.uuid4().hex[:24]}")

                            if tool_name:
                                yield self._create_content_block_start(
                                    'tool_use',
                                    id=tool_id,
                                    name=tool_name,
                                    input={}
                                )
                                self._add_delay()

                        # 处理工具参数
                        args_chunk = function_delta.get('arguments', '')
                        if args_chunk:
                            accumulated_tool_args += args_chunk
                            yield self._create_content_block_delta(
                                self.current_tool_block,
                                'input_json_delta',
                                args_chunk
                            )
                            self._add_delay()

                # 处理普通文本内容
                elif delta.get('function_call'):
                    # 兼容旧格式
                    fc = delta.get('function_call') or {}
                    if fc.get('name'):
                        # 如果还没开始文本块，先结束文本块
                        if text_started and not text_finished:
                            yield self._create_content_block_stop(self.current_text_block)
                            text_finished = True
                            self._add_delay()

                        if not tool_started:
                            tool_started = True
                            tool_name = fc.get('name')
                            tool_id = f"tool_{uuid.uuid4().hex[:24]}"

                            yield self._create_content_block_start(
                                'tool_use',
                                id=tool_id,
                                name=tool_name,
                                input={}
                            )
                            self._add_delay()

                        args_chunk = fc.get('arguments') or ''
                        if args_chunk:
                            accumulated_tool_args += args_chunk
                            yield self._create_content_block_delta(
                                self.current_tool_block,
                                'input_json_delta',
                                args_chunk
                            )
                            self._add_delay()

                else:
                    # 普通文本内容 - 支持reasoning_content和content
                    text_delta = delta.get('content') or delta.get('reasoning_content') or ''
                    if text_delta:
                        if not text_started:
                            text_started = True
                            yield self._create_content_block_start('text')
                            self._add_delay()

                        accumulated_text += text_delta
                        yield self._create_content_block_delta(
                            self.current_text_block,
                            'text_delta',
                            text_delta
                        )
                        self._add_delay()

            # 3. 确保所有块都正确结束
            if text_started and not text_finished:
                yield self._create_content_block_stop(self.current_text_block)
                self._add_delay()

            if tool_started:
                yield self._create_content_block_stop(self.current_tool_block)
                self._add_delay()

            # 4. 发送结束事件
            stop_reason = 'tool_use' if tool_started else 'end_turn'
            output_tokens = len(accumulated_text.split()) + len(accumulated_tool_args.split()) // 4  # 简单估算

            yield self._create_message_delta(stop_reason, max(1, output_tokens))
            self._add_delay()

            yield self._create_message_stop()
            self._add_delay()

            yield self._create_done()

        except Exception as e:
            # 错误处理
            error_event = {
                'type': 'error',
                'error': {
                    'type': 'stream_error',
                    'message': str(e)
                }
            }
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
            yield self._create_done()


def create_fixed_sse_generator(upstream_response, model_name: str, input_tokens: int = 0, enable_delay: bool = True):
    """创建修复后的SSE生成器的便捷函数"""
    logger = get_logger()  # 使用主logger
    logger.info(f"[FIXED_SSE_DEBUG] create_fixed_sse_generator called with model={model_name}, input_tokens={input_tokens}")

    generator = FixedSSEGenerator(model_name, enable_delay)
    logger.info(f"[FIXED_SSE_DEBUG] FixedSSEGenerator created, starting stream generation")

    return generator.generate_fixed_sse_stream(upstream_response, input_tokens)