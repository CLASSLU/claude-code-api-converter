#!/usr/bin/env python3
"""
优化版测试运行脚本
支持不同类型的测试执行和覆盖率报告
"""

import sys
import argparse
import subprocess
import os
from pathlib import Path


def run_command(cmd, description=""):
    """运行命令并处理结果"""
    print(f"\n{'='*60}")
    if description:
        print(f"运行: {description}")
    print(f"命令: {' '.join(cmd)}")
    print('='*60)

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("警告:", result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"错误: {e}")
        print("标准输出:", e.stdout)
        print("错误输出:", e.stderr)
        return False


def run_unit_tests(coverage=False, verbose=False):
    """运行单元测试"""
    cmd = ["python", "-m", "pytest", "tests/unit/", "-v"]

    if coverage:
        cmd.extend([
            "--cov=app",
            "--cov-report=html",
            "--cov-report=term-missing",
            "--cov-fail-under=80"
        ])

    if verbose:
        cmd.append("-vv")

    return run_command(cmd, "单元测试")


def run_integration_tests(verbose=False):
    """运行集成测试"""
    cmd = ["python", "-m", "pytest", "tests/integration/", "-v"]

    if verbose:
        cmd.append("-vv")

    return run_command(cmd, "集成测试")


def run_performance_tests(benchmark=False, verbose=False):
    """运行性能测试"""
    cmd = ["python", "-m", "pytest", "tests/performance/", "-m", "performance", "-v"]

    if benchmark:
        cmd.append("--benchmark-only")

    if verbose:
        cmd.append("-vv")

    return run_command(cmd, "性能测试")


def run_all_tests(coverage=False, verbose=False):
    """运行所有测试"""
    print("运行完整的测试套件...")

    # 单元测试
    unit_success = run_unit_tests(coverage=coverage, verbose=verbose)
    if not unit_success:
        print("单元测试失败，停止执行")
        return False

    # 集成测试
    integration_success = run_integration_tests(verbose=verbose)
    if not integration_success:
        print("集成测试失败，停止执行")
        return False

    # 性能测试
    performance_success = run_performance_tests(verbose=verbose)
    if not performance_success:
        print("性能测试失败，停止执行")
        return False

    return True


def run_specific_tests(test_path, coverage=False, verbose=False):
    """运行特定测试"""
    cmd = ["python", "-m", "pytest", test_path, "-v"]

    if coverage:
        cmd.extend([
            "--cov=app",
            "--cov-report=term-missing"
        ])

    if verbose:
        cmd.append("-vv")

    return run_command(cmd, f"特定测试: {test_path}")


def check_dependencies():
    """检查测试依赖"""
    print("检查测试依赖...")

    required_packages = [
        "pytest",
        "pytest-cov",
        "pytest-asyncio"
    ]

    missing_packages = []

    for package in required_packages:
        try:
            __import__(package)
            print(f"✓ {package}")
        except ImportError:
            print(f"✗ {package} (缺失)")
            missing_packages.append(package)

    if missing_packages:
        print(f"\n请安装缺失的依赖: {' '.join(missing_packages)}")
        print("运行: pip install -r requirements_optimized.txt")
        return False

    print("所有依赖检查通过!")
    return True


def setup_test_environment():
    """设置测试环境"""
    print("设置测试环境...")

    # 设置测试环境变量
    os.environ['TESTING'] = 'true'
    os.environ['LOG_LEVEL'] = 'WARNING'  # 减少测试期间的日志输出

    # 确保测试目录存在
    test_dirs = [
        "tests/unit",
        "tests/integration",
        "tests/performance",
        "logs"
    ]

    for test_dir in test_dirs:
        Path(test_dir).mkdir(parents=True, exist_ok=True)

    print("测试环境设置完成!")


def generate_test_report():
    """生成测试报告"""
    print("\n生成测试报告...")

    # 如果有覆盖率报告，显示总结
    if Path("htmlcov").exists():
        print("HTML覆盖率报告已生成: htmlcov/index.html")

    print("\n测试完成!")
    print("查看详细报告:")
    print("- 覆盖率报告: htmlcov/index.html")
    print("- 性能基准: 查看测试输出")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="测试运行脚本")
    parser.add_argument(
        "command",
        choices=["all", "unit", "integration", "performance", "check", "specific"],
        default="all",
        help="要运行的测试类型"
    )
    parser.add_argument(
        "--coverage", "-c",
        action="store_true",
        help="生成覆盖率报告"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="详细输出"
    )
    parser.add_argument(
        "--benchmark", "-b",
        action="store_true",
        help="运行性能基准测试"
    )
    parser.add_argument(
        "--path", "-p",
        help="特定测试路径 (仅当command为specific时使用)"
    )

    args = parser.parse_args()

    # 检查依赖
    if not check_dependencies():
        sys.exit(1)

    # 设置环境
    setup_test_environment()

    # 运行测试
    success = True

    if args.command == "check":
        # 仅检查依赖
        pass
    elif args.command == "unit":
        success = run_unit_tests(coverage=args.coverage, verbose=args.verbose)
    elif args.command == "integration":
        success = run_integration_tests(verbose=args.verbose)
    elif args.command == "performance":
        success = run_performance_tests(benchmark=args.benchmark, verbose=args.verbose)
    elif args.command == "specific":
        if not args.path:
            print("错误: 使用specific命令时必须指定--path参数")
            sys.exit(1)
        success = run_specific_tests(args.path, coverage=args.coverage, verbose=args.verbose)
    else:  # all
        success = run_all_tests(coverage=args.coverage, verbose=args.verbose)

    # 生成报告
    if success:
        generate_test_report()
        sys.exit(0)
    else:
        print("\n测试失败!")
        sys.exit(1)


if __name__ == "__main__":
    main()