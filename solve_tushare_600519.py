#!/usr/bin/env python3
"""
解决Tushare 600519数据获取问题

基于调试结果，提供完整的解决方案来获取600519的完整历史数据。

主要问题:
1. Token无效/过期
2. API调用限制
3. 时间范围限制
4. 数据分批获取

解决方案:
1. 验证和更新Token
2. 实现分批数据获取
3. 使用Qlib Tushare集成
4. 配置优化和缓存
"""

import os
import sys
import json
import pandas as pd
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

# 添加qlib路径
sys.path.insert(0, '/Users/berton/Github/qlib')

class Tushare600519Solution:
    """解决600519数据获取问题的完整方案"""

    def __init__(self, config_path: str = "/Users/berton/Github/qlib/demo_tushare_config.json"):
        """
        初始化解决方案

        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.config = self.load_config()
        self.token = self.config.get('token', '')

    def load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ 配置文件加载失败: {str(e)}")
            return {}

    def update_token(self, new_token: str):
        """
        更新Token

        Args:
            new_token: 新的Token
        """
        self.token = new_token
        self.config['token'] = new_token

        # 保存到配置文件
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            print(f"✅ Token已更新并保存到配置文件")
        except Exception as e:
            print(f"⚠️  保存配置文件失败: {str(e)}")

        # 设置环境变量
        os.environ['TUSHARE_TOKEN'] = new_token
        print(f"✅ Token已设置为环境变量")

    def solution_1_direct_api_with_batches(self, stock_code: str = "600519.SH",
                                         start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        解决方案1: 使用直接API分批获取

        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            合并后的完整数据
        """
        print("🔧 解决方案1: 直接API分批获取")
        print("=" * 50)

        if not self.token:
            print("❌ Token未配置，请先设置有效的Tushare Token")
            return pd.DataFrame()

        try:
            import tushare as ts
            ts.set_token(self.token)
            pro = ts.pro_api()

            # 设置默认时间范围
            if not end_date:
                end_date = datetime.now().strftime('%Y%m%d')
            if not start_date:
                start_date = (datetime.now() - timedelta(days=365*3)).strftime('%Y%m%d')

            print(f"📈 获取股票: {stock_code}")
            print(f"📅 时间范围: {start_date} - {end_date}")

            # 分批获取策略
            all_data = []
            batch_size_days = 60  # 每批60天，避免API限制
            current_date = datetime.strptime(start_date, '%Y%m%d')
            end_datetime = datetime.strptime(end_date, '%Y%m%d')

            batch_count = 0
            while current_date < end_datetime:
                batch_count += 1
                batch_start = current_date.strftime('%Y%m%d')
                batch_end = (current_date + timedelta(days=batch_size_days)).strftime('%Y%m%d')

                if batch_end > end_date:
                    batch_end = end_date

                print(f"\n📦 批次 {batch_count}: {batch_start} - {batch_end}")

                try:
                    # 获取单批数据
                    batch_data = pro.daily(
                        ts_code=stock_code,
                        start_date=batch_start,
                        end_date=batch_end,
                        adj='qfq'  # 前复权
                    )

                    if not batch_data.empty:
                        print(f"  ✅ 获取 {len(batch_data)} 条数据")
                        all_data.append(batch_data)
                    else:
                        print(f"  ⚠️  无数据返回")

                    # API限制控制
                    time.sleep(0.5)  # 500ms延迟，避免触发频率限制

                except Exception as e:
                    print(f"  ❌ 批次 {batch_count} 失败: {str(e)}")
                    # 继续下一批，不要因为单批失败而中断
                    continue

                current_date = current_date + timedelta(days=batch_size_days + 1)

            # 合并所有数据
            if all_data:
                print(f"\n🔗 合并 {len(all_data)} 批次数据...")
                full_data = pd.concat(all_data, ignore_index=True)

                # 去重和排序
                full_data = full_data.drop_duplicates(subset=['ts_code', 'trade_date'])
                full_data = full_data.sort_values('trade_date').reset_index(drop=True)

                print(f"✅ 最终数据量: {len(full_data)} 条")
                print(f"📅 数据范围: {full_data['trade_date'].min()} - {full_data['trade_date'].max()}")

                return full_data
            else:
                print("❌ 所有批次都失败，未获取到数据")
                return pd.DataFrame()

        except Exception as e:
            print(f"❌ 解决方案1执行失败: {str(e)}")
            return pd.DataFrame()

    def solution_2_qlib_integration(self, stock_code: str = "SH600519",
                                   start_time: str = None, end_time: str = None) -> pd.DataFrame:
        """
        解决方案2: 使用Qlib Tushare集成

        Args:
            stock_code: Qlib格式股票代码
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            特征数据DataFrame
        """
        print("\n🔧 解决方案2: Qlib Tushare集成")
        print("=" * 50)

        try:
            from qlib import init
            from qlib.data import D
            from qlib.contrib.data.tushare import TuShareConfig, TuShareProvider

            # 初始化Qlib
            print("🔧 初始化Qlib Tushare数据源...")

            # 配置Tushare
            tushare_config = TuShareConfig(
                token=self.token,
                enable_cache=True,
                cache_ttl=7200,  # 2小时缓存
                max_retries=5,
                rate_limit=180,  # 每分钟180次
                validate_data=True,
                adjust_price=True
            )

            # 使用Qlib的provider模式初始化
            provider_uri = f"tushare:{self.token}"

            init(
                provider_uri=provider_uri,
                default_conf={
                    "tushare": {
                        "token": self.token,
                        "enable_cache": True,
                        "cache_ttl": 7200
                    }
                }
            )

            print("✅ Qlib初始化成功")

            # 设置时间范围
            if not end_time:
                end_time = datetime.now().strftime('%Y-%m-%d')
            if not start_time:
                start_time = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

            print(f"📈 获取股票: {stock_code}")
            print(f"📅 时间范围: {start_time} - {end_time}")

            # 获取交易日历
            print("📅 获取交易日历...")
            calendar = D.calendar(start_time=start_time, end_time=end_time)
            print(f"  ✅ 交易日数量: {len(calendar)}")

            # 获取特征数据
            print("📊 获取特征数据...")
            instruments = [stock_code]
            fields = ["close", "open", "high", "low", "volume", "amount"]

            features = D.features(
                instruments=instruments,
                fields=fields,
                start_time=start_time,
                end_time=end_time
            )

            print(f"✅ 特征数据形状: {features.shape}")
            print(f"📅 数据范围: {features.index.get_level_values('datetime').min()} - {features.index.get_level_values('datetime').max()}")

            return features

        except Exception as e:
            print(f"❌ 解决方案2执行失败: {str(e)}")
            return pd.DataFrame()

    def solution_3_custom_provider(self) -> pd.DataFrame:
        """
        解决方案3: 自定义数据提供者

        Returns:
            自定义提供者获取的数据
        """
        print("\n🔧 解决方案3: 自定义数据提供者")
        print("=" * 50)

        try:
            from qlib.contrib.data.tushare import TuShareProvider, TuShareConfig

            # 创建自定义配置
            config = TuShareConfig(
                token=self.token,
                enable_cache=True,
                cache_ttl=86400,  # 24小时缓存
                max_retries=5,
                retry_backoff=2.0,
                timeout=60.0,
                rate_limit=120,  # 更保守的频率限制
                validate_data=True,
                adjust_price=True,
                remove_holidays=True
            )

            print("🔧 使用自定义数据提供者...")

            with TuShareProvider(config) as provider:
                # 获取交易日历
                print("📅 获取交易日历...")
                start_time = "2023-01-01"
                end_time = "2024-11-30"

                calendar = provider.calendar(start_time=start_time, end_time=end_time)
                print(f"  ✅ 交易日数量: {len(calendar)}")

                # 获取股票列表
                print("📈 获取股票列表...")
                instruments = provider.instruments(market="csi300")
                print(f"  ✅ 股票数量: {len(instruments)}")

                # 检查600519是否在列表中
                target_code = "SH600519"
                if target_code in instruments:
                    print(f"  ✅ 找到目标股票: {target_code}")
                else:
                    print(f"  ❌ 未找到目标股票: {target_code}")
                    print(f"  📋 可用股票示例: {list(instruments.keys())[:5]}")
                    return pd.DataFrame()

                # 获取特征数据
                print("📊 获取特征数据...")
                features = provider.features(
                    instruments=[target_code],
                    fields=["close", "open", "high", "low", "volume", "amount"],
                    start_time=start_time,
                    end_time=end_time
                )

                print(f"✅ 特征数据形状: {features.shape}")
                if not features.empty:
                    print(f"📅 数据范围: {features.index.min()} - {features.index.max()}")

                return features

        except Exception as e:
            print(f"❌ 解决方案3执行失败: {str(e)}")
            return pd.DataFrame()

    def solution_4_fallback_alternative(self) -> pd.DataFrame:
        """
        解决方案4: 备选数据源

        Returns:
            备选数据源的数据
        """
        print("\n🔧 解决方案4: 备选数据源")
        print("=" * 50)

        print("📋 备选数据源选项:")
        print("1. 📊 AkShare - 免费A股数据源")
        print("2. 📈 Baostock - 开源A股数据")
        print("3. 🌐 Yahoo Finance - 国际市场数据")
        print("4. 💰 付费数据源 - Wind/同花顺/Choice")

        # 尝试AkShare
        try:
            print("\n🔸 尝试AkShare数据源...")
            import akshare as ak

            # 获取贵州茅台历史数据
            print("📈 获取贵州茅台(600519)数据...")
            stock_data = ak.stock_zh_a_hist(symbol="600519", period="daily",
                                          start_date="20230101", end_date="20241130",
                                          adjust="qfq")

            if not stock_data.empty:
                print(f"✅ AkShare获取成功: {len(stock_data)} 条数据")
                print(f"📅 数据范围: {stock_data['日期'].min()} - {stock_data['日期'].max()}")

                # 重命名列以匹配标准格式
                stock_data = stock_data.rename(columns={
                    '日期': 'date',
                    '开盘': 'open',
                    '收盘': 'close',
                    '最高': 'high',
                    '最低': 'low',
                    '成交量': 'volume',
                    '成交额': 'amount'
                })

                return stock_data
            else:
                print("❌ AkShare返回空数据")

        except ImportError:
            print("⚠️  AkShare未安装，跳过...")
            print("   安装命令: pip install akshare")
        except Exception as e:
            print(f"❌ AkShare获取失败: {str(e)}")

        # 尝试Baostock
        try:
            print("\n🔸 尝试Baostock数据源...")
            import baostock as bs

            # 登录
            bs.login()

            # 获取历史数据
            rs = bs.query_history_k_data_plus(
                "sh.600519",
                "date,open,high,low,close,volume,amount",
                start_date='2023-01-01',
                end_date='2024-11-30',
                frequency="d",
                adjustflag="3"  # 前复权
            )

            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())

            if data_list:
                stock_data = pd.DataFrame(data_list, columns=rs.fields)
                print(f"✅ Baostock获取成功: {len(stock_data)} 条数据")
                print(f"📅 数据范围: {stock_data['date'].min()} - {stock_data['date'].max()}")

                bs.logout()
                return stock_data
            else:
                print("❌ Baostock返回空数据")
                bs.logout()

        except ImportError:
            print("⚠️  Baostock未安装，跳过...")
            print("   安装命令: pip install baostock")
        except Exception as e:
            print(f"❌ Baostock获取失败: {str(e)}")

        return pd.DataFrame()

    def generate_comprehensive_solution(self):
        """生成综合解决方案报告"""
        print("🎯 600519数据获取问题 - 综合解决方案")
        print("=" * 80)

        print("\n📋 问题分析:")
        print("1. ❌ Token无效 - 需要有效的Tushare Token")
        print("2. ⚠️  数据量异常 - 正常年份应该有200+交易日，只获取到23条")
        print("3. 🔄 API限制 - 可能存在时间范围或调用频率限制")
        print("4. 📊 配置问题 - 需要优化配置参数")

        print("\n🔧 推荐解决方案:")
        print("=" * 50)

        print("\n方案1: 更新Token并使用分批获取 ⭐⭐⭐⭐⭐")
        print("   - 获取有效的Tushare Token")
        print("   - 实现分批数据获取避免API限制")
        print("   - 使用前复权数据确保一致性")

        print("\n方案2: 使用Qlib Tushare集成 ⭐⭐⭐⭐")
        print("   - 利用Qlib的完整数据源集成")
        print("   - 内置缓存和重试机制")
        print("   - 统一的数据格式和字段映射")

        print("\n方案3: 自定义数据提供者 ⭐⭐⭐")
        print("   - 完全控制API调用参数")
        print("   - 自定义缓存和重试策略")
        print("   - 适合特定需求场景")

        print("\n方案4: 备选数据源 ⭐⭐")
        print("   - AkShare: 免费A股数据源")
        print("   - Baostock: 开源历史数据")
        print("   - 适合备选或补充数据源")

        print("\n🚀 立即执行步骤:")
        print("=" * 50)

        print("\n步骤1: 验证/更新Token")
        print("   1. 访问 https://tushare.pro 注册/登录")
        print("   2. 获取有效的API Token")
        print("   3. 更新配置文件: demo_tushare_config.json")
        print("   4. 设置环境变量: export TUSHARE_TOKEN='your_token'")

        print("\n步骤2: 安装依赖包")
        print("   pip install tushare qlib pandas")
        print("   pip install akshare baostock  # 备选数据源")

        print("\n步骤3: 测试数据获取")
        print("   python solve_tushare_600519.py")

        print("\n步骤4: 验证数据完整性")
        print("   - 检查数据量是否正常(200+交易日/年)")
        print("   - 验证数据连续性和完整性")
        print("   - 确认价格数据合理性")

    def run_all_solutions(self):
        """运行所有解决方案"""
        print("🚀 运行所有解决方案...")
        print("=" * 80)

        solutions_results = {}

        # 方案1: 直接API分批获取
        if self.token:
            print("\n🔸 尝试解决方案1...")
            result1 = self.solution_1_direct_api_with_batches()
            solutions_results['direct_api'] = not result1.empty
            if not result1.empty:
                print(f"✅ 方案1成功: {len(result1)} 条数据")
            else:
                print("❌ 方案1失败")
        else:
            print("⚠️  跳过方案1: Token未配置")
            solutions_results['direct_api'] = False

        # 方案2: Qlib集成
        if self.token:
            print("\n🔸 尝试解决方案2...")
            result2 = self.solution_2_qlib_integration()
            solutions_results['qlib_integration'] = not result2.empty
            if not result2.empty:
                print(f"✅ 方案2成功: {result2.shape}")
            else:
                print("❌ 方案2失败")
        else:
            print("⚠️  跳过方案2: Token未配置")
            solutions_results['qlib_integration'] = False

        # 方案3: 自定义提供者
        if self.token:
            print("\n🔸 尝试解决方案3...")
            result3 = self.solution_3_custom_provider()
            solutions_results['custom_provider'] = not result3.empty
            if not result3.empty:
                print(f"✅ 方案3成功: {result3.shape}")
            else:
                print("❌ 方案3失败")
        else:
            print("⚠️  跳过方案3: Token未配置")
            solutions_results['custom_provider'] = False

        # 方案4: 备选数据源
        print("\n🔸 尝试解决方案4...")
        result4 = self.solution_4_fallback_alternative()
        solutions_results['alternative_source'] = not result4.empty
        if not result4.empty:
            print(f"✅ 方案4成功: {len(result4)} 条数据")
        else:
            print("❌ 方案4失败")

        # 总结
        print("\n" + "=" * 80)
        print("📊 解决方案执行结果总结:")
        print("=" * 80)

        for solution, success in solutions_results.items():
            status = "✅ 成功" if success else "❌ 失败"
            print(f"{solution:20}: {status}")

        successful_count = sum(solutions_results.values())
        print(f"\n🎯 成功方案数: {successful_count}/{len(solutions_results)}")

        if successful_count > 0:
            print("\n🎉 恭喜！至少有一个解决方案成功")
            print("💡 建议使用成功的方案作为主要数据源")
        else:
            print("\n⚠️  所有方案都失败，建议:")
            print("   1. 检查网络连接")
            print("   2. 验证Token有效性")
            print("   3. 安装所需依赖包")
            print("   4. 联系技术支持")


def main():
    """主函数"""
    print("🔧 Tushare 600519数据获取问题解决方案")
    print("=" * 80)

    # 创建解决方案实例
    solution = Tushare600519Solution()

    # 显示综合解决方案
    solution.generate_comprehensive_solution()

    # 询问是否立即执行
    print(f"\n❓ 是否立即执行所有解决方案? (y/n): ", end="")
    try:
        choice = input().lower().strip()
        if choice == 'y' or choice == 'yes':
            solution.run_all_solutions()
        else:
            print("\n💡 请按照上述步骤手动执行解决方案")
    except KeyboardInterrupt:
        print("\n\n👋 用户取消执行")
    except Exception as e:
        print(f"\n❌ 执行过程出错: {str(e)}")


if __name__ == "__main__":
    main()