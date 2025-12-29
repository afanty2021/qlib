#!/usr/bin/env python3
"""
数据质量抽样比对工具

与 investment_data 项目的 Dolt 数据库进行抽样对比，评估本地数据质量。

主要功能：
- 抽样选择股票和时间段
- 从 Dolt 数据库获取参考数据
- 对比本地数据和参考数据
- 生成详细的质量报告
- 可视化比对结果

依赖项：
    pip install dolt pymysql

使用方法：
    python scripts/data_sampling_comparison.py
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import warnings
import subprocess
import json

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

warnings.filterwarnings('ignore')


class DoltDataFetcher:
    """
    Dolt 数据库数据获取器

    从 Dolt 数据库获取参考数据用于比对。
    """

    def __init__(self, dolt_db_path: str = None):
        """
        初始化 Dolt 数据获取器

        Args:
            dolt_db_path: 本地 Dolt 数据库路径
        """
        self.dolt_db_path = dolt_db_path
        self.logger = self._setup_logger()

        # 检查 Dolt 是否安装
        self.dolt_available = self._check_dolt()

    def _setup_logger(self) -> logging.Logger:
        """设置日志"""
        logger = logging.getLogger("DoltDataFetcher")
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def _check_dolt(self) -> bool:
        """检查 Dolt 是否安装"""
        try:
            result = subprocess.run(
                ["dolt", "version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                self.logger.info(f"✅ Dolt 已安装: {result.stdout.strip()}")
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        self.logger.warning("⚠️  Dolt 未安装，将使用模拟数据")
        return False

    def clone_dolt_db(self, db_name: str = "chenditc/investment_data", target_dir: str = None):
        """
        克隆 Dolt 数据库

        Args:
            db_name: Dolt 数据库名称
            target_dir: 目标目录

        Returns:
            是否成功
        """
        if not self.dolt_available:
            self.logger.error("❌ Dolt 未安装，无法克隆数据库")
            self.logger.info("💡 安装 Dolt: curl - https://www.dolthub.com/install.sh")
            return False

        if target_dir is None:
            target_dir = Path.cwd() / "dolt_data"

        try:
            target_dir = Path(target_dir)
            target_dir.mkdir(parents=True, exist_ok=True)

            self.logger.info(f"正在克隆 Dolt 数据库: {db_name}")

            result = subprocess.run(
                ["dolt", "clone", db_name, str(target_dir)],
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )

            if result.returncode == 0:
                self.dolt_db_path = str(target_dir / db_name)
                self.logger.info(f"✅ 数据库克隆成功: {self.dolt_db_path}")
                return True
            else:
                self.logger.error(f"❌ 克隆失败: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            self.logger.error("❌ 克隆超时（数据库可能很大）")
            return False
        except Exception as e:
            self.logger.error(f"❌ 克隆失败: {e}")
            return False

    def query_dolt_db(self, sql: str) -> pd.DataFrame:
        """
        查询 Dolt 数据库

        Args:
            sql: SQL 查询语句

        Returns:
            查询结果 DataFrame
        """
        if not self.dolt_db_path:
            self.logger.error("❌ Dolt 数据库路径未设置")
            return pd.DataFrame()

        try:
            result = subprocess.run(
                ["dolt", "sql", "-q", sql],
                cwd=self.dolt_db_path,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                # 解析输出（假设是 CSV 格式）
                from io import StringIO
                df = pd.read_csv(StringIO(result.stdout))
                return df
            else:
                self.logger.error(f"❌ 查询失败: {result.stderr}")
                return pd.DataFrame()

        except subprocess.TimeoutExpired:
            self.logger.error("❌ 查询超时")
            return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"❌ 查询失败: {e}")
            return pd.DataFrame()

    def get_sample_data_from_dolt(
        self,
        symbols: List[str] = None,
        start_date: str = None,
        end_date: str = None,
        limit: int = 1000
    ) -> pd.DataFrame:
        """
        从 Dolt 数据库获取抽样数据

        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            limit: 限制记录数

        Returns:
            抽样数据 DataFrame
        """
        self.logger.info("从 Dolt 数据库获取抽样数据...")

        # 构建查询
        where_clauses = []
        if symbols:
            symbol_list = "', '".join(symbols)
            where_clauses.append(f"symbol IN ('{symbol_list}')")

        if start_date:
            where_clauses.append(f"tradedate >= '{start_date}'")

        if end_date:
            where_clauses.append(f"tradedate <= '{end_date}'")

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        sql = f"""
        SELECT tradedate, symbol, open, high, low, close, volume, amount
        FROM final_a_stock_eod_price
        {where_sql}
        ORDER BY tradedate, symbol
        LIMIT {limit}
        """

        self.logger.info(f"SQL: {sql}")

        df = self.query_dolt_db(sql)

        if not df.empty:
            self.logger.info(f"✅ 获取到 {len(df)} 条 Dolt 数据")
        else:
            self.logger.warning("⚠️  未获取到 Dolt 数据，将使用模拟数据")

        return df


class DataComparisonAnalyzer:
    """
    数据对比分析器

    对比本地数据和参考数据，评估数据质量。
    """

    def __init__(self, local_data_dir: str = None):
        """
        初始化对比分析器

        Args:
            local_data_dir: 本地数据目录
        """
        self.local_data_dir = Path(local_data_dir or "~/.qlib/qlib_data/cn_data").expanduser()
        self.logger = self._setup_logger()

        self.comparison_results = {
            "summary": {},
            "price_comparison": {},
            "volume_comparison": {},
            "completeness_comparison": {},
            "sample_details": []
        }

    def _setup_logger(self) -> logging.Logger:
        """设置日志"""
        logger = logging.getLogger("DataComparisonAnalyzer")
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def load_local_data(
        self,
        file_name: str = "stock_data.csv",
        symbols: List[str] = None,
        start_date: str = None,
        end_date: str = None
    ) -> pd.DataFrame:
        """
        加载本地数据

        Args:
            file_name: 数据文件名
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            本地数据 DataFrame
        """
        file_path = self.local_data_dir / file_name

        if not file_path.exists():
            self.logger.error(f"❌ 本地数据文件不存在: {file_path}")
            return pd.DataFrame()

        try:
            df = pd.read_csv(file_path)

            # 确保 tradedate 是字符串类型
            if "tradedate" in df.columns:
                df["tradedate"] = df["tradedate"].astype(str)

            # 过滤数据
            if symbols:
                df = df[df["symbol"].isin(symbols)]

            if start_date:
                df = df[df["tradedate"] >= start_date]

            if end_date:
                df = df[df["tradedate"] <= end_date]

            self.logger.info(f"✅ 加载本地数据: {len(df)} 条记录")
            return df

        except Exception as e:
            self.logger.error(f"❌ 加载本地数据失败: {e}")
            return pd.DataFrame()

    def select_sample_symbols(
        self,
        n_symbols: int = 20,
        method: str = "random",
        file_name: str = "stock_data.csv"
    ) -> List[str]:
        """
        选择抽样的股票

        Args:
            n_symbols: 抽样数量
            method: 抽样方法 ("random", "market_cap", "index")
            file_name: 数据文件名

        Returns:
            股票代码列表
        """
        self.logger.info(f"选择抽样股票: 方法={method}, 数量={n_symbols}")

        # 从本地数据中获取实际可用的股票
        file_path = self.local_data_dir / file_name

        if file_path.exists():
            try:
                df = pd.read_csv(file_path)
                available_symbols = df["symbol"].unique().tolist()

                if len(available_symbols) == 0:
                    self.logger.warning("⚠️  本地数据没有股票，使用默认列表")
                    available_symbols = [
                        "000001.SZ", "000002.SZ", "000063.SZ", "000066.SZ", "000333.SZ",
                        "000338.SZ", "000401.SZ", "000402.SZ", "000651.SZ", "000652.SZ"
                    ]
                else:
                    self.logger.info(f"📊 本地数据共有 {len(available_symbols)} 只股票")
            except Exception as e:
                self.logger.warning(f"⚠️  读取本地数据失败: {e}，使用默认列表")
                available_symbols = [
                    "000001.SZ", "000002.SZ", "000063.SZ", "000066.SZ", "000333.SZ",
                    "000338.SZ", "000401.SZ", "000402.SZ", "000651.SZ", "000652.SZ"
                ]
        else:
            self.logger.warning(f"⚠️  本地数据文件不存在: {file_path}，使用默认列表")
            available_symbols = [
                "000001.SZ", "000002.SZ", "000063.SZ", "000066.SZ", "000333.SZ",
                "000338.SZ", "000401.SZ", "000402.SZ", "000651.SZ", "000652.SZ"
            ]

        # 从可用股票中选择
        n_select = min(n_symbols, len(available_symbols))

        if method == "random":
            selected = np.random.choice(available_symbols, n_select, replace=False)
        elif method == "index":
            # 优先选择指数成分股
            index_stocks = [s for s in available_symbols if s.startswith(("60", "00"))]
            selected = index_stocks[:n_select] if len(index_stocks) >= n_select else available_symbols[:n_select]
        else:
            selected = available_symbols[:n_select]

        self.logger.info(f"✅ 选择 {len(selected)} 只股票: {', '.join(selected[:5])}...")

        return list(selected)

    def compare_price_data(
        self,
        local_df: pd.DataFrame,
        reference_df: pd.DataFrame
    ) -> Dict:
        """
        对比价格数据

        Args:
            local_df: 本地数据
            reference_df: 参考数据

        Returns:
            对比结果
        """
        self.logger.info("\n" + "=" * 60)
        self.logger.info("对比价格数据")
        self.logger.info("=" * 60)

        # 合并数据
        merged = pd.merge(
            local_df,
            reference_df,
            on=["tradedate", "symbol"],
            how="inner",
            suffixes=("_local", "_ref")
        )

        if merged.empty:
            self.logger.warning("⚠️  没有共同的数据点可以对比")
            return {"match_rate": 0, "total_compared": 0}

        # 对比字段
        price_fields = ["open", "high", "low", "close"]
        comparison_results = {}

        for field in price_fields:
            local_col = f"{field}_local"
            ref_col = f"{field}_ref"

            if local_col in merged.columns and ref_col in merged.columns:
                # 计算偏差
                merged[f"{field}_diff"] = merged[local_col] - merged[ref_col]
                merged[f"{field}_diff_pct"] = (merged[local_col] - merged[ref_col]) / merged[ref_col]

                # 统计
                total = len(merged)
                exact_match = (merged[f"{field}_diff"] == 0).sum()
                small_diff = (merged[f"{field}_diff"].abs() < 0.01).sum()  # 差异小于0.01
                large_diff = (merged[f"{field}_diff_pct"].abs() > 0.05).sum()  # 差异超过5%

                comparison_results[field] = {
                    "total_compared": total,
                    "exact_match": exact_match,
                    "exact_match_rate": exact_match / total if total > 0 else 0,
                    "small_diff": small_diff,
                    "small_diff_rate": small_diff / total if total > 0 else 0,
                    "large_diff": large_diff,
                    "large_diff_rate": large_diff / total if total > 0 else 0,
                    "mean_diff": merged[f"{field}_diff"].mean(),
                    "std_diff": merged[f"{field}_diff"].std(),
                    "mean_abs_diff_pct": merged[f"{field}_diff_pct"].abs().mean()
                }

                self.logger.info(f"\n{field.upper()} 字段对比:")
                self.logger.info(f"  对比记录数: {total}")
                self.logger.info(f"  完全一致: {exact_match} ({exact_match/total:.2%})")
                self.logger.info(f"  小差异(<0.01): {small_diff} ({small_diff/total:.2%})")
                self.logger.info(f"  大差异(>5%): {large_diff} ({large_diff/total:.2%})")
                self.logger.info(f"  平均偏差: {comparison_results[field]['mean_diff']:.6f}")
                self.logger.info(f"  标准差: {comparison_results[field]['std_diff']:.6f}")

        self.comparison_results["price_comparison"] = comparison_results

        # 保存详细比对数据
        self.comparison_results["sample_details"] = merged

        return comparison_results

    def compare_volume_data(
        self,
        local_df: pd.DataFrame,
        reference_df: pd.DataFrame
    ) -> Dict:
        """
        对比成交量数据

        Args:
            local_df: 本地数据
            reference_df: 参考数据

        Returns:
            对比结果
        """
        self.logger.info("\n" + "=" * 60)
        self.logger.info("对比成交量数据")
        self.logger.info("=" * 60)

        # 合并数据
        merged = pd.merge(
            local_df,
            reference_df,
            on=["tradedate", "symbol"],
            how="inner",
            suffixes=("_local", "_ref")
        )

        if merged.empty:
            self.logger.warning("⚠️  没有共同的数据点可以对比")
            return {}

        # 对比成交量
        if "volume_local" in merged.columns and "volume_ref" in merged.columns:
            merged["volume_diff"] = merged["volume_local"] - merged["volume_ref"]
            merged["volume_diff_pct"] = (
                (merged["volume_local"] - merged["volume_ref"]) /
                merged["volume_ref"].replace(0, np.nan)
            )

            # 统计
            total = len(merged)
            exact_match = (merged["volume_diff"] == 0).sum()
            small_diff = (merged["volume_diff"].abs() < 1000).sum()  # 差异小于1000手

            volume_stats = {
                "total_compared": total,
                "exact_match": exact_match,
                "exact_match_rate": exact_match / total if total > 0 else 0,
                "small_diff": small_diff,
                "small_diff_rate": small_diff / total if total > 0 else 0,
                "mean_diff": merged["volume_diff"].mean(),
                "std_diff": merged["volume_diff"].std(),
                "correlation": merged["volume_local"].corr(merged["volume_ref"])
            }

            self.logger.info(f"\n成交量对比:")
            self.logger.info(f"  对比记录数: {total}")
            self.logger.info(f"  完全一致: {exact_match} ({exact_match/total:.2%})")
            self.logger.info(f"  相关系数: {volume_stats['correlation']:.4f}")

            self.comparison_results["volume_comparison"] = volume_stats

        return self.comparison_results.get("volume_comparison", {})

    def compare_completeness(
        self,
        local_df: pd.DataFrame,
        reference_df: pd.DataFrame
    ) -> Dict:
        """
        对比数据完整性

        Args:
            local_df: 本地数据
            reference_df: 参考数据

        Returns:
            对比结果
        """
        self.logger.info("\n" + "=" * 60)
        self.logger.info("对比数据完整性")
        self.logger.info("=" * 60)

        # 统计本地数据
        local_dates = set(local_df["tradedate"].unique()) if "tradedate" in local_df.columns else set()
        local_symbols = set(local_df["symbol"].unique()) if "symbol" in local_df.columns else set()

        # 统计参考数据
        ref_dates = set(reference_df["tradedate"].unique()) if "tradedate" in reference_df.columns else set()
        ref_symbols = set(reference_df["symbol"].unique()) if "symbol" in reference_df.columns else set()

        # 对比
        missing_dates = ref_dates - local_dates
        missing_symbols = ref_symbols - local_symbols
        extra_dates = local_dates - ref_dates
        extra_symbols = local_symbols - ref_symbols

        completeness_stats = {
            "local_date_count": len(local_dates),
            "ref_date_count": len(ref_dates),
            "local_symbol_count": len(local_symbols),
            "ref_symbol_count": len(ref_symbols),
            "missing_dates": len(missing_dates),
            "missing_symbols": len(missing_symbols),
            "extra_dates": len(extra_dates),
            "extra_symbols": len(extra_symbols),
            "date_coverage": len(local_dates & ref_dates) / len(ref_dates) if ref_dates else 0,
            "symbol_coverage": len(local_symbols & ref_symbols) / len(ref_symbols) if ref_symbols else 0
        }

        self.logger.info(f"\n数据完整性对比:")
        self.logger.info(f"  本地交易日数: {completeness_stats['local_date_count']}")
        self.logger.info(f"  参考交易日数: {completeness_stats['ref_date_count']}")
        self.logger.info(f"  日期覆盖率: {completeness_stats['date_coverage']:.2%}")
        self.logger.info(f"  本地股票数: {completeness_stats['local_symbol_count']}")
        self.logger.info(f"  参考股票数: {completeness_stats['ref_symbol_count']}")
        self.logger.info(f"  股票覆盖率: {completeness_stats['symbol_coverage']:.2%}")

        self.comparison_results["completeness_comparison"] = completeness_stats

        return completeness_stats

    def generate_comparison_report(self) -> str:
        """
        生成比对报告

        Returns:
            报告字符串
        """
        report = "\n" + "=" * 60
        report += "\n数据质量抽样比对报告"
        report += "\n" + "=" * 60

        # 概要
        if self.comparison_results["summary"]:
            report += "\n\n## 概要\n"
            for key, value in self.comparison_results["summary"].items():
                report += f"- {key}: {value}\n"

        # 价格对比
        if self.comparison_results.get("price_comparison"):
            report += "\n\n## 价格对比详情\n"
            price_comp = self.comparison_results["price_comparison"]

            for field, stats in price_comp.items():
                report += f"\n### {field.upper()}\n"
                report += f"- 对比记录数: {stats['total_compared']:,}\n"
                report += f"- 完全一致率: {stats['exact_match_rate']:.2%}\n"
                report += f"- 小差异率: {stats['small_diff_rate']:.2%}\n"
                report += f"- 大差异率: {stats['large_diff_rate']:.2%}\n"
                report += f"- 平均偏差: {stats['mean_diff']:.6f}\n"

        # 成交量对比
        if self.comparison_results.get("volume_comparison"):
            report += "\n\n## 成交量对比详情\n"
            vol_comp = self.comparison_results["volume_comparison"]

            report += f"- 对比记录数: {vol_comp['total_compared']:,}\n"
            report += f"- 完全一致率: {vol_comp['exact_match_rate']:.2%}\n"
            report += f"- 相关系数: {vol_comp['correlation']:.4f}\n"

        # 完整性对比
        if self.comparison_results.get("completeness_comparison"):
            report += "\n\n## 数据完整性对比\n"
            comp_comp = self.comparison_results["completeness_comparison"]

            report += f"- 日期覆盖率: {comp_comp['date_coverage']:.2%}\n"
            report += f"- 股票覆盖率: {comp_comp['symbol_coverage']:.2%}\n"
            report += f"- 缺失交易日: {comp_comp['missing_dates']}\n"
            report += f"- 缺失股票: {comp_comp['missing_symbols']}\n"

        # 总体评价
        report += "\n\n## 总体评价\n"
        overall_score = self._calculate_overall_score()
        report += f"数据质量评分: {overall_score:.1f}/100\n"

        if overall_score >= 90:
            report += "评价: ⭐⭐⭐⭐⭐ 优秀 - 数据质量很高\n"
        elif overall_score >= 75:
            report += "评价: ⭐⭐⭐⭐ 良好 - 数据质量良好\n"
        elif overall_score >= 60:
            report += "评价: ⭐⭐⭐ 中等 - 数据质量可接受\n"
        else:
            report += "评价: ⭐⭐ 较差 - 数据需要改进\n"

        return report

    def _calculate_overall_score(self) -> float:
        """
        计算总体质量评分

        Returns:
            评分 (0-100)
        """
        score = 100.0

        # 价格一致性 (权重 40%)
        if self.comparison_results.get("price_comparison"):
            price_comp = self.comparison_results["price_comparison"]
            if price_comp:
                avg_exact_match_rate = np.mean([
                    stats["exact_match_rate"]
                    for stats in price_comp.values()
                ])
                score -= (1 - avg_exact_match_rate) * 40

        # 成交量一致性 (权重 20%)
        if self.comparison_results.get("volume_comparison"):
            vol_comp = self.comparison_results["volume_comparison"]
            if vol_comp:
                score -= (1 - vol_comp["exact_match_rate"]) * 20

        # 完整性 (权重 40%)
        if self.comparison_results.get("completeness_comparison"):
            comp_comp = self.comparison_results["completeness_comparison"]
            if comp_comp:
                avg_coverage = (comp_comp["date_coverage"] + comp_comp["symbol_coverage"]) / 2
                score -= (1 - avg_coverage) * 40

        return max(0, score)

    def visualize_comparison(self, output_dir: str = None):
        """
        可视化比对结果

        Args:
            output_dir: 输出目录
        """
        if self.comparison_results.get("sample_details") is None:
            self.logger.warning("⚠️  没有比对数据可以可视化")
            return

        merged = self.comparison_results["sample_details"]

        # 创建输出目录
        if output_dir is None:
            output_dir = self.local_data_dir / "comparison_charts"
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 创建图表
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))

        # 1. 收盘价对比散点图
        if "close_local" in merged.columns and "close_ref" in merged.columns:
            ax = axes[0, 0]
            ax.scatter(merged["close_ref"], merged["close_local"], alpha=0.5, s=1)
            ax.plot([merged["close_ref"].min(), merged["close_ref"].max()],
                    [merged["close_ref"].min(), merged["close_ref"].max()],
                    'r--', label='完美匹配线')
            ax.set_xlabel("参考收盘价")
            ax.set_ylabel("本地收盘价")
            ax.set_title("收盘价对比")
            ax.legend()
            ax.grid(True, alpha=0.3)

        # 2. 收盘价差异分布
        if "close_diff_pct" in merged.columns:
            ax = axes[0, 1]
            ax.hist(merged["close_diff_pct"].dropna(), bins=50, edgecolor='black')
            ax.set_xlabel("价格差异百分比")
            ax.set_ylabel("频数")
            ax.set_title("价格差异分布")
            ax.axvline(0, color='r', linestyle='--', label='零差异线')
            ax.axvline(0.05, color='orange', linestyle='--', label='±5%阈值')
            ax.axvline(-0.05, color='orange', linestyle='--')
            ax.legend()
            ax.grid(True, alpha=0.3)

        # 3. 成交量对比散点图
        if "volume_local" in merged.columns and "volume_ref" in merged.columns:
            ax = axes[1, 0]
            ax.scatter(merged["volume_ref"], merged["volume_local"], alpha=0.5, s=1)
            ax.plot([merged["volume_ref"].min(), merged["volume_ref"].max()],
                    [merged["volume_ref"].min(), merged["volume_ref"].max()],
                    'r--', label='完美匹配线')
            ax.set_xlabel("参考成交量")
            ax.set_ylabel("本地成交量")
            ax.set_title("成交量对比")
            ax.legend()
            ax.grid(True, alpha=0.3)

        # 4. 价格差异时间序列
        if "tradedate" in merged.columns and "close_diff_pct" in merged.columns:
            ax = axes[1, 1]
            plot_data = merged.groupby("tradedate")["close_diff_pct"].mean()
            ax.plot(range(len(plot_data)), plot_data.values)
            ax.axhline(0, color='r', linestyle='--', label='零差异线')
            ax.axhline(0.05, color='orange', linestyle='--', label='±5%阈值')
            ax.axhline(-0.05, color='orange', linestyle='--')
            ax.set_xlabel("交易日")
            ax.set_ylabel("平均价格差异(%)")
            ax.set_title("价格差异时间趋势")
            ax.legend()
            ax.grid(True, alpha=0.3)

        plt.tight_layout()

        # 保存图表
        output_file = output_dir / f"comparison_{timestamp}.png"
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close()

        self.logger.info(f"✅ 对比图表已保存: {output_file}")

    def run_comparison(
        self,
        reference_fetcher: DoltDataFetcher = None,
        n_samples: int = 20,
        start_date: str = None,
        end_date: str = None
    ) -> Dict:
        """
        运行完整比对

        Args:
            reference_fetcher: 参考数据获取器
            n_samples: 抽样数量
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            比对结果
        """
        self.logger.info("\n" + "=" * 60)
        self.logger.info("开始数据质量抽样比对")
        self.logger.info("=" * 60)

        # 设置日期范围（默认最近3个月）
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")

        if start_date is None:
            start_date = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d")

        self.logger.info(f"比对时间范围: {start_date} -> {end_date}")

        # 选择抽样股票
        sample_symbols = self.select_sample_symbols(n_samples, file_name="stock_data.csv")

        # 加载本地数据
        local_df = self.load_local_data(
            symbols=sample_symbols,
            start_date=start_date,
            end_date=end_date
        )

        if local_df.empty:
            self.logger.error("❌ 本地数据为空，无法比对")
            return {"success": False}

        # 获取参考数据
        reference_df = None

        if reference_fetcher:
            reference_df = reference_fetcher.get_sample_data_from_dolt(
                symbols=sample_symbols,
                start_date=start_date,
                end_date=end_date
            )
        else:
            # 使用模拟数据
            self.logger.warning("⚠️  未提供参考数据获取器，使用本地数据的一半作为参考")
            reference_df = local_df.sample(frac=0.5).copy()
            # 添加一些随机噪声模拟参考数据
            noise = np.random.normal(0, 0.01, len(reference_df))
            reference_df["close"] *= (1 + noise)

        if reference_df.empty:
            self.logger.error("❌ 参考数据为空，无法比对")
            return {"success": False}

        # 执行比对
        self.compare_price_data(local_df, reference_df)
        self.compare_volume_data(local_df, reference_df)
        self.compare_completeness(local_df, reference_df)

        # 生成报告
        report = self.generate_comparison_report()
        print(report)

        # 可视化
        try:
            self.visualize_comparison()
        except Exception as e:
            self.logger.warning(f"⚠️  可视化失败: {e}")

        # 保存比对结果
        output_file = self.local_data_dir / f"comparison_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            # 转换数据为可序列化格式
            serializable_results = self.comparison_results.copy()
            if "sample_details" in serializable_results:
                serializable_results["sample_details"] = serializable_results["sample_details"].to_dict('records')
            json.dump(serializable_results, f, indent=2, default=str)

        self.logger.info(f"✅ 比对结果已保存: {output_file}")

        return {
            "success": True,
            "results": self.comparison_results,
            "report": report
        }


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="数据质量抽样比对工具")
    parser.add_argument("--local-data-dir", default="~/.qlib/qlib_data/cn_data", help="本地数据目录")
    parser.add_argument("--dolt-db-path", help="Dolt 数据库路径")
    parser.add_argument("--n-samples", type=int, default=20, help="抽样股票数量")
    parser.add_argument("--start-date", help="开始日期 (YYYYMMDD)")
    parser.add_argument("--end-date", help="结束日期 (YYYYMMDD)")

    args = parser.parse_args()

    print("\n🔍 数据质量抽样比对工具")
    print("=" * 60)

    # 检查本地数据
    local_file = Path(args.local_data_dir) / "stock_data.csv"
    if not local_file.exists():
        print(f"❌ 本地数据文件不存在: {local_file}")
        print("\n💡 提示:")
        print("   1. 先运行增量更新脚本获取数据:")
        print("      python scripts/tushare_incremental_update.py")
        print("   2. 或使用演示数据:")
        print("      python scripts/data_merge_demo.py")
        return 1

    # 创建 Dolt 数据获取器（可选）
    dolt_fetcher = None
    if args.dolt_db_path:
        dolt_fetcher = DoltDataFetcher(args.dolt_db_path)
    else:
        print("⚠️  未指定 Dolt 数据库路径")
        print("💡 如果有 Dolt 数据库，可以指定:")
        print("   --dolt-db-path /path/to/dolt/chenditc/investment_data")
        print("\n💡 或者克隆数据库（需要几分钟）:")
        print("   dolt clone chenditc/investment_data")
        print("   然后使用: --dolt-db-path ./investment_data")

    # 创建比对分析器
    analyzer = DataComparisonAnalyzer(local_data_dir=args.local_data_dir)

    # 运行比对
    result = analyzer.run_comparison(
        reference_fetcher=dolt_fetcher,
        n_samples=args.n_samples,
        start_date=args.start_date,
        end_date=args.end_date
    )

    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
