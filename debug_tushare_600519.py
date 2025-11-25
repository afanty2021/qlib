#!/usr/bin/env python3
"""
Tushare数据获取调试脚本

用于调试600519股票只返回23个日线数据的问题。
测试不同的API调用参数和配置选项。

使用方法:
    python debug_tushare_600519.py
"""

import os
import sys
import json
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List

# 添加qlib路径
sys.path.insert(0, '/Users/berton/Github/qlib')

try:
    import tushare as ts
except ImportError:
    print("❌ 请先安装tushare: pip install tushare")
    sys.exit(1)

class TushareDebugger:
    """Tushare数据获取调试器"""

    def __init__(self, token: str = None):
        """
        初始化调试器

        Args:
            token: Tushare API Token
        """
        self.token = token or os.getenv('TUSHARE_TOKEN')
        if not self.token:
            print("❌ 错误: 未设置TUSHARE_TOKEN环境变量或传入token")
            sys.exit(1)

        # 初始化tushare
        ts.set_token(self.token)
        self.pro = ts.pro_api()

        print(f"✅ Tushare初始化成功")
        print(f"🔑 Token: {self.token[:10]}...")
        print()

    def test_token_permissions(self) -> Dict[str, Any]:
        """
        测试Token权限和配额

        Returns:
            权限信息字典
        """
        print("🔍 测试Token权限和配额...")

        try:
            # 测试基础API调用
            print("  📊 测试基础查询...")

            # 获取交易日期
            today = datetime.now().strftime('%Y%m%d')
            one_year_ago = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')

            # 测试 simplest query
            cal_result = self.pro.trade_cal(exchange='SSE',
                                           start_date='20240101',
                                           end_date='20240110')

            permissions = {
                "token_valid": True,
                "basic_access": len(cal_result) > 0,
                "api_response": "success" if len(cal_result) > 0 else "failed",
                "sample_data_count": len(cal_result)
            }

            print(f"  ✅ Token有效: {permissions['token_valid']}")
            print(f"  ✅ 基础访问: {permissions['basic_access']}")
            print(f"  📈 样本数据量: {permissions['sample_data_count']}")

            return permissions

        except Exception as e:
            print(f"  ❌ Token权限测试失败: {str(e)}")
            return {
                "token_valid": False,
                "error": str(e),
                "api_response": "failed"
            }

    def debug_600519_data(self) -> Dict[str, Any]:
        """
        调试600519的数据获取问题

        Returns:
            调试结果字典
        """
        print("🔍 调试600519(贵州茅台)数据获取...")

        results = {}
        stock_code = "600519.SH"

        # 定义测试时间范围
        test_ranges = [
            ("最近一个月", "20241101", "20241130"),
            ("最近三个月", "20240901", "20241130"),
            ("最近半年", "20240501", "20241130"),
            ("最近一年", "20231201", "20241130"),
            ("2024全年", "20240101", "20241201"),
            ("2023全年", "20230101", "20231231"),
        ]

        for desc, start_date, end_date in test_ranges:
            print(f"\n  📅 测试时间范围: {desc} ({start_date} - {end_date})")

            try:
                # 方法1: 使用pro_api直接调用
                print(f"    🔹 方法1: pro.daily()")
                df1 = self.pro.daily(ts_code=stock_code,
                                    start_date=start_date,
                                    end_date=end_date)
                count1 = len(df1)
                print(f"      📊 返回数据量: {count1}")

                if count1 > 0:
                    print(f"      📅 数据范围: {df1['trade_date'].min()} - {df1['trade_date'].max()}")
                    print(f"      💰 价格范围: {df1['close'].min():.2f} - {df1['close'].max():.2f}")

                results[f"{desc}_method1"] = {
                    "count": count1,
                    "success": True,
                    "date_range": f"{df1['trade_date'].min()} - {df1['trade_date'].max()}" if count1 > 0 else "N/A"
                }

                # 方法2: 使用std函数（如果可用）
                try:
                    print(f"    🔹 方法2: pro.daily_std()")
                    df2 = self.pro.daily_std(ts_code=stock_code,
                                            start_date=start_date,
                                            end_date=end_date)
                    count2 = len(df2)
                    print(f"      📊 返回数据量: {count2}")

                    results[f"{desc}_method2"] = {
                        "count": count2,
                        "success": True
                    }

                except Exception as e:
                    print(f"      ❌ 方法2失败: {str(e)}")
                    results[f"{desc}_method2"] = {
                        "count": 0,
                        "success": False,
                        "error": str(e)
                    }

                # 检查是否有交易日历问题
                try:
                    print(f"    🔹 检查交易日历...")
                    cal_df = self.pro.trade_cal(exchange='SSE',
                                               start_date=start_date,
                                               end_date=end_date,
                                               is_open='1')
                    trading_days = len(cal_df)
                    print(f"      📊 交易日数量: {trading_days}")

                    results[f"{desc}_calendar"] = {
                        "trading_days": trading_days,
                        "data_coverage_ratio": count1 / trading_days if trading_days > 0 else 0
                    }

                except Exception as e:
                    print(f"      ❌ 交易日历查询失败: {str(e)}")

            except Exception as e:
                print(f"    ❌ 数据获取失败: {str(e)}")
                results[f"{desc}_method1"] = {
                    "count": 0,
                    "success": False,
                    "error": str(e)
                }

        return results

    def test_alternative_stocks(self) -> Dict[str, Any]:
        """
        测试其他股票的数据获取

        Returns:
            其他股票测试结果
        """
        print("\n🔍 测试其他股票数据获取...")

        test_stocks = [
            ("000001.SZ", "平安银行"),
            ("000002.SZ", "万科A"),
            ("600036.SH", "招商银行"),
            ("600000.SH", "浦发银行"),
        ]

        results = {}
        start_date = "20241001"
        end_date = "20241130"

        for stock_code, stock_name in test_stocks:
            print(f"\n  📈 测试股票: {stock_name} ({stock_code})")

            try:
                df = self.pro.daily(ts_code=stock_code,
                                   start_date=start_date,
                                   end_date=end_date)
                count = len(df)

                print(f"    📊 返回数据量: {count}")

                if count > 0:
                    print(f"    📅 数据范围: {df['trade_date'].min()} - {df['trade_date'].max()}")

                results[stock_code] = {
                    "name": stock_name,
                    "count": count,
                    "success": True,
                    "date_range": f"{df['trade_date'].min()} - {df['trade_date'].max()}" if count > 0 else "N/A"
                }

            except Exception as e:
                print(f"    ❌ 数据获取失败: {str(e)}")
                results[stock_code] = {
                    "name": stock_name,
                    "count": 0,
                    "success": False,
                    "error": str(e)
                }

        return results

    def check_api_limits(self) -> Dict[str, Any]:
        """
        检查API限制和配额

        Returns:
            API限制信息
        """
        print("\n🔍 检查API限制和配额...")

        try:
            # 尝试获取用户信息（如果有权限）
            try:
                user_info = self.pro.user()
                print(f"  👤 用户信息: {user_info}")
            except:
                print("  ⚠️  无法获取用户信息（可能需要更高权限）")

            # 测试不同时间范围的API调用
            test_cases = [
                ("1个月", 30),
                ("3个月", 90),
                ("6个月", 180),
                ("1年", 365),
                ("2年", 730),
            ]

            api_limits = {}

            for desc, days in test_cases:
                end_date = datetime.now().strftime('%Y%m%d')
                start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

                try:
                    # 测试单次请求的时间范围限制
                    df = self.pro.daily(ts_code='000001.SZ',
                                       start_date=start_date,
                                       end_date=end_date)

                    api_limits[desc] = {
                        "days": days,
                        "success": True,
                        "count": len(df)
                    }

                    print(f"  ✅ {desc}: 成功获取 {len(df)} 条数据")

                except Exception as e:
                    api_limits[desc] = {
                        "days": days,
                        "success": False,
                        "error": str(e)
                    }

                    print(f"  ❌ {desc}: 失败 - {str(e)}")

            return api_limits

        except Exception as e:
            print(f"  ❌ API限制检查失败: {str(e)}")
            return {"error": str(e)}

    def generate_debug_report(self) -> Dict[str, Any]:
        """
        生成完整的调试报告

        Returns:
            完整调试报告
        """
        print("🔍 开始生成完整调试报告...")
        print("=" * 60)

        report = {
            "timestamp": datetime.now().isoformat(),
            "token_info": self.test_token_permissions(),
            "600519_debug": self.debug_600519_data(),
            "other_stocks": self.test_alternative_stocks(),
            "api_limits": self.check_api_limits(),
        }

        print("\n" + "=" * 60)
        print("📋 调试报告总结:")
        print("=" * 60)

        # 分析结果
        token_valid = report["token_info"].get("token_valid", False)
        print(f"🔑 Token状态: {'✅ 有效' if token_valid else '❌ 无效'}")

        # 分析600519数据问题
        debug_600519 = report["600519_debug"]
        recent_year_data = debug_600519.get("最近一年_method1", {})
        data_count = recent_year_data.get("count", 0)

        print(f"📊 600519最近一年数据量: {data_count} 条")

        if data_count < 200:  # 正常情况下一年应该有约240-250个交易日
            print(f"⚠️  数据量异常少！正常年份应该有200+个交易日")

            # 可能的原因分析
            if data_count == 23:
                print("🔍 可能原因分析:")
                print("  1. API时间范围限制 - 可能需要分批获取")
                print("  2. Token权限限制 - 可能只有部分时间范围权限")
                print("  3. 股票上市时间 - 检查600519实际上市时间")
                print("  4. 数据源问题 - Tushare端数据缺失")

        # 对比其他股票
        other_stocks = report["other_stocks"]
        successful_stocks = [k for k, v in other_stocks.items() if v.get("success", False)]
        print(f"📈 其他股票测试成功数: {len(successful_stocks)}/{len(other_stocks)}")

        if len(successful_stocks) == 0:
            print("❌ 所有股票数据获取都失败，可能是Token或网络问题")
        elif len(successful_stocks) < len(other_stocks):
            print("⚠️  部分股票数据获取失败，可能是权限或数据问题")
        else:
            print("✅ 其他股票数据获取正常，问题可能特定于600519")

        return report

    def save_report(self, report: Dict[str, Any], filename: str = "tushare_debug_report.json"):
        """
        保存调试报告到文件

        Args:
            report: 调试报告
            filename: 文件名
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2, default=str)
            print(f"\n💾 调试报告已保存到: {filename}")
        except Exception as e:
            print(f"\n❌ 保存报告失败: {str(e)}")


def main():
    """主函数"""
    print("🔍 Tushare数据获取调试工具")
    print("=" * 60)

    # 从配置文件读取token
    config_file = "/Users/berton/Github/qlib/demo_tushare_config.json"
    token = None

    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                token = config.get('token')
                print(f"✅ 从配置文件读取Token: {token[:10] if token else 'None'}...")
        except Exception as e:
            print(f"⚠️  读取配置文件失败: {str(e)}")

    # 初始化调试器
    debugger = TushareDebugger(token)

    # 生成调试报告
    report = debugger.generate_debug_report()

    # 保存报告
    debugger.save_report(report)

    print("\n🎯 建议的解决方案:")
    print("=" * 60)

    data_count = report["600519_debug"].get("最近一年_method1", {}).get("count", 0)

    if data_count == 23:
        print("1. 🕐 分批获取数据:")
        print("   - Tushare可能对单次请求的时间范围有限制")
        print("   - 建议按月或季度分批获取数据")
        print()
        print("2. 🔐 检查Token权限:")
        print("   - 确认Token是否有足够的历史数据权限")
        print("   - 考虑升级到更高权限的账户")
        print()
        print("3. 📡 使用Qlib集成:")
        print("   - 使用Qlib的Tushare数据提供者")
        print("   - 内置缓存和重试机制")
        print()
        print("4. 🔄 实现数据合并:")
        print("   - 多次请求获取不同时间范围")
        print("   - 合并数据以获得完整历史")


if __name__ == "__main__":
    main()