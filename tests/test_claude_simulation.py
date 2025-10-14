#!/usr/bin/env python3
"""
模拟Claude Code实际使用场景的测试
"""

import requests
import json

def test_claude_code_simulation():
    """模拟Claude Code的实际工作流程"""
    
    # 模拟Claude Code发送的真实请求（基于日志分析）
    claude_request = {
        "model": "glm-4.6",
        "max_tokens": 4096,
        "temperature": 0.5,
        "messages": [
            {
                "role": "user",
                "content": "Bash(pwd)"
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
    
    print("🔍 模拟Claude Code真实场景测试...")
    print(f"📤 发送请求到: http://127.0.0.1:8080/v1/messages")
    print(f"💬 用户消息: {claude_request['messages'][0]['content']}")
    print(f"🔧 工具数量: {len(claude_request['tools'])}")
    
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
        
        print(f"📥 响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ 请求成功!")
            
            # 详细分析响应
            print("\n📋 详细响应分析:")
            print(f"  - ID: {result.get('id', 'N/A')}")
            print(f"  - 模型: {result.get('model', 'N/A')}")
            print(f"  - 停止原因: {result.get('stop_reason', 'N/A')}")
            
            content = result.get('content', [])
            print(f"  - 内容项数量: {len(content)}")
            
            for i, item in enumerate(content):
                print(f"\n    内容 {i+1}:")
                print(f"      - 类型: {item.get('type', 'N/A')}")
                
                if item.get('type') == 'text':
                    text = item.get('text', '')
                    print(f"      - 文本内容: {text}")
                    print(f"      - 文本长度: {len(text)}")
                    
                    # 检查是否包含工具调用意图
                    if any(keyword in text.lower() for keyword in ['pwd', '命令', '执行', 'bash']):
                        print("      ⚠️  检测到工具调用意图，但返回的是文本！")
                        
                elif item.get('type') == 'tool_use':
                    print(f"      - 工具ID: {item.get('id', 'N/A')}")
                    print(f"      - 工具名称: {item.get('name', 'N/A')}")
                    tool_input = item.get('input', {})
                    print(f"      - 工具输入: {json.dumps(tool_input, ensure_ascii=False)}")
                    
                    # 验证工具调用是否正确
                    if item.get('name') == 'Bash':
                        command = tool_input.get('command', '')
                        if 'pwd' in command:
                            print("      ✅ 工具调用正确!")
                        else:
                            print(f"      ⚠️  工具调用命令不匹配: {command}")
            
            # 判断整体结果
            has_tool_calls = any(item.get('type') == 'tool_use' for item in content)
            has_text_only = all(item.get('type') == 'text' for item in content)
            
            print(f"\n🎯 测试结果:")
            if has_tool_calls:
                print("  ✅ 包含工具调用 - 正常")
            elif has_text_only:
                print("  ❌ 只有文本响应 - 这就是Claude Code中断的原因!")
            else:
                print("  ❓ 响应格式异常")
                
        else:
            print(f"❌ 请求失败: {response.status_code}")
            print(f"错误信息: {response.text}")
            
    except Exception as e:
        print(f"❌ 测试异常: {str(e)}")

if __name__ == "__main__":
    test_claude_code_simulation()
