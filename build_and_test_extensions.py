#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
构建和测试Cython扩展的自动化脚本

自动编译高性能Cython扩展并进行性能基准测试。
"""

import os
import sys
import time
import subprocess
import numpy as np
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

def run_command(cmd, cwd=None):
    """运行命令并返回结果"""
    print(f"🔧 运行命令: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        if result.stdout:
            print(f"✅ 输出: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 命令失败: {e}")
        if e.stderr:
            print(f"错误输出: {e.stderr}")
        return False


def check_dependencies():
    """检查依赖"""
    print("📦 检查依赖...")

    try:
        import cython
        print("✅ Cython已安装")
    except ImportError:
        print("❌ Cython未安装")
        print("请安装Cython: pip install cython")
        return False

    try:
        import numpy
        print("✅ NumPy已安装")
    except ImportError:
        print("❌ NumPy未安装")
        print("请安装NumPy: pip install numpy")
        return False

    return True


def build_extensions():
    """构建Cython扩展"""
    print("🔨 构建Cython扩展...")

    ops_dir = Path(__file__).parent / "qlib" / "contrib" / "ops"

    if not ops_dir.exists():
        print(f"❌ 目录不存在: {ops_dir}")
        return False

    # 运行构建
    success = run_command([
        sys.executable, "setup.py", "build_ext", "--inplace"
    ], cwd=str(ops_dir))

    if success:
        print("✅ Cython扩展构建成功")
        return True
    else:
        print("❌ Cython扩展构建失败")
        return False


def test_extensions():
    """测试扩展功能"""
    print("🧪 测试扩展功能...")

    try:
        # 尝试导入扩展
        from qlib.contrib.ops.fast_ops import (
            FastMAD, FastWMA, FastSTD, FastRSI,
            PerformanceBenchmark, fast_mad, fast_wma, fast_std, fast_rsi
        )
        print("✅ 扩展导入成功")

        # 创建测试数据
        test_data = np.random.randn(10000)
        print(f"📊 测试数据大小: {test_data.shape}")

        # 测试各种操作符
        print("\n🚀 测试性能...")

        # MAD测试
        start_time = time.time()
        mad_result = fast_mad(test_data, 20)
        mad_time = time.time() - start_time
        print(f"  MAD计算时间: {mad_time:.4f}s, 结果形状: {mad_result.shape}")

        # WMA测试
        start_time = time.time()
        wma_result = fast_wma(test_data, 20)
        wma_time = time.time() - start_time
        print(f"  WMA计算时间: {wma_time:.4f}s, 结果形状: {wma_result.shape}")

        # STD测试
        start_time = time.time()
        std_result = fast_std(test_data, 20)
        std_time = time.time() - start_time
        print(f"  STD计算时间: {std_time:.4f}s, 结果形状: {std_result.shape}")

        # RSI测试
        start_time = time.time()
        rsi_result = fast_rsi(test_data, 14)
        rsi_time = time.time() - start_time
        print(f"  RSI计算时间: {rsi_time:.4f}s, 结果形状: {rsi_result.shape}")

        # 性能基准测试
        print("\n📈 运行性能基准测试...")
        benchmark = PerformanceBenchmark()
        results = benchmark.benchmark_implementations(
            test_data[:1000],  # 使用较小的测试数据
            window_size=20,
            iterations=100
        )

        print("\n📊 性能对比结果:")
        for op_name, stats in results.items():
            if isinstance(stats, dict):
                speedup = stats.get('speedup', 'N/A')
                print(f"  {op_name}: {speedup}x 加速")

        print("✅ 扩展测试完成")
        return True

    except ImportError as e:
        print(f"❌ 扩展导入失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 测试过程中出错: {e}")
        return False


def test_numpy_fallback():
    """测试NumPy备用实现"""
    print("🔄 测试NumPy备用实现...")

    try:
        # 强制禁用Cython
        from qlib.contrib.ops.fast_ops import FastMAD, FastWMA

        # 创建强制使用NumPy的操作符
        mad_op = FastMAD(window_size=20, fallback_to_numpy=True)
        wma_op = FastWMA(window_size=20, fallback_to_numpy=True)

        test_data = np.random.randn(1000)

        # 测试MAD
        start_time = time.time()
        mad_result = mad_op.compute(test_data)
        mad_time = time.time() - start_time
        print(f"  NumPy MAD时间: {mad_time:.4f}s")

        # 测试WMA
        start_time = time.time()
        wma_result = wma_op.compute(test_data)
        wma_time = time.time() - start_time
        print(f"  NumPy WMA时间: {wma_time:.4f}s")

        print("✅ NumPy备用实现测试完成")
        return True

    except Exception as e:
        print(f"❌ NumPy备用实现测试失败: {e}")
        return False


def clean_build():
    """清理构建文件"""
    print("🧹 清理构建文件...")

    ops_dir = Path(__file__).parent / "qlib" / "contrib" / "ops"

    # 清理常见的构建文件
    cleanup_patterns = [
        "*.so",
        "*.c",
        "*.cpp",
        "build",
        "__pycache__",
        "*.egg-info"
    ]

    import glob
    for pattern in cleanup_patterns:
        for file_path in ops_dir.glob(pattern):
            if file_path.is_file():
                file_path.unlink()
                print(f"  删除文件: {file_path}")
            elif file_path.is_dir():
                import shutil
                shutil.rmtree(file_path)
                print(f"  删除目录: {file_path}")

    print("✅ 清理完成")


def main():
    """主函数"""
    print("🚀 Qlib Cython扩展构建和测试工具")
    print("=" * 50)

    if len(sys.argv) > 1:
        command = sys.argv[1]
    else:
        command = "all"

    print(f"🎯 执行命令: {command}")
    print()

    if command == "check":
        success = check_dependencies()
    elif command == "build":
        success = check_dependencies() and build_extensions()
    elif command == "test":
        success = build_extensions() and test_extensions()
    elif command == "fallback":
        success = test_numpy_fallback()
    elif command == "clean":
        success = clean_build()
    elif command == "all":
        success = (
            check_dependencies() and
            build_extensions() and
            test_extensions() and
            test_numpy_fallback()
        )
    else:
        print(f"❌ 未知命令: {command}")
        print("可用命令: check, build, test, fallback, clean, all")
        return False

    print("\n" + "=" * 50)
    if success:
        print("✅ 操作完成!")
    else:
        print("❌ 操作失败!")

    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)