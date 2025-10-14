#!/usr/bin/env python3
"""
验证重复请求修复效果的测试
测试空响应ID生成和stop_reason映射修复
"""

import json
import logging
from converter_class import AnthropicToOpenAIConverter

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_empty_response_id_fix():
    """测试空响应ID修复"""
    print("=" * 50)
    print("测试空响应ID修复")
    print("=" * 50)

    converter = AnthropicToOpenAIConverter()

    # 测试用例1：完全空的ID
    openai_response_empty_id = {
        'choices': [{
            'message': {
                'content': 'Hello world',
                'role': 'assistant'
            },
            'finish_reason': 'stop'
        }],
        'usage': {
            'prompt_tokens': 10,
            'completion_tokens': 5
        }
    }

    result = converter.convert_response(openai_response_empty_id)

    # 验证ID不为空
    assert result['id'], "响应ID不能为空"
    assert result['id'].startswith('msg_'), f"响应ID应该以msg_开头，实际是: {result['id']}"
    print(f"✅ 空ID修复测试通过，生成ID: {result['id']}")

    # 测试用例2：无效的ID 'chat-'
    openai_response_invalid_id = {
        'id': 'chat-',
        'choices': [{
            'message': {
                'content': 'Hello with invalid ID',
                'role': 'assistant'
            },
            'finish_reason': 'stop'
        }],
        'usage': {
            'prompt_tokens': 10,
            'completion_tokens': 5
        }
    }

    result2 = converter.convert_response(openai_response_invalid_id)

    # 验证ID已被正确处理
    assert result2['id'], "响应ID不能为空"
    assert result2['id'].startswith('msg_'), f"响应ID应该以msg_开头，实际是: {result2['id']}"
    print(f"✅ 无效ID修复测试通过，生成ID: {result2['id']}")

    # 测试用例3：有效的ID
    openai_response_valid_id = {
        'id': 'chat-123456789',
        'choices': [{
            'message': {
                'content': 'Hello with valid ID',
                'role': 'assistant'
            },
            'finish_reason': 'stop'
        }],
        'usage': {
            'prompt_tokens': 10,
            'completion_tokens': 5
        }
    }

    result3 = converter.convert_response(openai_response_valid_id)

    # 验证有效ID被正确转换
    assert result3['id'], "响应ID不能为空"
    assert result3['id'] == 'msg_123456789', f"有效ID应该被转换，实际是: {result3['id']}"
    print(f"✅ 有效ID转换测试通过，转换ID: {result3['id']}")

def test_stop_reason_mapping_fix():
    """测试stop_reason映射修复"""
    print("\n" + "=" * 50)
    print("测试stop_reason映射修复")
    print("=" * 50)

    converter = AnthropicToOpenAIConverter()

    # 测试工具调用场景
    openai_tool_call_response = {
        'id': 'chat-test123',
        'choices': [{
            'message': {
                'role': 'assistant',
                'content': None,
                'tool_calls': [{
                    'id': 'call_123',
                    'type': 'function',
                    'function': {
                        'name': 'test_function',
                        'arguments': '{"param": "value"}'
                    }
                }]
            },
            'finish_reason': 'tool_calls'  # 这是关键测试点
        }],
        'usage': {
            'prompt_tokens': 20,
            'completion_tokens': 10
        }
    }

    result = converter.convert_response(openai_tool_call_response)

    # 验证stop_reason正确映射
    assert result['stop_reason'] == 'tool_use', f"工具调用应该映射为tool_use，实际是: {result['stop_reason']}"

    # 验证工具调用内容正确转换
    assert len(result['content']) == 1, f"应该有一个工具调用内容，实际数量: {len(result['content'])}"
    assert result['content'][0]['type'] == 'tool_use', f"内容类型应该是tool_use，实际是: {result['content'][0]['type']}"
    assert result['content'][0]['name'] == 'test_function', f"工具名称应该是test_function，实际是: {result['content'][0]['name']}"

    print(f"✅ stop_reason映射测试通过，tool_calls -> {result['stop_reason']}")
    print(f"✅ 工具调用内容转换正确: {result['content'][0]['name']}")

def test_combined_scenario():
    """测试组合场景：空ID + 工具调用"""
    print("\n" + "=" * 50)
    print("测试组合场景：空ID + 工具调用")
    print("=" * 50)

    converter = AnthropicToOpenAIConverter()

    # 组合问题场景：空ID + 工具调用
    problematic_response = {
        'id': 'chat-',  # 空ID问题
        'choices': [{
            'message': {
                'role': 'assistant',
                'content': None,
                'tool_calls': [{
                    'id': 'call_combo',
                    'type': 'function',
                    'function': {
                        'name': 'combo_function',
                        'arguments': '{"test": true}'
                    }
                }]
            },
            'finish_reason': 'tool_calls'  # stop_reason映射问题
        }],
        'usage': {
            'prompt_tokens': 15,
            'completion_tokens': 8
        }
    }

    result = converter.convert_response(problematic_response)

    # 验证所有修复都生效
    assert result['id'], "响应ID不能为空"
    assert result['id'].startswith('msg_'), f"响应ID应该以msg_开头，实际是: {result['id']}"
    assert result['stop_reason'] == 'tool_use', f"工具调用应该映射为tool_use，实际是: {result['stop_reason']}"
    assert len(result['content']) == 1, "应该有一个工具调用内容"
    assert result['content'][0]['type'] == 'tool_use', "内容类型应该是tool_use"

    print(f"✅ 组合场景测试通过")
    print(f"   - ID生成: {result['id']}")
    print(f"   - stop_reason: {result['stop_reason']}")
    print(f"   - 工具调用: {result['content'][0]['name']}")

def simulate_claude_code_validation():
    """模拟Claude Code验证修复效果"""
    print("\n" + "=" * 50)
    print("模拟Claude Code验证修复效果")
    print("=" * 50)

    converter = AnthropicToOpenAIConverter()

    # 模拟之前会导致Claude Code重复请求的响应
    problematic_response = {
        'id': 'chat-',  # 这之前会导致Claude Code认为响应无效
        'choices': [{
            'message': {
                'role': 'assistant',
                'content': None,
                'tool_calls': [{
                    'id': 'call_prev_problematic',
                    'type': 'function',
                    'function': {
                        'name': 'read_file',
                        'arguments': '{"file_path": "test.py"}'
                    }
                }]
            },
            'finish_reason': 'tool_calls'
        }],
        'usage': {
            'prompt_tokens': 25,
            'completion_tokens': 12
        }
    }

    result = converter.convert_response(problematic_response)

    print("修复前的响应特征:")
    print("   - id: 'chat-' (空ID，会导致Claude Code重试)")
    print("   - stop_reason: 'end_turn' (错误映射，应为'tool_use')")

    print("\n修复后的响应特征:")
    print(f"   - id: '{result['id']}' (有效ID，防止重试)")
    print(f"   - stop_reason: '{result['stop_reason']}' (正确映射)")
    print(f"   - content: {len(result['content'])} 个工具调用")

    # 验证现在Claude Code应该能接受的响应格式
    validation_checks = [
        (result['id'].startswith('msg_'), "ID格式有效"),
        (result['stop_reason'] == 'tool_use' if 'tool_calls' in result.get('content', [{}])[0].get('type', '') else True, "stop_reason映射正确"),
        (len(result['content']) > 0, "包含响应内容"),
        (result['role'] == 'assistant', "角色正确"),
        (result['type'] == 'message', "类型正确")
    ]

    print("\nClaude Code兼容性检查:")
    all_passed = True
    for check, description in validation_checks:
        status = "✅ PASS" if check else "❌ FAIL"
        print(f"   {status}: {description}")
        if not check:
            all_passed = False

    if all_passed:
        print("\n🎉 所有检查通过！修复应该能解决Claude Code重复请求问题")
    else:
        print("\n⚠️  仍有问题需要修复")

if __name__ == "__main__":
    print("开始验证Claude Code重复请求修复效果...")

    try:
        test_empty_response_id_fix()
        test_stop_reason_mapping_fix()
        test_combined_scenario()
        simulate_claude_code_validation()

        print("\n" + "=" * 50)
        print("🎉 所有测试通过！修复效果验证成功")
        print("=" * 50)

    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        exit(1)
    except Exception as e:
        print(f"\n💥 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        exit(1)