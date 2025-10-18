#!/usr/bin/env python3
"""
Test validation script to trigger PR Review Bot workflow
This script validates the performance optimization and caching mechanisms.
"""

import time
import requests
import json
from typing import Dict, Any

class PerformanceValidator:
    """Test class to validate API performance improvements"""

    def __init__(self, base_url: str = "http://127.0.0.1:10000"):
        self.base_url = base_url
        self.test_results = []

    def test_api_response_time(self) -> Dict[str, Any]:
        """Test API response time with large payload"""
        large_payload = {
            "model": "claude-3-5-haiku-20241022",
            "max_tokens": 100,
            "messages": [
                {
                    "role": "user",
                    "content": "Test message " * 10000  # Large payload test
                }
            ]
        }

        start_time = time.time()
        try:
            response = requests.post(
                f"{self.base_url}/v1/messages",
                json=large_payload,
                timeout=30
            )
            end_time = time.time()

            result = {
                "status_code": response.status_code,
                "response_time": end_time - start_time,
                "payload_size": len(json.dumps(large_payload))
            }

            self.test_results.append(result)
            return result

        except Exception as e:
            return {
                "status_code": 500,
                "response_time": 30.0,
                "error": str(e),
                "payload_size": len(json.dumps(large_payload))
            }

    def test_concurrent_requests(self) -> Dict[str, Any]:
        """Test concurrent request handling"""
        import threading
        import queue

        results_queue = queue.Queue()

        def make_request():
            result = self.test_api_response_time()
            results_queue.put(result)

        # Create 5 concurrent threads
        threads = []
        start_time = time.time()

        for _ in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        end_time = time.time()

        # Collect results
        all_results = []
        while not results_queue.empty():
            all_results.append(results_queue.get())

        avg_response_time = sum(r['response_time'] for r in all_results) / len(all_results)

        return {
            "concurrent_requests": 5,
            "total_time": end_time - start_time,
            "avg_response_time": avg_response_time,
            "individual_results": all_results
        }

    def caching_mechanism_validation(self) -> Dict[str, Any]:
        """Test caching mechanism effectiveness"""
        # First request
        start_time = time.time()
        result1 = self.test_api_response_time()
        first_request_time = time.time() - start_time

        # Second request (should be cached)
        start_time = time.time()
        result2 = self.test_api_response_time()
        second_request_time = time.time() - start_time

        caching_improvement = ((first_request_time - second_request_time) / first_request_time) * 100

        return {
            "first_request_time": first_request_time,
            "second_request_time": second_request_time,
            "caching_improvement_percent": caching_improvement,
            "cache_effective": caching_improvement > 10  # 10% threshold
        }

def main():
    """Main validation function"""
    validator = PerformanceValidator()

    print("🧪 Running API Performance Validation Tests")
    print("=" * 50)

    # Test 1: Basic response time
    print("Test 1: Basic API Response Time")
    result1 = validator.test_api_response_time()
    print(f"  Status: {result1['status_code']}")
    print(f"  Response Time: {result1['response_time']:.2f}s")
    print(f"  Payload Size: {result1['payload_size']} bytes")

    # Test 2: Concurrent requests
    print("\nTest 2: Concurrent Request Handling")
    result2 = validator.test_concurrent_requests()
    print(f"  Concurrent Requests: {result2['concurrent_requests']}")
    print(f"  Total Time: {result2['total_time']:.2f}s")
    print(f"  Avg Response Time: {result2['avg_response_time']:.2f}s")

    # Test 3: Caching mechanism
    print("\nTest 3: Caching Mechanism Validation")
    result3 = validator.caching_mechanism_validation()
    print(f"  First Request: {result3['first_request_time']:.2f}s")
    print(f"  Second Request: {result3['second_request_time']:.2f}s")
    print(f"  Cache Improvement: {result3['caching_improvement_percent']:.1f}%")
    print(f"  Cache Effective: {'✅' if result3['cache_effective'] else '❌'}")

    print("\n" + "=" * 50)
    print("🎯 Test Summary:")

    # Performance criteria
    criteria_met = 0
    total_criteria = 3

    if result1['response_time'] < 5.0:  # Under 5 seconds
        print("✅ Basic response time under 5s")
        criteria_met += 1
    else:
        print("❌ Basic response time too slow")

    if result2['avg_response_time'] < 3.0:  # Under 3 seconds average
        print("✅ Concurrent requests handled efficiently")
        criteria_met += 1
    else:
        print("❌ Concurrent request handling needs improvement")

    if result3['cache_effective']:
        print("✅ Caching mechanism working effectively")
        criteria_met += 1
    else:
        print("❌ Caching mechanism needs optimization")

    print(f"\n🏆 Overall Score: {criteria_met}/{total_criteria} tests passed")

    if criteria_met == total_criteria:
        print("🎉 All performance criteria met!")
        return 0
    else:
        print("⚠️  Some criteria not met, review optimization needed")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())