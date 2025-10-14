import requests
import json
import time

def test_simple_request():
    """测试简单请求的响应格式"""
    
    # 读取测试请求
    with open('test_simple_request.json', 'r', encoding='utf-8') as f:
        request_data = json.load(f)
    
    print("🔥 发送简单请求测试...")
    print(f"请求内容: {json.dumps(request_data, indent=2)}")
    
    start_time = time.time()
    
    try:
        response = requests.post(
            'http://localhost:8080/v1/messages',
            headers={'Content-Type': 'application/json'},
            json=request_data,
            timeout=30
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"\n📊 响应状态: {response.status_code}")
        print(f"⏱️ 响应时间: {duration:.2f}秒")
        
        if response.status_code == 200:
            response_data = response.json()
            print(f"\n✅ 响应格式验证:")
            print(f"- ID: {response_data.get('id', '❌ 缺失')}")
            print(f"- Type: {response_data.get('type', '❌ 缺失')}")
            print(f"- Role: {response_data.get('role', '❌ 缺失')}")
            print(f"- Model: {response_data.get('model', '❌ 缺失')}")
            print(f"- Stop Reason: {response_data.get('stop_reason', '❌ 缺失')}")
            print(f"- Content Length: {len(response_data.get('content', []))}")
            
            # 检查usage字段
            usage = response_data.get('usage', {})
            print(f"- Usage: input_tokens={usage.get('input_tokens', '❌')}, output_tokens={usage.get('output_tokens', '❌')}")
            
            # 保存响应到文件
            with open('simple_response.json', 'w', encoding='utf-8') as f:
                json.dump(response_data, f, indent=2, ensure_ascii=False)
            print(f"\n💾 响应已保存到 simple_response.json")
            
        else:
            print(f"❌ 请求失败: {response.text}")
            
    except Exception as e:
        print(f"❌ 异常: {str(e)}")

if __name__ == "__main__":
    test_simple_request()
