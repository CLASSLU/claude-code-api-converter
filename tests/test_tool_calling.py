#!/usr/bin/env python3
"""
测试工具调用功能的脚本
"""

import requests
import json

def test_tool_calling():
    """测试工具调用功能"""
    
    # 模拟Claude Code的工具调用请求
    test_request = {
        "model": "glm-4.6",
        "max_tokens": 1000,
        "temperature": 0.7,
        "messages": [
            {
                "role": "user",
                "content": "请读取文件 /tmp/test.txt 的内容"
            }
        ],
        "tools": [
            {
                "name": "Read",
                "description": "Reads the contents of a file at the specified path",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "The absolute path to the file to read"
                        }
                    },
                    "required": ["file_path"]
                }
            },
            {
                "name": "Write",
                "description": "Writes a file to the local filesystem",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "The absolute path to the file to write"
                        },
                        "content": {
                            "type": "string",
                            "description": "The content to write to the file"
                        }
                    },
                    "required": ["file_path", "content"]
                }
            }
        ],
        "tool_choice": "auto"
    }
    
    print("🧪 测试工具调用功能...")
    print(f"📤 发送请求到: http://127.0.0.1:8080/v1/messages")
    print(f"🔧 包含工具数量: {len(test_request['tools'])}")
    
    try:
        response = requests.post(
            "http://127.0.0.1:8080/v1/messages",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer test-key"
            },
            json=test_request,
            timeout=30
        )
        
        print(f"📥 响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ 请求成功!")
            
            # 检查响应结构
            print("\n📋 响应分析:")
            print(f"  - ID: {result.get('id', 'N/A')}")
            print(f"  - 类型: {result.get('type', 'N/A')}")
            print(f"  - 角色: {result.get('role', 'N/A')}")
            print(f"  - 模型: {result.get('model', 'N/A')}")
            print(f"  - 停止原因: {result.get('stop_reason', 'N/A')}")
            
            # 检查内容
            content = result.get('content', [])
            print(f"  - 内容项数量: {len(content)}")
            
            for i, item in enumerate(content):
                print(f"    内容 {i+1}:")
                print(f"      - 类型: {item.get('type', 'N/A')}")
                if item.get('type') == 'text':
                    print(f"      - 文本: {item.get('text', '')[:100]}...")
                elif item.get('type') == 'tool_use':
                    print(f"      - 工具ID: {item.get('id', 'N/A')}")
                    print(f"      - 工具名称: {item.get('name', 'N/A')}")
                    print(f"      - 工具输入: {json.dumps(item.get('input', {}), ensure_ascii=False)}")
            
            # 检查使用量
            usage = result.get('usage', {})
            print(f"  - 输入tokens: {usage.get('input_tokens', 0)}")
            print(f"  - 输出tokens: {usage.get('output_tokens', 0)}")
            
            # 判断是否包含工具调用
            has_tool_calls = any(item.get('type') == 'tool_use' for item in content)
            if has_tool_calls:
                print("\n🎉 检测到工具调用! 修复成功!")
            else:
                print("\n⚠️  未检测到工具调用，可能需要进一步调试")
                
        else:
            print(f"❌ 请求失败: {response.status_code}")
            print(f"错误信息: {response.text}")
            
    except Exception as e:
        print(f"❌ 测试异常: {str(e)}")

if __name__ == "__main__":
    test_tool_calling()
