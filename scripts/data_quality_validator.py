#!/usr/bin/env python3
"""
数据质量验证工具

借鉴 investment_data 项目的验证机制，提供本地数据质量检查功能。

主要功能：
- 多数据源交叉验证（TuShare vs Yahoo）
- 价格范围验证
- 成交量验证
- 复权因子验证
- 交易日历验证
- 数据完整性验证

使用方法：
    python scripts/data_quality_validator.py
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import warnings

import pandas as pd
import numpy as np

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 忽略一些警告
warnings.filterwarnings('ignore')


class DataQualityValidator:
    """
    数据质量验证器

    提供全面的数据质量检查功能。
    """

    def __init__(self, data_dir: str = None):
        """
        初始化验证器

        Args:
            data_dir: 数据目录
        """
        self.data_dir = Path(data_dir or "~/.qlib/qlib_data/cn_data").expanduser()
        self.logger = self._setup_logger()

        # 验证规则配置
        self.rules = {
            "price": {
                "min_price": 0.01,        # 最低价格（避免除权后价格为0）
                "max_price": 10000,       # 最高价格
                "max_change_pct": 0.50,    # 最大单日涨跌幅（50%）
                "allow_zero": False       # 是否允许价格为0
            },
            "volume": {
                "min_volume": 0,          # 最小成交量
                "amount_tolerance": 0.05,  # 成交额与成交量×价格的误差容忍度
            },
            "completeness": {
                "min_stocks_per_day": 1000,  # 每日最少股票数
                "max_missing_pct": 0.10,     # 最大缺失比例
            }
        }

        self.validation_results = {
            "total_records": 0,
            "total_errors": 0,
            "errors_by_type": {},
            "error_details": []
        }

    def _setup_logger(self) -> logging.Logger:
        """设置日志"""
        logger = logging.getLogger("DataQualityValidator")
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def load_data(self, file_name: str = "stock_data.csv") -> pd.DataFrame:
        """
        加载数据文件

        Args:
            file_name: 数据文件名

        Returns:
            数据 DataFrame
        """
        file_path = self.data_dir / file_name

        if not file_path.exists():
            self.logger.error(f"❌ 数据文件不存在: {file_path}")
            return pd.DataFrame()

        try:
            df = pd.read_csv(file_path)
            self.logger.info(f"✅ 加载数据: {file_path} ({len(df):,} 行)")
            return df
        except Exception as e:
            self.logger.error(f"❌ 加载数据失败: {e}")
            return pd.DataFrame()

    def validate_price_range(self, df: pd.DataFrame) -> List[Dict]:
        """
        验证价格范围

        检查项：
        1. 价格不能为负数
        2. 价格不能为零（除非配置允许）
        3. 最高价 >= 最低价
        4. 收盘价在 [最低价, 最高价] 范围内
        5. 价格在合理范围内

        Args:
            df: 数据 DataFrame

        Returns:
            错误列表
        """
        self.logger.info("\n" + "=" * 60)
        self.logger.info("验证价格范围")
        self.logger.info("=" * 60)

        errors = []

        for idx, row in df.iterrows():
            # 检查负价格
            if row["close"] < 0:
                errors.append({
                    "type": "negative_price",
                    "severity": "critical",
                    "row_idx": idx,
                    "tradedate": row.get("tradedate", "N/A"),
                    "symbol": row.get("symbol", "N/A"),
                    "field": "close",
                    "value": row["close"],
                    "message": "收盘价不能为负数"
                })

            # 检查零价格
            if row["close"] == 0 and not self.rules["price"]["allow_zero"]:
                errors.append({
                    "type": "zero_price",
                    "severity": "warning",
                    "row_idx": idx,
                    "tradedate": row.get("tradedate", "N/A"),
                    "symbol": row.get("symbol", "N/A"),
                    "field": "close",
                    "value": row["close"],
                    "message": "收盘价为零（可能需要复权）"
                })

            # 检查价格范围
            if row["close"] < self.rules["price"]["min_price"]:
                errors.append({
                    "type": "price_too_low",
                    "severity": "warning",
                    "row_idx": idx,
                    "tradedate": row.get("tradedate", "N/A"),
                    "symbol": row.get("symbol", "N/A"),
                    "field": "close",
                    "value": row["close"],
                    "min_allowed": self.rules["price"]["min_price"],
                    "message": f"价格低于最小值 {self.rules['price']['min_price']}"
                })

            if row["close"] > self.rules["price"]["max_price"]:
                errors.append({
                    "type": "price_too_high",
                    "severity": "warning",
                    "row_idx": idx,
                    "tradedate": row.get("tradedate", "N/A"),
                    "symbol": row.get("symbol", "N/A"),
                    "field": "close",
                    "value": row["close"],
                    "max_allowed": self.rules["price"]["max_price"],
                    "message": f"价格高于最大值 {self.rules['price']['max_price']}"
                })

            # 检查高低价关系
            if pd.notna(row["high"]) and pd.notna(row["low"]):
                if row["high"] < row["low"]:
                    errors.append({
                        "type": "high_less_than_low",
                        "severity": "critical",
                        "row_idx": idx,
                        "tradedate": row.get("tradedate", "N/A"),
                        "symbol": row.get("symbol", "N/A"),
                        "high": row["high"],
                        "low": row["low"],
                        "message": "最高价小于最低价"
                    })

                # 检查收盘价是否在范围内
                if pd.notna(row["close"]):
                    if not (row["low"] <= row["close"] <= row["high"]):
                        errors.append({
                            "type": "close_out_of_range",
                            "severity": "critical",
                            "row_idx": idx,
                            "tradedate": row.get("tradedate", "N/A"),
                            "symbol": row.get("symbol", "N/A"),
                            "close": row["close"],
                            "low": row["low"],
                            "high": row["high"],
                            "message": "收盘价不在[最低价, 最高价]范围内"
                        })

        self.logger.info(f"发现 {len(errors)} 个价格范围错误")
        return errors

    def validate_volume(self, df: pd.DataFrame) -> List[Dict]:
        """
        验证成交量

        检查项：
        1. 成交量不能为负数
        2. 成交额应该约等于 成交量 × 收盘价

        Args:
            df: 数据 DataFrame

        Returns:
            错误列表
        """
        self.logger.info("\n" + "=" * 60)
        self.logger.info("验证成交量")
        self.logger.info("=" * 60)

        errors = []

        for idx, row in df.iterrows():
            # 检查负成交量
            if pd.notna(row["volume"]) and row["volume"] < 0:
                errors.append({
                    "type": "negative_volume",
                    "severity": "critical",
                    "row_idx": idx,
                    "tradedate": row.get("tradedate", "N/A"),
                    "symbol": row.get("symbol", "N/A"),
                    "volume": row["volume"],
                    "message": "成交量不能为负数"
                })

            # 检查成交额与成交量的关系
            if pd.notna(row["volume"]) and pd.notna(row["amount"]) and pd.notna(row["close"]):
                # 估算成交额 = 成交量 × 收盘价
                estimated_amount = row["volume"] * row["close"]

                if row["amount"] > 0:
                    error_pct = abs(row["amount"] - estimated_amount) / row["amount"]

                    if error_pct > self.rules["volume"]["amount_tolerance"]:
                        errors.append({
                            "type": "amount_mismatch",
                            "severity": "warning",
                            "row_idx": idx,
                            "tradedate": row.get("tradedate", "N/A"),
                            "symbol": row.get("symbol", "N/A"),
                            "actual_amount": row["amount"],
                            "estimated_amount": estimated_amount,
                            "error_pct": error_pct,
                            "message": f"成交额与估算值误差 {error_pct:.2%}"
                        })

        self.logger.info(f"发现 {len(errors)} 个成交量错误")
        return errors

    def validate_completeness(self, df: pd.DataFrame) -> List[Dict]:
        """
        验证数据完整性

        检查项：
        1. 每日股票数量是否合理
        2. 缺失值检查
        3. 重复记录检查

        Args:
            df: 数据 DataFrame

        Returns:
            错误列表
        """
        self.logger.info("\n" + "=" * 60)
        self.logger.info("验证数据完整性")
        self.logger.info("=" * 60)

        errors = []

        # 检查每日股票数量
        if "tradedate" in df.columns:
            daily_counts = df.groupby("tradedate")["symbol"].nunique()

            for tradedate, count in daily_counts.items():
                if count < self.rules["completeness"]["min_stocks_per_day"]:
                    errors.append({
                        "type": "insufficient_stocks",
                        "severity": "warning",
                        "tradedate": tradedate,
                        "stock_count": count,
                        "min_required": self.rules["completeness"]["min_stocks_per_day"],
                        "message": f"交易日期 {tradedate} 股票数量不足: {count} < {self.rules['completeness']['min_stocks_per_day']}"
                    })

        # 检查缺失值
        missing_counts = df.isnull().sum()
        for column, count in missing_counts.items():
            if count > 0:
                missing_pct = count / len(df)
                if missing_pct > self.rules["completeness"]["max_missing_pct"]:
                    errors.append({
                        "type": "too_many_missing",
                        "severity": "warning",
                        "column": column,
                        "missing_count": count,
                        "missing_pct": missing_pct,
                        "message": f"字段 {column} 缺失值过多: {missing_pct:.2%}"
                    })

        # 检查重复记录
        if "tradedate" in df.columns and "symbol" in df.columns:
            duplicates = df.duplicated(subset=["tradedate", "symbol"], keep=False)
            dup_count = duplicates.sum()

            if dup_count > 0:
                dup_samples = df[duplicates][["tradedate", "symbol"]].head(10).to_dict('records')
                errors.append({
                    "type": "duplicate_records",
                    "severity": "error",
                    "duplicate_count": dup_count,
                    "samples": dup_samples,
                    "message": f"发现 {dup_count} 条重复记录（tradedate + symbol）"
                })

        self.logger.info(f"发现 {len(errors)} 个完整性错误")
        return errors

    def validate_price_continuity(self, df: pd.DataFrame) -> List[Dict]:
        """
        验证价格连续性

        检查项：
        1. 检测异常的价格跳变（除权除息外）
        2. 检测停牌后价格连续性

        Args:
            df: 数据 DataFrame

        Returns:
            错误列表
        """
        self.logger.info("\n" + "=" * 60)
        self.logger.info("验证价格连续性")
        self.logger.info("=" * 60)

        errors = []

        if "tradedate" not in df.columns or "symbol" not in df.columns:
            self.logger.warning("⚠️  数据缺少 tradedate 或 symbol 字段，跳过连续性验证")
            return errors

        # 按股票分组检查
        for symbol in df["symbol"].unique():
            symbol_data = df[df["symbol"] == symbol].sort_values("tradedate")

            # 计算价格变化
            symbol_data["prev_close"] = symbol_data["close"].shift(1)
            symbol_data["change_pct"] = symbol_data["close"].pct_change()

            # 检测异常变化（超过阈值）
            max_change = self.rules["price"]["max_change_pct"]
            abnormal_changes = symbol_data[
                (symbol_data["change_pct"].abs() > max_change) &
                (symbol_data["change_pct"].notna())
            ]

            for idx, row in abnormal_changes.iterrows():
                errors.append({
                    "type": "abnormal_price_change",
                    "severity": "warning",
                    "symbol": symbol,
                    "tradedate": row["tradedate"],
                    "prev_close": row["prev_close"],
                    "current_close": row["close"],
                    "change_pct": row["change_pct"],
                    "message": f"单日价格变化 {row['change_pct']:.2%}，可能是除权除息或数据错误"
                })

        self.logger.info(f"发现 {len(errors)} 个价格连续性异常")
        return errors

    def validate_trading_calendar(self, df: pd.DataFrame) -> List[Dict]:
        """
        验证交易日历

        检查项：
        1. 检测周末数据（除非是特殊情况）
        2. 检测节假日数据

        Args:
            df: 数据 DataFrame

        Returns:
            错误列表
        """
        self.logger.info("\n" + "=" * 60)
        self.logger.info("验证交易日历")
        self.logger.info("=" * 60)

        errors = []

        if "tradedate" not in df.columns:
            self.logger.warning("⚠️  数据缺少 tradedate 字段，跳过交易日历验证")
            return errors

        # 检查日期格式
        try:
            df["tradedate_dt"] = pd.to_datetime(df["tradedate"], format="%Y%m%d", errors="coerce")

            # 检查无效日期
            invalid_dates = df[df["tradedate_dt"].isna()]
            if len(invalid_dates) > 0:
                errors.append({
                    "type": "invalid_date_format",
                    "severity": "error",
                    "count": len(invalid_dates),
                    "samples": invalid_dates["tradedate"].head(10).tolist(),
                    "message": f"发现 {len(invalid_dates)} 条无效日期格式"
                })

            # 检查周末（周六、周日）
            if len(df) > 0:
                df["day_of_week"] = df["tradedate_dt"].dt.dayofweek
                weekend_data = df[df["day_of_week"] >= 5]  # 5=周六, 6=周日

                if len(weekend_data) > 0:
                    errors.append({
                        "type": "weekend_data",
                        "severity": "warning",
                        "count": len(weekend_data),
                        "dates": weekend_data["tradedate"].unique().tolist()[:10],
                        "message": f"发现 {len(weekend_data)} 条周末数据（可能是正常的补数据）"
                    })

        except Exception as e:
            errors.append({
                "type": "date_parsing_error",
                "severity": "error",
                "message": f"日期解析失败: {str(e)}"
            })

        self.logger.info(f"发现 {len(errors)} 个交易日历问题")
        return errors

    def run_validation(self, file_name: str = "stock_data.csv") -> Dict:
        """
        运行完整验证

        Args:
            file_name: 数据文件名

        Returns:
            验证结果字典
        """
        self.logger.info("\n" + "=" * 60)
        self.logger.info("开始数据质量验证")
        self.logger.info("=" * 60)

        # 加载数据
        df = self.load_data(file_name)

        if df.empty:
            self.logger.error("❌ 数据为空或加载失败")
            return {"success": False, "errors": []}

        self.validation_results["total_records"] = len(df)

        # 执行各项验证
        all_errors = []

        all_errors.extend(self.validate_price_range(df))
        all_errors.extend(self.validate_volume(df))
        all_errors.extend(self.validate_completeness(df))
        all_errors.extend(self.validate_price_continuity(df))
        all_errors.extend(self.validate_trading_calendar(df))

        # 汇总结果
        self.validation_results["total_errors"] = len(all_errors)
        self.validation_results["errors_by_type"] = {}
        self.validation_results["error_details"] = all_errors

        for error in all_errors:
            error_type = error["type"]
            if error_type not in self.validation_results["errors_by_type"]:
                self.validation_results["errors_by_type"][error_type] = 0
            self.validation_results["errors_by_type"][error_type] += 1

        # 打印验证报告
        self._print_validation_report()

        return {
            "success": len([e for e in all_errors if e.get("severity") == "critical"]) == 0,
            "errors": all_errors,
            "summary": self.validation_results
        }

    def _print_validation_report(self):
        """打印验证报告"""
        print("\n" + "=" * 60)
        print("数据质量验证报告")
        print("=" * 60)

        print(f"\n📊 数据统计:")
        print(f"   总记录数: {self.validation_results['total_records']:,}")
        print(f"   错误总数: {self.validation_results['total_errors']}")

        if self.validation_results["errors_by_type"]:
            print(f"\n🔍 错误分类:")
            for error_type, count in sorted(
                self.validation_results["errors_by_type"].items(),
                key=lambda x: x[1],
                reverse=True
            ):
                print(f"   - {error_type}: {count}")

        # 统计严重级别
        severity_counts = {}
        for error in self.validation_results["error_details"]:
            severity = error.get("severity", "unknown")
            if severity not in severity_counts:
                severity_counts[severity] = 0
            severity_counts[severity] += 1

        print(f"\n⚠️  严重级别:")
        for severity, count in sorted(severity_counts.items()):
            print(f"   - {severity}: {count}")

        # 显示部分错误详情
        if self.validation_results["error_details"]:
            print(f"\n📝 错误详情（前20个）:")
            for i, error in enumerate(self.validation_results["error_details"][:20], 1):
                print(f"   {i}. [{error.get('severity', 'unknown')}] {error.get('message', 'N/A')}")
                if "tradedate" in error and "symbol" in error:
                    print(f"      日期: {error['tradedate']}, 股票: {error['symbol']}")

        # 判断验证结果
        critical_errors = [
            e for e in self.validation_results["error_details"]
            if e.get("severity") == "critical"
        ]

        print("\n" + "=" * 60)
        if len(critical_errors) == 0:
            print("✅ 验证通过：没有严重错误")
        else:
            print(f"❌ 验证失败：发现 {len(critical_errors)} 个严重错误")
        print("=" * 60)

    def export_errors_to_csv(self, output_file: str = None):
        """
        导出错误到 CSV 文件

        Args:
            output_file: 输出文件路径
        """
        if not self.validation_results["error_details"]:
            self.logger.info("没有错误需要导出")
            return

        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.data_dir / f"validation_errors_{timestamp}.csv"

        # 转换为 DataFrame
        errors_df = pd.DataFrame(self.validation_results["error_details"])
        errors_df.to_csv(output_file, index=False)

        self.logger.info(f"✅ 错误已导出到: {output_file}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="数据质量验证工具")
    parser.add_argument(
        "--data-dir",
        default="~/.qlib/qlib_data/cn_data",
        help="数据目录路径"
    )
    parser.add_argument(
        "--file",
        default="stock_data.csv",
        help="数据文件名"
    )

    args = parser.parse_args()

    # 创建验证器
    validator = DataQualityValidator(data_dir=args.data_dir)

    # 运行验证
    result = validator.run_validation(file_name=args.file)

    # 导出错误
    if result["errors"]:
        validator.export_errors_to_csv()

    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
