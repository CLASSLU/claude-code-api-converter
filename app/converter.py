"""
轻量级转换器 - 只保留核心功能
专注于简单、快速的Anthropic到OpenAI格式转换
"""

import json
import logging
import uuid
import re

# 设置极简日志 - 只记录错误
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


class LiteConverter:
    """轻量级转换器 - 简单、快速、透明"""

    def __init__(self, model_mappings=None):
        self.model_mappings = model_mappings or []

    def get_mapped_model(self, anthropic_model):
        """获取映射后的OpenAI模型名称"""
        if not self.model_mappings:
            return anthropic_model

        for mapping in self.model_mappings:
            if mapping.get('anthropic') == anthropic_model:
                return mapping.get('openai', anthropic_model)

        return anthropic_model

    def convert_messages(self, anthropic_messages):
        """Anthropic消息格式转为OpenAI格式"""
        openai_messages = []

        for message in anthropic_messages:
            role = message.get('role', 'user')
            content = message.get('content', '')

            # 角色映射
            openai_role = 'assistant' if role == 'assistant' else 'user'

            # 处理列表内容（工具调用和工具结果）
            if isinstance(content, list):
                # 检查是否包含工具调用或工具结果
                has_tool_calls = any(item.get('type') in ['tool_use', 'tool_result'] for item in content)

                if has_tool_calls and role == 'assistant':
                    # 处理助手工具调用，转换为OpenAI格式
                    tool_calls = []
                    text_content = ''

                    for item in content:
                        if item.get('type') == 'tool_use':
                            tool_calls.append({
                                'id': item.get('id', ''),
                                'type': 'function',
                                'function': {
                                    'name': item.get('name', ''),
                                    'arguments': json.dumps(item.get('input', {}))
                                }
                            })
                        elif item.get('type') == 'text':
                            text_content += item.get('text', '')

                    openai_message = {'role': openai_role, 'content': text_content if text_content else None}
                    if tool_calls:
                        openai_message['tool_calls'] = tool_calls

                elif has_tool_calls and role == 'user':
                    # 处理用户工具结果，转换为OpenAI role=tool
                    openai_message = {'role': 'tool', 'content': ''}
                    for item in content:
                        if item.get('type') == 'tool_result':
                            openai_message['tool_call_id'] = item.get('tool_use_id', '')
                            # 支持 JSON 或文本结果
                            result_content = item.get('content', '')
                            if isinstance(result_content, (dict, list)):
                                openai_message['content'] = json.dumps(result_content, ensure_ascii=False)
                            else:
                                openai_message['content'] = str(result_content)
                        elif item.get('type') == 'text' and not openai_message['content']:
                            openai_message['content'] = item.get('text', '')

                else:
                    # 普通文本内容处理
                    text_content = ''
                    for item in content:
                        if item.get('type') == 'text':
                            text_content += item.get('text', '')

                    openai_message = {'role': openai_role, 'content': text_content}

            elif isinstance(content, str):
                # 普通字符串内容
                openai_message = {'role': openai_role, 'content': content}
            else:
                # 普通文本
                openai_message = {'role': openai_role, 'content': content}

            openai_messages.append(openai_message)

        return openai_messages

    def convert_request(self, anthropic_request):
        """Anthropic请求格式转为OpenAI格式"""
        anthropic_model = anthropic_request.get('model', 'gpt-4')
        openai_model = self.get_mapped_model(anthropic_model)

        openai_request = {
            'model': openai_model,
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
        tool_calls = message.get('tool_calls')
        if tool_calls:
            for tool_call in tool_calls:
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
                # 尝试从文本中解析工具调用
                parsed_tools = self._parse_tools_from_text(message_content)

                if parsed_tools:
                    # 找到了工具调用，转换为Anthropic格式
                    for tool in parsed_tools:
                        anthropic_response['content'].append({
                            'type': 'tool_use',
                            'id': f"toolu_{uuid.uuid4().hex[:24]}",
                            'name': tool['name'],
                            'input': tool['arguments']
                        })
                    anthropic_response['stop_reason'] = 'tool_use'
                else:
                    # 普通文本响应
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

    def _parse_tools_from_text(self, text):
        """从文本中解析工具调用

        支持多种格式：
        1. <function=tool.name><parameter=key>value</parameter></function>
        2. <function=execute><name=tool.name</name><parameter=string>{"key": "value"}</parameter></function>
        3. [{"name": "tool_name", "arguments": "{\"key\": \"value\"}"}]
        """
        tools = []

        # 格式1: <function=tool.name><parameter=key>value</parameter></function>
        pattern1 = r'<function=([^>]+)>(.*?)</function>'
        matches1 = re.findall(pattern1, text, re.DOTALL)

        for tool_name, params_block in matches1:
            tool_name = tool_name.strip()
            if not tool_name:
                continue

            # 清理工具名称，移除前缀
            if '.' in tool_name:
                tool_name = tool_name.split('.')[-1]

            # 解析参数
            param_pattern = r'<parameter=([^>]+)>(.*?)</parameter>'
            param_matches = re.findall(param_pattern, params_block, re.DOTALL)

            arguments = {}
            for param_name, param_value in param_matches:
                param_name = param_name.strip()
                param_value = param_value.strip()

                # 尝试解析为JSON，否则保持字符串
                try:
                    arguments[param_name] = json.loads(param_value)
                except:
                    arguments[param_name] = param_value

            tools.append({
                'name': tool_name,
                'arguments': arguments
            })

        if tools:
            return tools

        # 格式2: <function=execute><name=tool.name</name><parameter=string>{"key": "value"}</parameter></function>
        pattern2 = r'<function=execute><name=([^>]+)</name><parameter=string>([^<]+)</parameter></function>'
        matches2 = re.findall(pattern2, text, re.DOTALL)

        for tool_name, args_json in matches2:
            tool_name = tool_name.strip()
            if not tool_name:
                continue

            # 清理工具名称
            if '.' in tool_name:
                tool_name = tool_name.split('.')[-1]

            try:
                arguments = json.loads(args_json)
            except:
                arguments = {}

            tools.append({
                'name': tool_name,
                'arguments': arguments
            })

        if tools:
            return tools

        # 格式3: <tool_code>function_name(arg1='value1', arg2="value2")</tool_code>
        pattern3 = r'<tool_code>([^<]+)</tool_code>'
        matches3 = re.findall(pattern3, text)

        for tool_call in matches3:
            tool_call = tool_call.strip()
            if not tool_call:
                continue

            # 解析 function_name(args) 格式
            match = re.match(r'(\w+)\s*\(([^)]*)\)', tool_call)
            if match:
                tool_name = match.group(1)
                args_str = match.group(2)

                # 清理工具名称
                if '.' in tool_name:
                    tool_name = tool_name.split('.')[-1]

                # 解析参数
                arguments = {}
                if args_str.strip():
                    try:
                        # 简单的参数解析，支持 key='value' 和 key="value" 格式
                        arg_pattern = r'(\w+)\s*=\s*["\']([^"\']*)["\']'
                        arg_matches = re.findall(arg_pattern, args_str)
                        for key, value in arg_matches:
                            arguments[key] = value
                    except:
                        pass

                tools.append({
                    'name': tool_name,
                    'arguments': arguments
                })

        if tools:
            return tools

        # 格式4: JSON代码块格式 ```json{"tool_name": "...", "parameters": {...}}```
        pattern4 = r'```json\s*({[^`]+})\s*```'
        matches4 = re.findall(pattern4, text, re.DOTALL)

        for json_block in matches4:
            try:
                tool_data = json.loads(json_block)
                tool_name = tool_data.get('tool_name', '')
                parameters = tool_data.get('parameters', {})

                if tool_name:
                    # 清理工具名称
                    if '.' in tool_name:
                        tool_name = tool_name.split('.')[-1]

                    tools.append({
                        'name': tool_name,
                        'arguments': parameters
                    })
            except:
                pass

        if tools:
            return tools

        # 格式5: JSON数组格式 [{"name": "tool_name", "arguments": "{\"key\": \"value\"}"}]
        pattern5 = r'\[{"name":\s*"([^"]+)",\s*"arguments":\s*({[^}]+})\}\]'
        matches5 = re.findall(pattern5, text)

        for tool_name, args_json in matches5:
            tool_name = tool_name.strip()
            if not tool_name:
                continue

            try:
                arguments = json.loads(args_json)
            except:
                arguments = {}

            tools.append({
                'name': tool_name,
                'arguments': arguments
            })

        return tools
