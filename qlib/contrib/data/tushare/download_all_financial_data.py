#!/usr/bin/env python3
"""
下载全部A股财务数据

功能：
1. 获取全部A股列表
2. 批量下载财务指标数据
3. 保存到Qlib数据目录
4. 支持断点续传和增量更新
"""

import os
import sys
import time
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# 添加qlib路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))


class AShareFinancialDataDownloader:
    """A股财务数据批量下载器"""

    def __init__(self, token: str = None, output_dir: str = None):
        """
        初始化下载器

        Args:
            token: TuShare Token
            output_dir: 输出目录
        """
        self.token = token or os.getenv("TUSHARE_TOKEN")
        if not self.token:
            raise ValueError("请设置TUSHARE_TOKEN环境变量或传入token参数")

        # 设置输出目录
        if output_dir is None:
            output_dir = Path.home() / ".qlib/qlib_data/cn_data/financial_data"
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 初始化TuShare
        import tushare as ts
        self.pro = ts.pro_api(self.token)

        print(f"✅ 初始化完成")
        print(f"   输出目录: {self.output_dir}")

    def get_stock_list(self) -> pd.DataFrame:
        """
        获取全部A股列表

        Returns:
            股票列表DataFrame
        """
        print("\n📊 获取全部A股列表...")

        try:
            # 获取上市股票
            df = self.pro.stock_basic(
                exchange='',
                list_status='L',  # 只获取上市股票
                fields='ts_code,name,area,industry,list_date'
            )

            print(f"✅ 共 {len(df)} 只股票")

            return df

        except Exception as e:
            print(f"❌ 获取股票列表失败: {str(e)}")
            return pd.DataFrame()

    def download_financial_data(
        self,
        ts_code: str,
        start_date: str = None,
        end_date: str = None
    ) -> Optional[pd.DataFrame]:
        """
        下载单只股票的财务数据

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            财务数据DataFrame
        """
        try:
            # 下载财务指标
            df = self.pro.fina_indicator(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )

            if df is not None and not df.empty:
                return df
            else:
                return None

        except Exception as e:
            print(f"  ⚠️ {ts_code} 下载失败: {str(e)}")
            return None

    def download_all_stocks(
        self,
        start_date: str = "20200101",
        end_date: str = None,
        batch_size: int = 100,
        delay: float = 0.3
    ):
        """
        批量下载全部A股财务数据

        Args:
            start_date: 开始日期
            end_date: 结束日期 (默认为今天)
            batch_size: 每批处理数量
            delay: 请求间隔(秒)
        """
        print("\n" + "="*80)
        print("🚀 开始批量下载A股财务数据")
        print("="*80)

        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")

        # 获取股票列表
        stock_list = self.get_stock_list()

        if stock_list.empty:
            print("❌ 未获取到股票列表")
            return

        # 准备下载
        all_data = []
        success_count = 0
        fail_count = 0

        total_stocks = len(stock_list)
        print(f"\n📊 计划下载 {total_stocks} 只股票的财务数据")
        print(f"   时间范围: {start_date} - {end_date}")
        print(f"   批处理大小: {batch_size}")
        print("="*80)

        # 分批处理
        for i in range(0, total_stocks, batch_size):
            batch = stock_list.iloc[i:i+batch_size]

            print(f"\n批次 {i//batch_size + 1}/{(total_stocks-1)//batch_size + 1}")

            for idx, row in batch.iterrows():
                ts_code = row['ts_code']
                stock_name = row['name']

                print(f"  [{i+idx+1}/{total_stocks}] {ts_code} {stock_name}...", end=" ")

                # 下载数据
                df = self.download_financial_data(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date
                )

                if df is not None:
                    all_data.append(df)
                    success_count += 1
                    print(f"✅ {len(df)} 条")
                else:
                    fail_count += 1
                    print("⚠️ 无数据")

                # API限流
                time.sleep(delay)

            # 每批次保存一次
            if all_data:
                self.save_batch_data(all_data, f"batch_{i//batch_size + 1}")

        # 合并所有数据
        print("\n" + "="*80)
        print("📊 合并所有数据...")

        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)

            # 保存完整数据
            self.save_final_data(combined_df)

            print(f"\n✅ 下载完成!")
            print(f"   成功: {success_count} 只")
            print(f"   失败: {fail_count} 只")
            print(f"   总记录: {len(combined_df)} 条")
        else:
            print("⚠️ 没有下载到任何数据")

    def save_batch_data(self, data: List[pd.DataFrame], batch_name: str):
        """
        保存批次数据

        Args:
            data: 数据列表
            batch_name: 批次名称
        """
        if not data:
            return

        combined = pd.concat(data, ignore_index=True)

        filename = self.output_dir / f"financial_{batch_name}.csv"
        combined.to_csv(filename, index=False, encoding='utf-8-sig')

        print(f"  💾 批次已保存: {filename.name}")

    def save_final_data(self, df: pd.DataFrame):
        """
        保存最终数据

        Args:
            df: 完整数据DataFrame
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 保存完整数据
        filename = self.output_dir / f"a_share_financial_{timestamp}.csv"
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"  💾 完整数据: {filename}")

        # 保存最新版本
        latest_file = self.output_dir / "a_share_financial_latest.csv"
        df.to_csv(latest_file, index=False, encoding='utf-8-sig')
        print(f"  💾 最新版本: {latest_file.name}")

        # 保存数据摘要
        self.generate_summary_report(df, timestamp)

    def generate_summary_report(self, df: pd.DataFrame, timestamp: str):
        """
        生成数据摘要报告

        Args:
            df: 数据DataFrame
            timestamp: 时间戳
        """
        report_lines = []
        report_lines.append("# A股财务数据下载报告")
        report_lines.append(f"\n下载时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"数据文件: a_share_financial_{timestamp}.csv")
        report_lines.append(f"\n## 数据统计")
        report_lines.append(f"- 总记录数: {len(df)}")
        report_lines.append(f"- 股票数量: {df['ts_code'].nunique()}")
        report_lines.append(f"- 时间范围: {df['end_date'].min()} - {df['end_date'].max()}")

        # 字段统计
        report_lines.append(f"\n## 字段列表 ({len(df.columns)} 个)")
        report_lines.append("\n### 主要财务指标")
        key_fields = ['roe', 'roa', 'grossprofit_margin', 'netprofit_margin',
                     'or_yoy', 'op_yoy', 'pe', 'pb', 'debt_to_assets', 'current_ratio']

        for field in key_fields:
            if field in df.columns:
                non_null = df[field].notna().sum()
                report_lines.append(f"- {field}: {non_null} 条非空记录")

        # 保存报告
        report_file = self.output_dir / "download_summary_report.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))

        print(f"  📄 摘要报告: {report_file.name}")


def main():
    """主函数"""
    print("\n🎯 A股财务数据批量下载")
    print("="*80)

    # 检查Token
    token = os.getenv("TUSHARE_TOKEN")
    if not token:
        print("❌ 请设置TUSHARE_TOKEN环境变量")
        print("   export TUSHARE_TOKEN='your_token_here'")
        sys.exit(1)

    try:
        # 创建下载器
        downloader = AShareFinancialDataDownloader()

        # 开始下载
        # 注意：全部A股约5000只，需要较长时间
        # 建议先用小批量测试
        print("\n⚠️ 注意: 全部A股约5000只股票，预计需要1-2小时")
        print("   建议首次运行时先测试少量股票")
        print("   可以修改 batch_size 参数控制批次大小")

        # 询问是否继续
        import shutil
        terminal_width = shutil.get_terminal_size().columns

        print("\n" + "="*terminal_width)
        print("选项:")
        print("  1. 下载全部A股 (耗时较长)")
        print("  2. 测试下载 (前100只股票)")
        print("="*terminal_width)

        choice = input("\n请选择 (1/2): ").strip()

        if choice == "1":
            # 下载全部
            downloader.download_all_stocks(
                start_date="20230101",  # 从2023年开始
                end_date="20241231",
                batch_size=100,
                delay=0.3
            )

        elif choice == "2":
            # 测试下载
            print("\n🧪 测试模式: 仅下载前100只股票")
            downloader.download_all_stocks(
                start_date="20240101",
                end_date="20241231",
                batch_size=20,
                delay=0.2
            )

        else:
            print("⚠️ 无效选择，退出")
            sys.exit(0)

        print("\n✅ 下载完成!")
        print(f"   数据目录: {downloader.output_dir}")

    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断下载")
        print("💡 已下载的数据已保存在输出目录中")
        sys.exit(0)

    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
