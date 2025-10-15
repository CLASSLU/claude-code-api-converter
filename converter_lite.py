"""
轻量级转换器 - 只保留核心功能
专注于简单、快速的Anthropic到OpenAI格式转换
"""

import json
import logging
import uuid

# 设置极简日志 - 只记录错误
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


class LiteConverter:
    """轻量级转换器 - 简单、快速、透明"""

    def convert_messages(self, anthropic_messages):
        """Anthropic消息格式转为OpenAI格式"""
        openai_messages = []

        for message in anthropic_messages:
            role = message.get('role', 'user')
            content = message.get('content', '')

            # 角色映射
            openai_role = 'assistant' if role == 'assistant' else 'user'

            # 处理列表内容（工具调用）
            if isinstance(content, list):
                text_content = ''
                tool_calls = []

                for item in content:
                    if item.get('type') == 'text':
                        text_content += item.get('text', '')
                    elif item.get('type') == 'tool_use' and openai_role == 'assistant':
                        tool_calls.append({
                            'id': item.get('id', ''),
                            'type': 'function',
                            'function': {
                                'name': item.get('name', ''),
                                'arguments': json.dumps(item.get('input', {}))
                            }
                        })

                openai_message = {'role': openai_role, 'content': text_content if text_content else None}
                if tool_calls:
                    openai_message['tool_calls'] = tool_calls

            elif isinstance(content, str) and role == 'user':
                # 用户工具结果处理
                if '[Tool Result for' in content:
                    text_content = content
                else:
                    text_content = content
                openai_message = {'role': openai_role, 'content': text_content}
            else:
                # 普通文本
                openai_message = {'role': openai_role, 'content': content}

            openai_messages.append(openai_message)

        return openai_messages

    def convert_request(self, anthropic_request):
        """Anthropic请求格式转为OpenAI格式"""
        openai_request = {
            'model': anthropic_request.get('model', 'gpt-4'),
            'max_tokens': anthropic_request.get('max_tokens', 1024),
            'messages': [],
            'temperature': anthropic_request.get('temperature', 0.7)
        }

        # 处理系统消息
        if 'system' in anthropic_request:
            openai_request['messages'].insert(0, {
                'role': 'system',
                'content': anthropic_request['system']
            })

        # 转换消息
        anthropic_messages = anthropic_request.get('messages', [])
        openai_request['messages'].extend(self.convert_messages(anthropic_messages))

        # 转换工具定义
        if 'tools' in anthropic_request:
            openai_tools = []
            for tool in anthropic_request['tools']:
                openai_tool = {
                    "type": "function",
                    "function": {
                        "name": tool.get('name', ''),
                        "description": tool.get('description', ''),
                        "parameters": tool.get('input_schema', {})
                    }
                }
                openai_tools.append(openai_tool)
            openai_request['tools'] = openai_tools

        # 可选参数
        if 'tool_choice' in anthropic_request:
            openai_request['tool_choice'] = anthropic_request['tool_choice']

        return openai_request

    def convert_response(self, openai_response):
        """OpenAI响应格式转为Anthropic格式"""
        # 检查错误响应
        if not openai_response.get('choices'):
            raise Exception(f"OpenAI API error: {openai_response}")

        # 生成有效ID
        original_id = openai_response.get('id', '')
        response_id = f"msg_{original_id.replace('chat-', '')}" if original_id else f"msg_{uuid.uuid4().hex[:12]}"

        anthropic_response = {
            'id': response_id,
            'type': 'message',
            'role': 'assistant',
            'content': [],
            'model': openai_response.get('model', ''),
            'stop_reason': 'end_turn',
            'usage': {
                'input_tokens': openai_response.get('usage', {}).get('prompt_tokens', 0),
                'output_tokens': openai_response.get('usage', {}).get('completion_tokens', 0)
            }
        }

        # 转换内容
        choice = openai_response['choices'][0]
        message = choice.get('message', {})

        # 处理工具调用
        if 'tool_calls' in message:
            for tool_call in message['tool_calls']:
                function = tool_call.get('function', {})
                anthropic_response['content'].append({
                    'type': 'tool_use',
                    'id': tool_call.get('id', ''),
                    'name': function.get('name', ''),
                    'input': json.loads(function.get('arguments', '{}'))
                })
            anthropic_response['stop_reason'] = 'tool_use'
        else:
            # 处理文本响应（兼容reasoning_content字段）
            message_content = message.get('content') or message.get('reasoning_content', '')
            if message_content:
                anthropic_response['content'] = [{
                    'type': 'text',
                    'text': message_content
                }]

        # 转换停止原因
        finish_reason = choice.get('finish_reason', 'stop')
        stop_mapping = {
            'stop': 'end_turn',
            'length': 'max_tokens',
            'tool_calls': 'tool_use',
            'content_filter': 'stop_sequence'
        }
        anthropic_response['stop_reason'] = stop_mapping.get(finish_reason, 'end_turn')

        return anthropic_response