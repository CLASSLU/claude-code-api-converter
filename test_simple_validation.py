#!/usr/bin/env python3
"""
 simplified validation test for duplicate request fixes
"""

import json
import logging
from converter_class import AnthropicToOpenAIConverter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_empty_id_fix():
    """Test empty response ID fix"""
    print("=== Testing Empty ID Fix ===")

    converter = AnthropicToOpenAIConverter()

    # Test case 1: completely empty ID
    response_empty = {
        'choices': [{
            'message': {'content': 'Hello', 'role': 'assistant'},
            'finish_reason': 'stop'
        }],
        'usage': {'prompt_tokens': 10, 'completion_tokens': 5}
    }

    result = converter.convert_response(response_empty)

    # Validate ID is not empty
    assert result['id'], "Response ID should not be empty"
    assert result['id'].startswith('msg_'), f"ID should start with msg_, got: {result['id']}"
    print(f"PASS: Empty ID fixed, generated: {result['id']}")

    # Test case 2: invalid ID 'chat-'
    response_invalid = {
        'id': 'chat-',
        'choices': [{
            'message': {'content': 'Hello', 'role': 'assistant'},
            'finish_reason': 'stop'
        }],
        'usage': {'prompt_tokens': 10, 'completion_tokens': 5}
    }

    result2 = converter.convert_response(response_invalid)

    assert result2['id'], "Response ID should not be empty"
    assert result2['id'].startswith('msg_'), f"ID should start with msg_, got: {result2['id']}"
    print(f"PASS: Invalid ID fixed, generated: {result2['id']}")

def test_stop_reason_fix():
    """Test stop_reason mapping fix"""
    print("\n=== Testing Stop Reason Fix ===")

    converter = AnthropicToOpenAIConverter()

    # Test tool call scenario
    tool_response = {
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
            'finish_reason': 'tool_calls'  # Key test point
        }],
        'usage': {'prompt_tokens': 20, 'completion_tokens': 10}
    }

    result = converter.convert_response(tool_response)

    # Validate stop_reason mapping
    assert result['stop_reason'] == 'tool_use', f"tool_calls should map to tool_use, got: {result['stop_reason']}"

    # Validate tool call content
    assert len(result['content']) == 1, f"Should have 1 tool call, got: {len(result['content'])}"
    assert result['content'][0]['type'] == 'tool_use', f"Type should be tool_use, got: {result['content'][0]['type']}"
    assert result['content'][0]['name'] == 'test_function', f"Name should be test_function, got: {result['content'][0]['name']}"

    print(f"PASS: stop_reason mapping: tool_calls -> {result['stop_reason']}")
    print(f"PASS: Tool call converted: {result['content'][0]['name']}")

def test_combined_scenario():
    """Test combined scenario: empty ID + tool calls"""
    print("\n=== Testing Combined Scenario ===")

    converter = AnthropicToOpenAIConverter()

    problematic_response = {
        'id': 'chat-',  # Empty ID issue
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
            'finish_reason': 'tool_calls'  # stop_reason mapping issue
        }],
        'usage': {'prompt_tokens': 15, 'completion_tokens': 8}
    }

    result = converter.convert_response(problematic_response)

    # Validate all fixes
    assert result['id'], "Response ID should not be empty"
    assert result['id'].startswith('msg_'), f"ID should start with msg_, got: {result['id']}"
    assert result['stop_reason'] == 'tool_use', f"Should be tool_use, got: {result['stop_reason']}"
    assert len(result['content']) == 1, "Should have 1 tool call"
    assert result['content'][0]['type'] == 'tool_use', "Type should be tool_use"

    print(f"PASS: Combined scenario working")
    print(f"  - ID: {result['id']}")
    print(f"  - stop_reason: {result['stop_reason']}")
    print(f"  - tool call: {result['content'][0]['name']}")

def simulate_claude_code_validation():
    """Simulate Claude Code validation"""
    print("\n=== Simulating Claude Code Validation ===")

    converter = AnthropicToOpenAIConverter()

    # Response that previously caused Claude Code retries
    problematic_response = {
        'id': 'chat-',
        'choices': [{
            'message': {
                'role': 'assistant',
                'content': None,
                'tool_calls': [{
                    'id': 'call_problem',
                    'type': 'function',
                    'function': {
                        'name': 'read_file',
                        'arguments': '{"file_path": "test.py"}'
                    }
                }]
            },
            'finish_reason': 'tool_calls'
        }],
        'usage': {'prompt_tokens': 25, 'completion_tokens': 12}
    }

    result = converter.convert_response(problematic_response)

    print("Before fix:")
    print("   - id: 'chat-' (empty, causes retries)")
    print("   - stop_reason: 'end_turn' (wrong mapping)")

    print("\nAfter fix:")
    print(f"   - id: '{result['id']}' (valid, prevents retries)")
    print(f"   - stop_reason: '{result['stop_reason']}' (correct mapping)")
    print(f"   - content: {len(result['content'])} tool calls")

    # Claude Code compatibility checks
    checks = [
        (result['id'].startswith('msg_'), "ID format valid"),
        (result['stop_reason'] == 'tool_use', "stop_reason correct"),
        (len(result['content']) > 0, "has content"),
        (result['role'] == 'assistant', "role correct"),
        (result['type'] == 'message', "type correct")
    ]

    print("\nClaude Code compatibility:")
    all_passed = True
    for check, description in checks:
        status = "PASS" if check else "FAIL"
        print(f"   [{status}] {description}")
        if not check:
            all_passed = False

    if all_passed:
        print("\nALL CHECKS PASSED! Fix should resolve Claude Code duplicate requests")
    else:
        print("\nWARNING: Some issues remain")

    return all_passed

if __name__ == "__main__":
    print("Starting validation of Claude Code duplicate request fixes...")

    try:
        test_empty_id_fix()
        test_stop_reason_fix()
        test_combined_scenario()
        success = simulate_claude_code_validation()

        print("\n" + "=" * 50)
        if success:
            print("SUCCESS: All tests passed! Fixes validated successfully")
        else:
            print("FAILURE: Some tests failed")
        print("=" * 50)

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)