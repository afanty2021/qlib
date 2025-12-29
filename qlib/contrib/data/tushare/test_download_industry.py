#!/usr/bin/env python3
"""
行业板块数据下载测试脚本

测试下载功能但不实际调用API（模拟模式）
"""

import os
import sys
from pathlib import Path

# 添加路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from qlib.contrib.data.tushare.config import TuShareConfig
from qlib.contrib.data.tushare.api_client import TuShareAPIClient


def test_api_connection():
    """测试API连接"""
    print("="*80)
    print("测试TuShare API连接")
    print("="*80)

    token = os.getenv("TUSHARE_TOKEN")
    if not token:
        print("❌ TUSHARE_TOKEN 未设置")
        return False

    print(f"✅ Token: {token[:10]}...")

    try:
        config = TuShareConfig(token=token)
        client = TuShareAPIClient(config)

        # 测试一个小API调用
        print("\n📊 测试API调用（获取股票列表）...")

        # 只获取少量数据测试
        result = client.get_stock_basic(
            list_status="L",
            fields="ts_code,name,industry"
        )

        if result is not None and not result.empty:
            print(f"✅ API连接成功，获取到 {len(result)} 条数据")
            print(f"\n数据样例（前3条）：")
            print(result.head(3).to_string(index=False))
            return True
        else:
            print("⚠️ API返回空数据")
            return False

    except Exception as e:
        print(f"❌ API连接失败: {str(e)}")
        return False


def test_industry_api():
    """测试行业API接口"""
    print("\n" + "="*80)
    print("测试行业板块API接口")
    print("="*80)

    token = os.getenv("TUSHARE_TOKEN")
    if not token:
        print("❌ TUSHARE_TOKEN 未设置")
        return False

    try:
        # 使用原生TuShare API（更稳定）
        import tushare as ts
        ts_client = ts.pro_api(token)

        # 测试行业分类接口（使用index_classify）
        print("\n📊 测试申万2021一级行业接口...")
        result = ts_client.index_classify(level="L1", source="SW2021")

        if result is not None and not result.empty:
            print(f"✅ 获取成功，共 {len(result)} 个一级行业")
            print(f"\n行业列表（前10个）：")
            print(result.head(10)[['industry_code', 'industry_name']].to_string(index=False))
            return True
        else:
            print("⚠️ 返回空数据")
            return False

    except Exception as e:
        print(f"❌ 接口调用失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_concept_api():
    """测试概念板块API接口"""
    print("\n" + "="*80)
    print("测试概念板块API接口")
    print("="*80)

    token = os.getenv("TUSHARE_TOKEN")
    if not token:
        print("❌ TUSHARE_TOKEN 未设置")
        return False

    try:
        # 使用原生TuShare API（更稳定）
        import tushare as ts
        ts_client = ts.pro_api(token)

        # 测试概念板块接口
        print("\n📊 测试概念板块接口...")
        result = ts_client.concept()

        if result is not None and not result.empty:
            print(f"✅ 获取成功，共 {len(result)} 个概念板块")
            print(f"\n概念板块列表（前10个）：")
            if 'concept_name' in result.columns:
                print(result.head(10)[['id', 'concept_name']].to_string(index=False))
            else:
                print(result.head(10).to_string(index=False))
            return True
        else:
            print("⚠️ 返回空数据")
            return False

    except Exception as e:
        print(f"❌ 接口调用失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("\n🧪 行业板块数据下载测试")
    print("="*80)
    print("此脚本测试API接口是否可用")
    print("不会下载大量数据，只进行小规模测试")
    print("="*80)

    results = {}

    # 测试1: API连接
    results['connection'] = test_api_connection()

    # 测试2: 行业接口
    results['industry'] = test_industry_api()

    # 测试3: 概念接口
    results['concept'] = test_concept_api()

    # 汇总结果
    print("\n" + "="*80)
    print("测试结果汇总")
    print("="*80)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")

    success_count = sum(results.values())
    total_count = len(results)

    print(f"\n总计: {success_count}/{total_count} 测试通过")

    if success_count == total_count:
        print("\n✅ 所有测试通过！可以运行完整下载")
        print("\n运行命令:")
        print("  python qlib/contrib/data/tushare/download_industry_data.py")
    else:
        print("\n⚠️ 部分测试失败，请检查:")
        print("  1. Token是否正确")
        print("  2. 网络连接是否正常")
        print("  3. API权限是否足够")

    return success_count == total_count


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
