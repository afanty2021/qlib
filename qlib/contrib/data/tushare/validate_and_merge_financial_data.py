#!/usr/bin/env python3
"""
2000-2025财务数据验证和合并工具

下载完成后的数据处理：
1. 验证所有阶段数据完整性
2. 合并所有阶段数据
3. 去重和数据清洗
4. 生成最终数据集
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

class FinancialDataValidator:
    """财务数据验证器"""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir

    def check_phase_completeness(self) -> Dict[str, pd.DataFrame]:
        """检查所有阶段文件完整性"""
        print("\n📋 检查阶段文件...")
        print("="*80)

        phase_files = sorted(self.data_dir.glob("phase_*.csv"))

        if not phase_files:
            print("❌ 未找到阶段文件")
            return {}

        phases = {}

        for phase_file in phase_files:
            phase_name = phase_file.stem.replace("phase_", "").replace("_", " ")
            df = pd.read_csv(phase_file)

            # 基本统计
            stats = {
                "records": len(df),
                "stocks": df['ts_code'].nunique(),
                "quarters": df['end_date'].nunique(),
                "fields": len(df.columns),
                "size_mb": phase_file.stat().st_size / 1024 / 1024,
                "file": phase_file
            }

            # 年份范围
            df['year'] = df['end_date'].astype(str).str[:4]
            years = sorted(df['year'].unique())
            stats['year_range'] = f"{years[0]}-{years[-1]}" if years else "N/A"

            # 季度分布
            quarter_counts = df['end_date'].value_counts().sort_index()
            stats['quarter_distribution'] = quarter_counts

            phases[phase_name] = df

            print(f"\n✅ {phase_name}")
            print(f"   记录数: {stats['records']:,} 条")
            print(f"   股票数: {stats['stocks']} 只")
            print(f"   季度数: {stats['quarters']} 个")
            print(f"   年份范围: {stats['year_range']}")
            print(f"   字段数: {stats['fields']} 个")
            print(f"   文件大小: {stats['size_mb']:.2f} MB")

        return phases

    def validate_data_quality(self, df: pd.DataFrame) -> Dict:
        """验证数据质量"""
        print("\n🔍 数据质量检查")
        print("="*80)

        report = {}

        # 1. 缺失值检查
        missing_stats = df.isnull().sum()
        missing_pct = (missing_stats / len(df) * 100).round(2)

        high_missing = missing_pct[missing_pct > 50].sort_values(ascending=False)

        report['missing_fields'] = len(high_missing)
        report['total_missing'] = df.isnull().sum().sum()

        print(f"\n缺失值统计:")
        print(f"   总缺失值: {report['total_missing']:,} 个")
        print(f"   高缺失字段(>50%): {report['missing_fields']} 个")

        if len(high_missing) > 0:
            print(f"\n   高缺失字段 Top 10:")
            for field, pct in high_missing.head(10).items():
                print(f"     - {field}: {pct}%")

        # 2. 重复值检查
        duplicates = df.duplicated(subset=['ts_code', 'end_date']).sum()
        report['duplicates'] = duplicates

        print(f"\n重复记录:")
        print(f"   基于(ts_code, end_date)的重复: {duplicates} 条")

        # 3. 数据范围检查
        df['year'] = df['end_date'].astype(str).str[:4]
        year_range = (df['year'].min(), df['year'].max())
        report['year_range'] = year_range

        print(f"\n年份范围:")
        print(f"   {year_range[0]} - {year_range[1]} ({df['year'].nunique()} 年)")

        # 4. 股票覆盖率
        total_stocks = df['ts_code'].nunique()
        report['total_stocks'] = total_stocks

        print(f"\n股票覆盖:")
        print(f"   总股票数: {total_stocks} 只")

        # 5. 季度覆盖率
        quarters = df['end_date'].nunique()
        report['total_quarters'] = quarters

        print(f"\n季度覆盖:")
        print(f"   总季度数: {quarters} 个")

        # 6. 关键字段检查
        key_fields = ['roe', 'roa', 'or_yoy', 'pe', 'pb']
        key_coverage = {}
        for field in key_fields:
            if field in df.columns:
                valid_count = df[field].notna().sum()
                coverage = (valid_count / len(df) * 100)
                key_coverage[field] = coverage
                print(f"   {field}: {coverage:.1f}% 覆盖率")

        report['key_coverage'] = key_coverage

        return report

    def merge_all_phases(self, phases: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """合并所有阶段数据"""
        print("\n🔄 合并所有阶段数据")
        print("="*80)

        if not phases:
            print("❌ 没有阶段数据可合并")
            return pd.DataFrame()

        # 合并
        print(f"\n合并 {len(phases)} 个阶段...")
        combined_df = pd.concat(phases.values(), ignore_index=True)

        print(f"合并前总记录: {len(combined_df):,} 条")

        # 排序（按股票、报告期、公告日期）
        print("\n排序数据...")
        combined_df['end_date'] = combined_df['end_date'].astype(int)
        combined_df = combined_df.sort_values(['ts_code', 'end_date', 'ann_date'])

        # 去重（保留最新公告）
        print("去重处理...")
        before_dedup = len(combined_df)
        combined_df = combined_df.drop_duplicates(
            subset=['ts_code', 'end_date'],
            keep='last'  # 保留最后（最新）的记录
        )
        dedup_count = before_dedup - len(combined_df)

        print(f"去重后总记录: {len(combined_df):,} 条 (删除 {dedup_count} 条重复)")

        return combined_df

    def generate_summary_report(self, merged_df: pd.DataFrame) -> str:
        """生成汇总报告"""
        print("\n📊 生成汇总报告")
        print("="*80)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 统计信息
        total_records = len(merged_df)
        total_stocks = merged_df['ts_code'].nunique()
        total_fields = len(merged_df.columns)
        total_quarters = merged_df['end_date'].nunique()

        # 年份统计
        merged_df['year'] = merged_df['end_date'].astype(str).str[:4]
        year_counts = merged_df['year'].value_counts().sort_index()

        # 报告内容
        report = f"""
# A股财务数据汇总报告 (2000-2025)

> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
> 数据来源: TuShare Pro

## 📊 数据统计

- **总记录数**: {total_records:,} 条
- **股票数量**: {total_stocks} 只
- **数据字段**: {total_fields} 个
- **季度数量**: {total_quarters} 个

## 📅 年份分布

"""

        for year, count in year_counts.items():
            stocks_in_year = merged_df[merged_df['year'] == year]['ts_code'].nunique()
            report += f"- **{year}**: {count:,} 条记录 ({stocks_in_year} 只股票)\n"

        # 字段说明
        report += "\n## 📋 主要字段\n\n"

        key_categories = {
            "基本信息": ["ts_code", "ann_date", "end_date"],
            "每股指标": ["eps", "dt_eps", "bps", "ocfps", "cfps"],
            "盈利能力": ["roe", "roa", "npta", "roic", "grossprofit_margin", "netprofit_margin"],
            "偿债能力": ["debt_to_assets", "current_ratio", "quick_ratio"],
            "运营能力": ["assets_turnover", "ar_turn", "ca_turn"],
            "成长能力": ["or_yoy", "op_yoy", "netprofit_yoy"],
            "估值指标": ["pe", "pb", "ps", "pcf"]
        }

        for category, fields in key_categories.items():
            available_fields = [f for f in fields if f in merged_df.columns]
            if available_fields:
                report += f"**{category}**: {', '.join(available_fields)}\n"

        # 数据质量
        report += "\n## ✅ 数据质量\n\n"

        missing_pct = (merged_df.isnull().sum() / len(merged_df) * 100)
        good_quality_fields = missing_pct[missing_pct < 30]

        report += f"- 高质量字段(缺失<30%): {len(good_quality_fields)}/{total_fields} 个\n"
        report += f"- 平均记录覆盖率: {(1 - merged_df.isnull().sum().sum() / (total_records * total_fields)) * 100:.1f}%\n"

        # 文件信息
        report += f"\n## 📁 文件信息\n\n"
        report += f"- **完整数据文件**: `a_share_financial_2000_2025_{timestamp}.csv`\n"
        report += f"- **最新版本**: `a_share_financial_latest.csv`\n"

        return report

    def save_final_dataset(self, merged_df: pd.DataFrame):
        """保存最终数据集"""
        print("\n💾 保存最终数据集")
        print("="*80)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 保存带时间戳的完整文件
        final_file = self.data_dir / f"a_share_financial_2000_2025_{timestamp}.csv"
        merged_df.to_csv(final_file, index=False, encoding='utf-8-sig')
        file_size_mb = final_file.stat().st_size / 1024 / 1024

        print(f"\n✅ 完整数据: {final_file}")
        print(f"   大小: {file_size_mb:.2f} MB")

        # 保存最新版本
        latest_file = self.data_dir / "a_share_financial_latest.csv"
        merged_df.to_csv(latest_file, index=False, encoding='utf-8-sig')

        print(f"✅ 最新版本: {latest_file}")

        # 生成汇总报告
        report = self.generate_summary_report(merged_df)
        report_file = self.data_dir / "FINANCIAL_DATA_2000_2025_SUMMARY.md"

        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"✅ 汇总报告: {report_file}")

        # 生成数据样本
        print("\n📊 数据样本:")
        print("-" * 40)

        sample_stocks = ['000001.SZ', '000002.SZ', '600000.SH']
        for stock in sample_stocks:
            if stock in merged_df['ts_code'].values:
                stock_data = merged_df[merged_df['ts_code'] == stock].sort_values('end_date')
                print(f"\n{stock} (最新5个季度):")
                display_cols = ['end_date', 'roe', 'or_yoy', 'pe', 'pb']
                available_cols = [c for c in display_cols if c in stock_data.columns]
                print(stock_data[available_cols].tail().to_string(index=False))

def main():
    """主函数"""
    print("\n" + "="*80)
    print("🔧 2000-2025财务数据验证和合并")
    print("="*80)

    # 数据目录
    data_dir = Path.home() / ".qlib/qlib_data/cn_data/financial_data"

    # 创建验证器
    validator = FinancialDataValidator(data_dir)

    # 1. 检查阶段文件
    phases = validator.check_phase_completeness()

    if not phases:
        print("\n❌ 未找到阶段文件，请先运行下载脚本")
        return

    # 2. 合并数据
    merged_df = validator.merge_all_phases(phases)

    if merged_df.empty:
        print("\n❌ 合并失败")
        return

    # 3. 验证数据质量
    quality_report = validator.validate_data_quality(merged_df)

    # 4. 保存最终数据集
    validator.save_final_dataset(merged_df)

    # 5. 完成
    print("\n" + "="*80)
    print("✅ 数据验证和合并完成!")
    print("="*80)

    print("\n📈 数据可用于:")
    print("   • 长期回测 (2000-2025 = 26年历史)")
    print("   • 财务因子分析")
    print("   • 价值投资策略")
    print("   • 行业对比研究")

    print("\n💡 下一步:")
    print("   1. 使用 Qlib 集成财务数据")
    print("   2. 计算自定义财务因子")
    print("   3. 构建回测策略")
    print("   4. 分析因子有效性")

if __name__ == "__main__":
    main()
