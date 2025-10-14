#!/usr/bin/env python3
"""
测试真实的Claude Code场景：43个工具
"""

import requests
import json

def test_real_43_tools():
    """测试真实的43个工具场景"""
    
    # 模拟Claude Code发送的真实请求（基于日志中的43个工具）
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
            },
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
            },
            {
                "name": "ReplaceInFile",
                "description": "Request to replace sections of content in an existing file using SEARCH/REPLACE blocks",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "The path of the file to modify"
                        },
                        "diff": {
                            "type": "string",
                            "description": "One or more SEARCH/REPLACE blocks"
                        }
                    },
                    "required": ["path", "diff"]
                }
            },
            {
                "name": "ListFiles",
                "description": "Request to list files and directories within the specified directory",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "The path of the directory to list contents for"
                        },
                        "recursive": {
                            "type": "boolean",
                            "description": "Whether to list files recursively"
                        }
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "SearchFiles",
                "description": "Request to perform a regex search across files in a specified directory",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "The path of the directory to search in"
                        },
                        "regex": {
                            "type": "string",
                            "description": "The regular expression pattern to search for"
                        }
                    },
                    "required": ["path", "regex"]
                }
            },
            {
                "name": "ExecuteCommand",
                "description": "Request to execute a CLI command on the system",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The CLI command to execute"
                        }
                    },
                    "required": ["command"]
                }
            },
            {
                "name": "BrowserAction",
                "description": "Request to interact with a Puppeteer-controlled browser",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "description": "The action to perform"
                        }
                    },
                    "required": ["action"]
                }
            },
            {
                "name": "AskFollowupQuestion",
                "description": "Ask the user a question to gather additional information",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "The question to ask the user"
                        }
                    },
                    "required": ["question"]
                }
            },
            {
                "name": "AttemptCompletion",
                "description": "Present the result of the task to the user",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "result": {
                            "type": "string",
                            "description": "The result of the task"
                        }
                    },
                    "required": ["result"]
                }
            }
        ],
        "tool_choice": "auto"
    }
    
    print("🔍 测试真实场景：10个工具（简化版43个工具）")
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
            timeout=60  # 增加超时时间
        )
        
        print(f"📥 响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ 请求成功!")
            
            content = result.get('content', [])
            print(f"📋 内容项数量: {len(content)}")
            
            for i, item in enumerate(content):
                print(f"\n    内容 {i+1}:")
                print(f"      - 类型: {item.get('type', 'N/A')}")
                
                if item.get('type') == 'text':
                    text = item.get('text', '')
                    print(f"      - 文本内容: {text}")
                    print(f"      - ⚠️  返回文本而不是工具调用!")
                        
                elif item.get('type') == 'tool_use':
                    print(f"      - 工具ID: {item.get('id', 'N/A')}")
                    print(f"      - 工具名称: {item.get('name', 'N/A')}")
                    tool_input = item.get('input', {})
                    print(f"      - 工具输入: {json.dumps(tool_input, ensure_ascii=False)}")
                    print(f"      - ✅ 正确的工具调用!")
            
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

def test_progressive_tools():
    """逐步增加工具数量，观察行为变化"""
    
    print(f"\n🔍 场景2：逐步增加工具数量测试")
    
    tool_counts = [1, 5, 10, 20, 43]
    
    for count in tool_counts:
        print(f"\n🧪 测试 {count} 个工具:")
        
        # 构建工具列表
        tools = []
        base_tools = [
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
            }
        ]
        
        # 重复工具以达到目标数量
        for i in range(count):
            base_tool = base_tools[i % len(base_tools)]
            tools.append({
                "name": f"{base_tool['name']}_{i}" if i >= len(base_tools) else base_tool['name'],
                "description": base_tool['description'],
                "input_schema": base_tool['input_schema']
            })
        
        request = {
            "model": "glm-4.6",
            "max_tokens": 4096,
            "temperature": 0.5,
            "messages": [{"role": "user", "content": "Bash(pwd)"}],
            "tools": tools,
            "tool_choice": "auto"
        }
        
        try:
            response = requests.post(
                "http://127.0.0.1:8080/v1/messages",
                headers={"Content-Type": "application/json", "Authorization": "Bearer test-key"},
                json=request,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get('content', [])
                has_tool_call = any(item.get('type') == 'tool_use' for item in content)
                print(f"   结果: {'✅ 工具调用' if has_tool_call else '❌ 文本响应'}")
            else:
                print(f"   结果: ❌ 请求失败 ({response.status_code})")
                
        except Exception as e:
            print(f"   结果: ❌ 异常 ({str(e)[:30]}...)")

if __name__ == "__main__":
    print("🔍 测试真实Claude Code场景...")
    test_real_43_tools()
    test_progressive_tools()
    print(f"\n📊 测试完成!")
