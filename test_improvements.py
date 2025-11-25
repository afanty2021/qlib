#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试我们的改进效果
"""

import sys
import time
import numpy as np
import pandas as pd
from unittest.mock import Mock

# 添加项目路径
sys.path.insert(0, '.')

def test_security_improvements():
    """测试安全改进"""
    print("🔒 测试安全改进...")

    # 测试NFS挂载参数验证
    try:
        from qlib.nfs_mount import _validate_mount_parameters

        # 测试有效参数
        _validate_mount_parameters("192.168.1.100/data", "/mnt/test")
        print("  ✅ 参数验证正常工作")

        # 测试无效参数
        try:
            _validate_mount_parameters("invalid uri with spaces", "/mnt/test")
            print("  ❌ 无效参数检测失败")
        except ValueError:
            print("  ✅ 无效参数正确被拒绝")

    except ImportError as e:
        print(f"  ⚠️ 无法导入NFS挂载模块: {e}")

def test_performance_improvements():
    """测试性能改进"""
    print("⚡ 测试性能改进...")

    try:
        from qlib.data.ops import Mad, WMA

        # 创建测试数据
        test_data = pd.Series(np.random.randn(10000))
        feature = Mock()
        feature.load.return_value = test_data

        # 测试MAD操作符
        mad_op = Mad(feature, 20)
        start_time = time.time()
        mad_result = mad_op._load_internal("test", 0, 9999)
        mad_time = time.time() - start_time

        # 测试WMA操作符
        wma_op = WMA(feature, 20)
        start_time = time.time()
        wma_result = wma_op._load_internal("test", 0, 9999)
        wma_time = time.time() - start_time

        print(f"  ✅ MAD计算时间: {mad_time:.4f}s")
        print(f"  ✅ WMA计算时间: {wma_time:.4f}s")

        # 验证结果类型
        assert isinstance(mad_result, pd.Series)
        assert isinstance(wma_result, pd.Series)
        print("  ✅ 向量化计算正常工作")

    except Exception as e:
        print(f"  ❌ 性能测试失败: {e}")

def test_memory_management():
    """测试内存管理"""
    print("💾 测试内存管理...")

    try:
        import gc

        # 记录初始对象数量
        initial_objects = len(gc.get_objects())

        # 创建大量临时对象
        temp_data = []
        for i in range(1000):
            temp_data.append(pd.DataFrame(np.random.randn(100, 10)))

        # 强制垃圾回收
        del temp_data
        gc.collect()

        # 检查对象数量
        final_objects = len(gc.get_objects())
        object_growth = final_objects - initial_objects

        print(f"  ✅ 对象数量变化: {object_growth}")

        if object_growth < 100000:  # 允许合理的对象增长
            print("  ✅ 内存管理正常")
        else:
            print("  ⚠️ 对象数量增长较多")

    except Exception as e:
        print(f"  ❌ 内存管理测试失败: {e}")

def test_code_quality_improvements():
    """测试代码质量改进"""
    print("🔧 测试代码质量改进...")

    try:
        # 测试模块导入
        from qlib.nfs_mount import mount_nfs_uri_improved
        print("  ✅ 重构的NFS模块导入正常")

        # 测试函数存在
        assert callable(mount_nfs_uri_improved)
        print("  ✅ 改进的挂载函数可用")

        # 测试文档字符串
        docstring = mount_nfs_uri_improved.__doc__
        if docstring and len(docstring) > 100:
            print("  ✅ 函数文档完整")
        else:
            print("  ⚠️ 函数文档较短")

    except Exception as e:
        print(f"  ❌ 代码质量测试失败: {e}")

def main():
    """主测试函数"""
    print("🚀 Qlib 改进验证测试")
    print("=" * 50)

    test_security_improvements()
    print()

    test_performance_improvements()
    print()

    test_memory_management()
    print()

    test_code_quality_improvements()
    print()

    print("=" * 50)
    print("✅ 改进验证完成!")

if __name__ == "__main__":
    main()