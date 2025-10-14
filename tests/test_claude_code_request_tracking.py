#!/usr/bin/env python3
"""
测试Claude Code请求跟踪脚本
用于验证请求ID跟踪和重试机制
"""

import requests
import json
import time
import uuid

def test_claude_code_request():
    """测试Claude Code风格的请求"""
    
    # 读取测试数据
    with open('test_claude_code_full.json', 'r', encoding='utf-8') as f:
        test_data = json.load(f)
    
    print("🔥 开始测试Claude Code请求跟踪...")
    print(f"📋 测试数据包含 {len(test_data.get('messages', []))} 条消息")
    
    # 发送请求
    url = "http://localhost:8080/v1/messages?beta=true"
    headers = {
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
        "User-Agent": "Claude-Code/1.0 (Test)"
    }
    
    try:
        print(f"🚀 发送请求到: {url}")
        start_time = time.time()
        
        response = requests.post(url, headers=headers, json=test_data, timeout=300)
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"⏱️  请求耗时: {duration:.2f}秒")
        print(f"📊 响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ 请求成功")
            print(f"📝 响应类型: {result.get('type', 'unknown')}")
            
            # 检查是否有工具调用
            content = result.get('content', [])
            tool_calls = [item for item in content if item.get('type') == 'tool_use']
            print(f"🔧 工具调用数量: {len(tool_calls)}")
            
            if tool_calls:
                for i, tool_call in enumerate(tool_calls):
                    print(f"   工具 {i+1}: {tool_call.get('name', 'unknown')}")
            
            return True
        else:
            print(f"❌ 请求失败: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("⏰ 请求超时")
        return False
    except Exception as e:
        print(f"💥 请求异常: {str(e)}")
        return False

def monitor_logs_for_duplicates():
    """监控日志中的重复请求"""
    print("\n🔍 监控日志中的重复请求模式...")
    
    try:
        with open('api_server.log', 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 查找最近的请求ID
        recent_requests = []
        for line in lines[-100:]:  # 只检查最后100行
            if '[REQ:' in line and '新HTTP请求开始' in line:
                # 提取请求ID
                start = line.find('[REQ:') + 5
                end = line.find(']', start)
                if start > 4 and end > start:
                    req_id = line[start:end]
                    recent_requests.append(req_id)
        
        print(f"📋 发现 {len(recent_requests)} 个最近请求:")
        for req_id in recent_requests:
            print(f"   - {req_id}")
        
        # 检查重复
        unique_requests = set(recent_requests)
        if len(recent_requests) != len(unique_requests):
            print("⚠️  发现重复请求!")
            duplicates = []
            for req_id in unique_requests:
                count = recent_requests.count(req_id)
                if count > 1:
                    duplicates.append((req_id, count))
            
            for req_id, count in duplicates:
                print(f"   请求 {req_id} 重复了 {count} 次")
        else:
            print("✅ 没有发现重复请求")
        
        return len(recent_requests) != len(unique_requests)
        
    except Exception as e:
        print(f"❌ 监控日志失败: {str(e)}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Claude Code 请求跟踪测试")
    print("=" * 60)
    
    # 测试请求
    success = test_claude_code_request()
    
    if success:
        print("\n⏳ 等待3秒后检查日志...")
        time.sleep(3)
        
        # 监控重复请求
        has_duplicates = monitor_logs_for_duplicates()
        
        if has_duplicates:
            print("\n🚨 检测到重复请求模式!")
        else:
            print("\n✅ 没有检测到重复请求")
    else:
        print("\n❌ 测试请求失败，无法检查重复请求")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
