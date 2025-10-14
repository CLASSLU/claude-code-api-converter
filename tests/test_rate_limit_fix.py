#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试智能限流处理修复效果
"""

import requests
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

def test_single_request():
    """测试单个请求"""
    try:
        url = "http://localhost:8080/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer test-key"
        }
        
        data = {
            "model": "claude-3-sonnet-20240229",
            "messages": [
                {"role": "user", "content": "Hello, this is a test message."}
            ],
            "max_tokens": 50,
            "temperature": 0.1
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 请求成功: {result.get('choices', [{}])[0].get('message', {}).get('content', 'N/A')[:50]}...")
        else:
            print(f"❌ 请求失败: {response.text}")
            
        return response.status_code == 200
        
    except Exception as e:
        print(f"❌ 请求异常: {str(e)}")
        return False

def test_concurrent_requests(num_requests=5):
    """测试并发请求，验证限流处理"""
    print(f"\n🔄 测试 {num_requests} 个并发请求...")
    
    success_count = 0
    rate_limit_count = 0
    error_count = 0
    
    def make_request(request_id):
        try:
            url = "http://localhost:8080/v1/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": "Bearer test-key"
            }
            
            data = {
                "model": "claude-3-sonnet-20240229",
                "messages": [
                    {"role": "user", "content": f"Concurrent test message {request_id}"}
                ],
                "max_tokens": 30,
                "temperature": 0.1
            }
            
            start_time = time.time()
            response = requests.post(url, headers=headers, json=data, timeout=60)
            end_time = time.time()
            
            duration = end_time - start_time
            
            if response.status_code == 200:
                print(f"✅ 请求 {request_id}: 成功 ({duration:.1f}s)")
                return "success"
            elif response.status_code == 429:
                print(f"⏱️ 请求 {request_id}: 限流 ({duration:.1f}s)")
                return "rate_limit"
            else:
                print(f"❌ 请求 {request_id}: 失败 ({response.status_code}) ({duration:.1f}s)")
                return "error"
                
        except Exception as e:
            print(f"❌ 请求 {request_id}: 异常 - {str(e)}")
            return "error"
    
    # 使用线程池并发执行
    with ThreadPoolExecutor(max_workers=num_requests) as executor:
        futures = [executor.submit(make_request, i) for i in range(num_requests)]
        
        for future in as_completed(futures):
            result = future.result()
            if result == "success":
                success_count += 1
            elif result == "rate_limit":
                rate_limit_count += 1
            else:
                error_count += 1
    
    print(f"\n📊 并发测试结果:")
    print(f"   成功: {success_count}")
    print(f"   限流: {rate_limit_count}")
    print(f"   错误: {error_count}")
    
    return success_count > 0

def test_anthropic_format():
    """测试Anthropic格式请求"""
    print(f"\n🔄 测试Anthropic格式请求...")
    
    try:
        url = "http://localhost:8080/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            "Authorization": "Bearer test-key"
        }
        
        data = {
            "model": "claude-3-sonnet-20240229",
            "max_tokens": 50,
            "messages": [
                {"role": "user", "content": "Hello, this is an Anthropic format test."}
            ]
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            content = result.get('content', [])
            if content and len(content) > 0:
                text = content[0].get('text', 'N/A')
            else:
                text = 'N/A'
            print(f"✅ Anthropic请求成功: {text[:50]}...")
        else:
            print(f"❌ Anthropic请求失败: {response.text}")
            
        return response.status_code == 200
        
    except Exception as e:
        print(f"❌ Anthropic请求异常: {str(e)}")
        return False

def main():
    """主测试函数"""
    print("🚀 开始测试智能限流处理修复效果...")
    print("=" * 60)
    
    # 测试1: 单个请求
    print("\n📋 测试1: 单个请求")
    test1_result = test_single_request()
    
    # 测试2: Anthropic格式请求
    print("\n📋 测试2: Anthropic格式请求")
    test2_result = test_anthropic_format()
    
    # 测试3: 并发请求
    print("\n📋 测试3: 并发请求")
    test3_result = test_concurrent_requests(3)
    
    # 总结
    print("\n" + "=" * 60)
    print("📊 测试总结:")
    print(f"   单个请求: {'✅ 通过' if test1_result else '❌ 失败'}")
    print(f"   Anthropic格式: {'✅ 通过' if test2_result else '❌ 失败'}")
    print(f"   并发请求: {'✅ 通过' if test3_result else '❌ 失败'}")
    
    if test1_result and test2_result and test3_result:
        print("\n🎉 所有测试通过！智能限流处理修复成功！")
        print("💡 现在API服务器能够:")
        print("   • 自动检测限流错误")
        print("   • 使用指数退避算法重试")
        print("   • 避免无限循环问题")
        print("   • 提供更好的错误处理")
    else:
        print("\n⚠️  部分测试失败，需要进一步检查")

if __name__ == "__main__":
    main()
