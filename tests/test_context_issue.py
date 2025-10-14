#!/usr/bin/env python3
"""
测试上下文对工具调用的影响
"""

import requests
import json

def test_context_scenario():
    """测试可能导致问题的上下文场景"""
    
    # 场景1：模拟Claude Code的真实多轮对话
    print("🔍 场景1：模拟Claude Code多轮对话")
    
    session = requests.Session()
    
    # 第一轮：用户发送复杂请求
    request1 = {
        "model": "glm-4.6",
        "max_tokens": 4096,
        "temperature": 0.5,
        "messages": [
            {
                "role": "user",
                "content": "让我开始分析代码库结构：\n\n为什么总是终止了"
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
    
    print("📤 第一轮请求：复杂文本")
    response1 = session.post(
        "http://127.0.0.1:8080/v1/messages",
        headers={"Content-Type": "application/json", "Authorization": "Bearer test-key"},
        json=request1,
        timeout=30
    )
    
    if response1.status_code == 200:
        result1 = response1.json()
        content1 = result1.get('content', [])
        print(f"📥 第一轮响应类型: {[item.get('type') for item in content1]}")
        
        # 第二轮：基于第一轮的上下文，发送Bash(pwd)
        messages = [
            {"role": "user", "content": "让我开始分析代码库结构：\n\n为什么总是终止了"},
            {"role": "assistant", "content": json.dumps(content1, ensure_ascii=False)},
            {"role": "user", "content": "Bash(pwd)"}
        ]
        
        request2 = {
            "model": "glm-4.6",
            "max_tokens": 4096,
            "temperature": 0.5,
            "messages": messages,
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
        
        print("\n📤 第二轮请求：Bash(pwd) 带上下文")
        response2 = session.post(
            "http://127.0.0.1:8080/v1/messages",
            headers={"Content-Type": "application/json", "Authorization": "Bearer test-key"},
            json=request2,
            timeout=30
        )
        
        if response2.status_code == 200:
            result2 = response2.json()
            content2 = result2.get('content', [])
            print(f"📥 第二轮响应类型: {[item.get('type') for item in content2]}")
            
            for item in content2:
                if item.get('type') == 'tool_use':
                    print("✅ 第二轮触发工具调用!")
                    print(f"   工具: {item.get('name')}")
                    print(f"   参数: {json.dumps(item.get('input', {}), ensure_ascii=False)}")
                elif item.get('type') == 'text':
                    print("❌ 第二轮返回文本:")
                    print(f"   内容: {item.get('text', '')[:100]}...")
        else:
            print(f"❌ 第二轮请求失败: {response2.status_code}")
    else:
        print(f"❌ 第一轮请求失败: {response1.status_code}")

def test_temperature_effect():
    """测试temperature参数的影响"""
    
    print("\n🔍 场景2：测试不同temperature值")
    
    temperatures = [0.0, 0.3, 0.5, 0.7, 1.0]
    
    for temp in temperatures:
        print(f"\n🌡️  测试 temperature={temp}")
        
        request = {
            "model": "glm-4.6",
            "max_tokens": 4096,
            "temperature": temp,
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
                headers={"Content-Type": "application/json", "Authorization": "Bearer test-key"},
                json=request,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get('content', [])
                has_tool_call = any(item.get('type') == 'tool_use' for item in content)
                print(f"   结果: {'✅ 工具调用' if has_tool_call else '❌ 文本响应'}")
            else:
                print(f"   结果: ❌ 请求失败 ({response.status_code})")
                
        except Exception as e:
            print(f"   结果: ❌ 异常 ({str(e)[:50]}...)")

if __name__ == "__main__":
    print("🔍 测试上下文和参数对工具调用的影响...")
    test_context_scenario()
    test_temperature_effect()
    print(f"\n📊 测试完成!")
