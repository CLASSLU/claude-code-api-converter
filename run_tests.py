#!/usr/bin/env python3
"""
测试运行脚本
运行所有集成测试
"""

import sys
import os
import unittest
import subprocess
from pathlib import Path

# 添加当前目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

def run_tests():
    """运行所有测试"""
    # 设置测试环境
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['LOG_LEVEL'] = 'ERROR'

    # 发现并运行测试
    loader = unittest.TestLoader()
    start_dir = 'tests'
    suite = loader.discover(start_dir, pattern='test_*.py')

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 返回测试结果
    return result.wasSuccessful()

if __name__ == '__main__':
    print("运行API服务器集成测试...")
    print("=" * 50)

    # 测试前安装依赖
    req_file = Path(__file__).parent / 'requirements.txt'
    if req_file.exists():
        print("安装测试依赖...")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', str(req_file)])
            print("依赖安装完成")
        except subprocess.CalledProcessError as e:
            print(f"依赖安装失败: {e}")
    else:
        print("未找到 requirements.txt，跳过依赖安装")

    success = run_tests()

    if success:
        print("=" * 50)
        print("所有测试通过！")
        sys.exit(0)
    else:
        print("=" * 50)
        print("测试失败！")
        sys.exit(1)