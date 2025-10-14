import json
import logging
from typing import Dict, List, Optional, Any
import requests
from config_manager import ConfigManager

# 设置日志
logger = logging.getLogger(__name__)

class AnthropicToOpenAIConverter:
    def __init__(self, config_manager: ConfigManager = None):
        self.config_manager = config_manager or ConfigManager()
        
    def convert_messages(self, anthropic_messages: List[Dict]) -> List[Dict]:
        """将Anthropic消息格式转换为OpenAI消息格式"""
        openai_messages = []
        
        for message in anthropic_messages:
            role = message.get('role', '')
            content = message.get('content', '')
            
            # 角色映射
            if role == 'user':
                openai_role = 'user'
            elif role == 'assistant':
                openai_role = 'assistant'
            else:
                openai_role = 'user'  # 默认映射
            
            # 处理内容格式（Anthropic可能是对象数组，OpenAI是字符串或对象数组）
            if isinstance(content, list):
                # 如果是内容数组，提取文本
                text_content = ''
                for content_item in content:
                    if content_item.get('type') == 'text':
                        text_content += content_item.get('text', '')
                openai_messages.append({
                    'role': openai_role,
                    'content': text_content
                })
            else:
                # 如果是纯文本
                openai_messages.append({
                    'role': openai_role,
                    'content': content
                })
        
        return openai_messages
    
    def convert_request(self, anthropic_request: Dict) -> Dict:
        """将Anthropic API请求转换为OpenAI API请求"""
        model = anthropic_request.get('model', 'gpt-4')
        
        openai_request = {
            'model': self._convert_model(model),
            'max_tokens': anthropic_request.get('max_tokens', 1024),
            'messages': [],
            'temperature': anthropic_request.get('temperature', 0.7),
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
        
        # 处理工具调用（Claude Code关键功能）
        if 'tools' in anthropic_request:
            # 转换Anthropic工具格式为OpenAI格式
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
            logger.info(f"转换工具定义: {len(openai_tools)} 个工具")
        
        if 'tool_choice' in anthropic_request:
            openai_request['tool_choice'] = anthropic_request['tool_choice']
        
        # 可选参数转换
        if 'top_p' in anthropic_request:
            openai_request['top_p'] = anthropic_request['top_p']
        
        if 'stop_sequences' in anthropic_request:
            openai_request['stop'] = anthropic_request['stop_sequences']
        
        return openai_request
    
    def _convert_model(self, anthropic_model: str) -> str:
        """直接使用传入的模型名称，不进行映射"""
        return anthropic_model
    
    def convert_response(self, openai_response: Dict) -> Dict:
        """将OpenAI API响应转换为Anthropic格式"""
        
        # 🔥 关键修复：检查OpenAI API错误响应
        if self._is_error_response(openai_response):
            error_msg = openai_response.get('msg', 'Unknown API error')
            error_status = openai_response.get('status', '500')
            logger.error(f"OpenAI API返回错误: {error_status} - {error_msg}")
            raise Exception(f"OpenAI API error: {error_status} - {error_msg}")
        
        anthropic_response = {
            'id': openai_response.get('id', ''),
            'type': 'message',
            'role': 'assistant',
            'content': [],
            'model': self._reverse_convert_model(openai_response.get('model', '')),
            'stop_reason': 'end_turn',
            'usage': self._convert_usage(openai_response.get('usage', {}))
        }
        
        # 转换内容
        if openai_response.get('choices'):
            choice = openai_response['choices'][0]
            message = choice.get('message', {})
            
            # 处理工具调用响应（Claude Code关键功能）
            if 'tool_calls' in message:
                tool_calls = message['tool_calls']
                logger.info(f"转换工具调用响应: {len(tool_calls)} 个工具调用")
                
                # 将工具调用转换为Claude格式
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
                # 处理普通文本响应
                message_content = message.get('content', '')
                
                # 🔴 关键修复：glm-4.6模型使用reasoning_content字段而不是content字段
                if not message_content:
                    message_content = message.get('reasoning_content', '')
                
                if message_content:
                    anthropic_response['content'] = [{
                        'type': 'text',
                        'text': message_content
                    }]
            
            anthropic_response['stop_reason'] = self._convert_stop_reason(
                choice.get('finish_reason', 'stop')
            )
        
        return anthropic_response
    
    def _reverse_convert_model(self, openai_model: str) -> str:
        """直接使用返回的模型名称，不进行映射"""
        return openai_model
    
    def _convert_stop_reason(self, openai_stop_reason: str) -> str:
        """转换停止原因"""
        reason_mapping = {
            'stop': 'end_turn',
            'length': 'max_tokens',
            'content_filter': 'stop_sequence',
            'tool_calls': 'tool_use'  # 🔴 关键修复：工具调用应该映射为 tool_use
        }
        return reason_mapping.get(openai_stop_reason, 'end_turn')
    
    def _convert_usage(self, openai_usage: Dict) -> Dict:
        """转换使用量统计"""
        return {
            'input_tokens': openai_usage.get('prompt_tokens', 0),
            'output_tokens': openai_usage.get('completion_tokens', 0)
        }
    
    def _is_error_response(self, openai_response: Dict) -> bool:
        """检测OpenAI API错误响应"""
        # 检查明显的错误字段
        if 'status' in openai_response and openai_response['status'] != '200':
            return True
        
        if 'error' in openai_response:
            return True
        
        # 检查是否缺少必要字段
        if 'choices' not in openai_response:
            return True
        
        # 检查body字段为空（某些API错误格式）
        if openai_response.get('body') is None and 'choices' not in openai_response:
            return True
        
        return False
