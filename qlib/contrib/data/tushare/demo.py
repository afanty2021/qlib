#!/usr/bin/env python3
"""
TuShare数据源演示

演示如何使用TuShare数据源获取A股数据。
"""

import os
import sys
import pandas as pd
from datetime import datetime

# 添加Qlib路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from qlib.contrib.data.tushare import TuShareConfig, TuShareProvider
from qlib.contrib.data.tushare.utils import (
    TuShareCodeConverter,
    TuShareDataProcessor,
    TuShareDateUtils
)


def demo_basic_usage():
    """演示基本使用"""
    print("🎯 TuShare数据源基本使用演示")
    print("=" * 60)

    # 1. 检查环境变量
    if not os.getenv("TUSHARE_TOKEN"):
        print("⚠️ 警告: 未设置TUSHARE_TOKEN环境变量")
        print("   请设置: export TUSHARE_TOKEN='your_token_here'")
        print("   此演示将跳过实际API调用")
        return

    # 2. 创建配置
    config = TuShareConfig.from_env()
    print(f"✅ 配置加载完成")
    print(f"   - Token: {config.token[:10]}...")
    print(f"   - 缓存启用: {config.enable_cache}")
    print(f"   - 最大重试: {config.max_retries}")

    # 3. 演示工具功能
    print("\n🔧 工具功能演示:")

    # 代码转换
    test_codes = ["000001", "600000", "300001"]
    print("\n   股票代码转换:")
    for code in test_codes:
        tushare_code = TuShareCodeConverter.to_tushare_format(code)
        qlib_code = TuShareCodeConverter.to_qlib_format(tushare_code)
        print(f"     {code} -> {tushare_code} -> {qlib_code}")

    # 日期转换
    test_dates = ["2024-01-01", "2024/01/01", "20240101"]
    print("\n   日期转换:")
    for date in test_dates:
        tushare_date = TuShareDateUtils.to_tushare_date(date)
        dt_obj = TuShareDateUtils.from_tushare_date(tushare_date)
        print(f"     {date} -> {tushare_date} -> {dt_obj.strftime('%Y-%m-%d')}")

    # 4. 模拟数据处理
    print("\n📊 数据处理演示:")

    # 创建模拟交易数据
    sample_data = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=10),
        "open": [10.0, 10.2, 10.5, 10.3, 10.8, 11.0, 10.9, 11.2, 11.5, 11.3],
        "high": [10.3, 10.6, 10.8, 10.7, 11.1, 11.3, 11.2, 11.6, 11.8, 11.5],
        "low": [9.8, 10.0, 10.2, 10.0, 10.5, 10.7, 10.6, 10.9, 11.1, 10.9],
        "close": [10.2, 10.4, 10.6, 10.5, 10.9, 11.1, 11.0, 11.4, 11.6, 11.2],
        "volume": [1000, 1200, 900, 1100, 1300, 1500, 1200, 1400, 1600, 1300]
    })

    print(f"   原始数据: {sample_data.shape}")
    print(f"   数据列: {list(sample_data.columns)}")

    # 数据验证
    is_valid, errors = TuShareDataProcessor.validate_trading_data(sample_data)
    print(f"   数据验证: {'✅ 通过' if is_valid else '❌ 失败'}")
    if errors:
        print(f"   错误: {errors}")

    # 计算技术指标
    indicators_df = TuShareDataProcessor.calculate_technical_indicators(sample_data)
    indicator_cols = [col for col in indicators_df.columns if col.startswith(('ma_', 'rsi', 'macd'))]
    print(f"   技术指标: {indicator_cols}")

    if indicator_cols:
        print(f"   最新指标值:")
        latest_values = indicators_df[indicator_cols].iloc[-1]
        for col, val in latest_values.items():
            print(f"     {col}: {val:.4f}")


def demo_config_management():
    """演示配置管理"""
    print("\n📋 配置管理演示")
    print("=" * 60)

    # 1. 从环境变量创建配置
    env_config = TuShareConfig.from_env()
    print("🌍 从环境变量创建配置:")
    print(f"   - 缓存目录: {env_config.cache_dir}")
    print(f"   - 缓存TTL: {env_config.cache_ttl}秒")

    # 2. 从字典创建配置
    dict_config = TuShareConfig.from_dict({
        "token": "demo_token",
        "max_retries": 5,
        "enable_cache": True,
        "rate_limit": 180
    })
    print("\n📖 从字典创建配置:")
    print(f"   - Token: {dict_config.token}")
    print(f"   - 最大重试: {dict_config.max_retries}")
    print(f"   - 频率限制: {dict_config.rate_limit}")

    # 3. 配置合并
    merged_config = dict_config.merge_with(env_config)
    print("\n🔄 配置合并:")
    print(f"   - Token: {merged_config.token[:10] if merged_config.token else 'None'}...")
    print(f"   - 最大重试: {merged_config.max_retries}")
    print(f"   - 频率限制: {merged_config.rate_limit}")

    # 4. 保存配置到文件
    try:
        config_path = "demo_tushare_config.json"
        dict_config.save_to_file(config_path, format="json")
        print(f"\n💾 配置已保存到: {config_path}")

        # 从文件加载配置
        loaded_config = TuShareConfig.from_file(config_path)
        print(f"✅ 从文件加载配置成功: {loaded_config.token}")
    except Exception as e:
        print(f"⚠️ 配置文件操作失败: {e}")


def demo_performance_features():
    """演示性能特性"""
    print("\n⚡ 性能特性演示")
    print("=" * 60)

    # 1. 缓存系统演示
    config = TuShareConfig(enable_cache=True, cache_ttl=3600)

    from qlib.contrib.data.tushare.cache import TuShareCacheManager
    cache_manager = TuShareCacheManager(config)

    # 演示缓存键生成
    keys = []
    for i in range(5):
        key = cache_manager.generate_key("demo", f"symbol_{i}", "20240101", "20240131")
        keys.append(key)

    print(f"🔑 缓存键生成:")
    for i, key in enumerate(keys):
        print(f"   symbol_{i}: {key[:16]}...")

    # 演示缓存存取
    test_data = {"price": 10.5, "volume": 1000, "timestamp": datetime.now()}
    cache_manager.set(keys[0], test_data, level="memory")
    retrieved_data = cache_manager.get(keys[0], level="memory")

    print(f"\n💾 缓存存取:")
    print(f"   原始数据: {test_data}")
    print(f"   缓存数据: {retrieved_data}")
    print(f"   数据一致: {'✅' if retrieved_data == test_data else '❌'}")

    # 2. 缓存统计
    stats = cache_manager.get_stats()
    print(f"\n📊 缓存统计:")
    print(f"   - 启用状态: {stats['enabled']}")
    if stats.get("memory"):
        mem_stats = stats["memory"]
        print(f"   - 内存缓存: {mem_stats['size']} 条目")
        print(f"   - 使用率: {mem_stats['usage_ratio']:.1%}")

    # 3. 数据处理性能
    print(f"\n🚀 数据处理性能:")

    # 创建较大的测试数据集
    large_data = pd.DataFrame({
        "date": pd.date_range("2020-01-01", periods=1000),
        "open": [10.0 + i * 0.001 for i in range(1000)],
        "high": [10.2 + i * 0.001 for i in range(1000)],
        "low": [9.8 + i * 0.001 for i in range(1000)],
        "close": [10.1 + i * 0.001 for i in range(1000)],
        "volume": [1000 + i * 10 for i in range(1000)]
    })

    import time

    # 数据验证性能
    start_time = time.time()
    is_valid, errors = TuShareDataProcessor.validate_trading_data(large_data)
    validation_time = time.time() - start_time
    print(f"   - 数据验证: {validation_time:.4f}秒 ({len(large_data)}行)")

    # 技术指标计算性能
    start_time = time.time()
    indicators_df = TuShareDataProcessor.calculate_technical_indicators(large_data)
    calculation_time = time.time() - start_time
    print(f"   - 指标计算: {calculation_time:.4f}秒 ({len(indicators_df)}行)")

    # 数据清洗性能
    start_time = time.time()
    cleaned_data = TuShareDataProcessor.clean_trading_data(large_data)
    cleaning_time = time.time() - start_time
    print(f"   - 数据清洗: {cleaning_time:.4f}秒 ({len(cleaned_data)}行)")


def demo_error_handling():
    """演示错误处理"""
    print("\n🛡️ 错误处理演示")
    print("=" * 60)

    from qlib.contrib.data.tushare.exceptions import (
        TuShareConfigError,
        TuShareDataError
    )

    # 1. 配置错误演示
    print("1️⃣ 配置错误处理:")
    try:
        invalid_config = TuShareConfig(
            max_retries=-1,  # 无效值
            log_level="INVALID_LEVEL"  # 无效日志级别
        )
    except TuShareConfigError as e:
        print(f"   ✅ 成功捕获配置错误: {e.error_code}")
        print(f"   详情: {len(e.details.get('validation_errors', []))} 个验证错误")

    # 2. 数据验证错误演示
    print("\n2️⃣ 数据验证错误处理:")
    # 创建包含无效数据的DataFrame
    invalid_data = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=3),
        "open": [-1, 0, 10],  # 负价格和零价格
        "high": [5, 15, 8],   # high < low
        "low": [8, 5, 15],    # low > high
        "close": [12, 8, 12],  # close超出范围
        "volume": [-100, 1000, 500]  # 负成交量
    })

    is_valid, errors = TuShareDataProcessor.validate_trading_data(invalid_data)
    if not is_valid:
        print(f"   ✅ 成功检测到 {len(errors)} 个数据错误:")
        for i, error in enumerate(errors, 1):
            print(f"     {i}. {error}")

    # 3. 字段验证错误演示
    print("\n3️⃣ 字段验证错误处理:")
    incomplete_data = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=3),
        "close": [10.0, 10.5, 11.0]
        # 缺少必需的字段: open, high, low, volume
    })

    try:
        from qlib.contrib.data.tushare.field_mapping import TuShareFieldMapping
        required_fields = ["open", "high", "low", "close", "volume"]
        TuShareFieldMapping.validate_required_fields(incomplete_data, required_fields)
    except TuShareDataError as e:
        print(f"   ✅ 成功捕获字段验证错误")
        print(f"   缺少字段: {e.details.get('missing_fields', [])}")


def main():
    """主演示函数"""
    print("🎪 TuShare数据源完整演示")
    print("=" * 80)

    try:
        demo_basic_usage()
        demo_config_management()
        demo_performance_features()
        demo_error_handling()

        print("\n" + "=" * 80)
        print("🎉 演示完成！")
        print("=" * 80)

        print("\n📚 更多信息:")
        print("   - 文档: qlib/contrib/data/tushare/README.md")
        print("   - 示例: qlib/contrib/data/tushare/example.py")
        print("   - 测试: qlib/contrib/data/tushare/tests/")

    except Exception as e:
        print(f"\n❌ 演示过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()