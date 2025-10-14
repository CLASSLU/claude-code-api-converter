#!/usr/bin/env python3
"""
测试不同输入格式对GLM工具调用的影响
"""

import requests
import json

def test_input_format(format_name, user_message):
    """测试特定的输入格式"""
    
    claude_request = {
        "model": "glm-4.6",
        "max_tokens": 4096,
        "temperature": 0.5,
        "messages": [
            {
                "role": "user",
                "content": user_message
            }
        ],
        "tools": [
            {
                "name": "Bash",
                "description": "Run a Bash command on the user's system",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The Bash command to run"
                        }
                    },
                    "required": ["command"]
                }
            }
        ],
        "tool_choice": "auto"
    }
    
    print(f"\n🧪 测试格式: {format_name}")
    print(f"💬 用户消息: {user_message}")
    
    try:
        response = requests.post(
            "http://127.0.0.1:8080/v1/messages",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer test-key"
            },
            json=claude_request,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('content', [])
            
            has_tool_calls = any(item.get('type') == 'tool_use' for item in content)
            
            if has_tool_calls:
                print("✅ 触发工具调用!")
                for item in content:
                    if item.get('type') == 'tool_use':
                        print(f"   工具: {item.get('name')}")
                        print(f"   参数: {json.dumps(item.get('input', {}), ensure_ascii=False)}")
            else:
                print("❌ 未触发工具调用")
                for item in content:
                    if item.get('type') == 'text':
                        print(f"   响应: {item.get('text', '')[:100]}...")
                        
        else:
            print(f"❌ 请求失败: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 异常: {str(e)}")

def main():
    """测试多种输入格式"""
    
    test_formats = [
        ("原始格式", "Bash(pwd)"),
        ("明确命令", "请执行命令: pwd"),
        ("英文命令", "Please execute the command: pwd"),
        ("直接询问", "执行pwd命令"),
        ("工具调用格式", "我需要使用Bash工具执行pwd命令"),
        ("系统提示格式", "作为助手，请使用Bash工具执行pwd命令"),
        ("简单格式", "pwd"),
        ("带引号格式", "执行 'pwd' 命令"),
    ]
    
    print("🔍 测试不同输入格式对GLM工具调用的影响...")
    
    for format_name, message in test_formats:
        test_input_format(format_name, message)
        
    print(f"\n📊 测试完成!")

if __name__ == "__main__":
    main()
