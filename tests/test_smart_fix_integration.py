#!/usr/bin/env python3
"""
测试智能修复功能的集成效果
"""

import requests
import json

def test_smart_fix_integration():
    """测试智能修复集成效果"""
    
    print("🧪 测试智能修复集成效果...")
    
    # 测试场景1：单工具请求（容易触发文本响应）
    print("\n🔍 场景1：单工具请求测试")
    
    single_tool_request = {
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
    
    try:
        response = requests.post(
            "http://127.0.0.1:8080/v1/messages",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer test-key"
            },
            json=single_tool_request,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('content', [])
            
            print(f"📥 响应状态码: {response.status_code}")
            print(f"📋 内容项数量: {len(content)}")
            
            for i, item in enumerate(content):
                print(f"\n    内容 {i+1}:")
                print(f"      - 类型: {item.get('type', 'N/A')}")
                
                if item.get('type') == 'text':
                    text = item.get('text', '')
                    print(f"      - 文本内容: {text[:100]}...")
                    print(f"      - ⚠️  返回文本响应")
                        
                elif item.get('type') == 'tool_use':
                    print(f"      - 工具ID: {item.get('id', 'N/A')}")
                    print(f"      - 工具名称: {item.get('name', 'N/A')}")
                    tool_input = item.get('input', {})
                    print(f"      - 工具输入: {json.dumps(tool_input, ensure_ascii=False)}")
                    print(f"      - ✅ 工具调用成功!")
            
            # 判断是否需要智能修复
            has_tool_calls = any(item.get('type') == 'tool_use' for item in content)
            has_text_only = all(item.get('type') == 'text' for item in content)
            
            if has_tool_calls:
                print(f"\n🎯 结果: ✅ 正常工具调用（或已智能修复）")
            elif has_text_only:
                print(f"\n🎯 结果: ❌ 仍为文本响应（需要进一步优化）")
            else:
                print(f"\n🎯 结果: ❓ 响应格式异常")
                
        else:
            print(f"❌ 请求失败: {response.status_code}")
            print(f"错误信息: {response.text}")
            
    except Exception as e:
        print(f"❌ 测试异常: {str(e)}")

def test_multi_tool_scenario():
    """测试多工具场景（应该正常工作）"""
    
    print(f"\n🔍 场景2：多工具场景测试")
    
    multi_tool_request = {
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
                "name": "Read",
                "description": "Reads the contents of a file",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "File path"}
                    },
                    "required": ["file_path"]
                }
            },
            {
                "name": "Write", 
                "description": "Writes a file",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "File path"},
                        "content": {"type": "string", "description": "Content"}
                    },
                    "required": ["file_path", "content"]
                }
            },
            {
                "name": "Bash",
                "description": "Run a Bash command",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Command"}
                    },
                    "required": ["command"]
                }
            },
            {
                "name": "ListFiles",
                "description": "List files in directory",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path"}
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "SearchFiles",
                "description": "Search files",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Search path"},
                        "pattern": {"type": "string", "description": "Search pattern"}
                    },
                    "required": ["path", "pattern"]
                }
            }
        ],
        "tool_choice": "auto"
    }
    
    try:
        response = requests.post(
            "http://127.0.0.1:8080/v1/messages",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer test-key"
            },
            json=multi_tool_request,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('content', [])
            
            print(f"📥 响应状态码: {response.status_code}")
            print(f"📋 内容项数量: {len(content)}")
            
            has_tool_calls = any(item.get('type') == 'tool_use' for item in content)
            
            if has_tool_calls:
                print(f"🎯 结果: ✅ 多工具场景正常工作")
                for item in content:
                    if item.get('type') == 'tool_use':
                        print(f"      - 工具调用: {item.get('name')} - {json.dumps(item.get('input', {}), ensure_ascii=False)}")
            else:
                print(f"🎯 结果: ❌ 多工具场景异常")
                
        else:
            print(f"❌ 请求失败: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 测试异常: {str(e)}")

def test_edge_cases():
    """测试边缘情况"""
    
    print(f"\n🔍 场景3：边缘情况测试")
    
    # 测试不明确的工具调用
    ambiguous_request = {
        "model": "glm-4.6",
        "max_tokens": 4096,
        "temperature": 0.5,
        "messages": [
            {
                "role": "user",
                "content": "请帮我查看当前目录"
            }
        ],
        "tools": [
            {
                "name": "Bash",
                "description": "Run a Bash command",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Command"}
                    },
                    "required": ["command"]
                }
            },
            {
                "name": "ListFiles",
                "description": "List files in directory",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path"}
                    },
                    "required": ["path"]
                }
            }
        ],
        "tool_choice": "auto"
    }
    
    try:
        response = requests.post(
            "http://127.0.0.1:8080/v1/messages",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer test-key"
            },
            json=ambiguous_request,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('content', [])
            
            print(f"📥 响应状态码: {response.status_code}")
            print(f"📋 内容项数量: {len(content)}")
            
            for item in content:
                if item.get('type') == 'tool_use':
                    print(f"      - ✅ 智能识别工具: {item.get('name')}")
                elif item.get('type') == 'text':
                    print(f"      - 📝 文本响应: {item.get('text', '')[:50]}...")
                    
        else:
            print(f"❌ 请求失败: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 测试异常: {str(e)}")

if __name__ == "__main__":
    print("🔍 测试智能修复集成效果...")
    test_smart_fix_integration()
    test_multi_tool_scenario()
    test_edge_cases()
    print(f"\n📊 测试完成!")
