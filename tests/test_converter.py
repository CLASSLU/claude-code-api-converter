# test_converter.py
import requests
import json
from converter_class import AnthropicToOpenAIConverter

def test_anthropic_to_openai_conversion():
    """测试Anthropic到OpenAI的转换"""
    converter = AnthropicToOpenAIConverter()
    
    # Anthropic格式的请求示例
    anthropic_request = {
        "model": "claude-3-sonnet-20240229",
        "max_tokens": 100,
        "messages": [
            {
                "role": "user", 
                "content": "Hello, please introduce yourself"
            }
        ],
        "temperature": 0.7,
        "system": "You are a helpful assistant"
    }
    
    # 转换为OpenAI格式
    openai_request = converter.convert_request(anthropic_request)
    print("OpenAI请求格式:")
    print(json.dumps(openai_request, indent=2, ensure_ascii=False))
    
    # 模拟OpenAI响应
    openai_response = {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1677652288,
        "model": "gpt-4",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant", 
                "content": "Hello! I'm an AI assistant created by OpenAI."
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 9,
            "completion_tokens": 12,
            "total_tokens": 21
        }
    }
    
    # 转换回Anthropic格式
    anthropic_response = converter.convert_response(openai_response)
    print("\nAnthropic响应格式:")
    print(json.dumps(anthropic_response, indent=2, ensure_ascii=False))

def test_api_integration():
    """测试API集成"""
    # 使用anthropic库风格的请求
    headers = {
        'Content-Type': 'application/json',
        'x-api-key': 'dummy-key'  # 在实际使用中可能是你的API密钥
    }
    
    data = {
        "model": "claude-3-sonnet-20240229",
        "max_tokens": 100,
        "messages": [
            {"role": "user", "content": "Hello, how are you?"}
        ]
    }
    
    response = requests.post(
        'http://localhost:8080/v1/messages',
        headers=headers,
        json=data
    )
    
    print("API响应:")
    print(json.dumps(response.json(), indent=2))

if __name__ == "__main__":
    test_anthropic_to_openai_conversion()
