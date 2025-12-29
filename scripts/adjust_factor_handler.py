#!/usr/bin/env python3
"""
股票复权处理工具

处理分红、送股、增发等除权除息事件，确保价格数据的可比性。

主要功能：
- 获取复权因子数据
- 计算前复权、后复权价格
- 复权数据的存储和读取
- 复权数据的验证和可视化

复权类型说明：
1. 前复权 (qfq): 当前价格不变，调整历史价格
   - 适用场景：技术分析、趋势判断
   - 公式：adj_price = raw_price * adj_factor

2. 后复权 (hfq): 最早价格不变，调整当前价格
   - 适用场景：长期投资分析
   - 公式：adj_price = raw_price * (adj_factor / first_adj_factor)

3. 不复权 (none): 保持原始价格
   - 适用场景：当日交易分析

使用方法：
    python scripts/adjust_factor_handler.py
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Literal

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import yaml

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from qlib.contrib.data.tushare.api_client import TuShareAPIClient
from qlib.contrib.data.tushare.config import TuShareConfig


class AdjustFactorHandler:
    """
    复权因子处理器

    获取、计算和存储复权数据。
    """

    def __init__(self, config: Dict = None):
        """
        初始化复权因子处理器

        Args:
            config: 配置字典
        """
        self.config = config or {}
        self.data_dir = Path(self.config.get("data_dir", "~/.qlib/qlib_data/cn_data")).expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 初始化 TuShare 客户端
        token = os.getenv("TUSHARE_TOKEN")
        if not token:
            raise ValueError("请设置 TUSHARE_TOKEN 环境变量")

        tushare_config = TuShareConfig(token=token)
        self.client = TuShareAPIClient(tushare_config)

        # 设置日志
        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """设置日志"""
        logger = logging.getLogger("AdjustFactorHandler")
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def get_adj_factor(
        self,
        ts_code: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        获取复权因子数据

        Args:
            ts_code: 股票代码
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)

        Returns:
            复权因子 DataFrame
        """
        self.logger.info(f"获取 {ts_code} 的复权因子: {start_date} -> {end_date}")

        try:
            # TuShare API 获取复权因子
            data = self.client._make_request("adj_factor", {
                "ts_code": ts_code,
                "start_date": start_date,
                "end_date": end_date
            })

            if data and "items" in data and len(data["items"]) > 0:
                df = pd.DataFrame(data["items"], columns=data["fields"])

                # 字段映射
                df = df.rename(columns={
                    "trade_date": "tradedate",
                    "ts_code": "symbol",
                    "adj_factor": "adj_factor"
                })

                self.logger.info(f"✅ 获取到 {len(df)} 条复权因子数据")
                return df
            else:
                self.logger.warning(f"⚠️  {ts_code} 没有复权因子数据")
                return pd.DataFrame()

        except Exception as e:
            self.logger.error(f"❌ 获取复权因子失败: {e}")
            return pd.DataFrame()

    def calculate_adjusted_price(
        self,
        price_df: pd.DataFrame,
        adj_factor_df: pd.DataFrame,
        adjust_type: Literal["qfq", "hfq", "none"] = "qfq"
    ) -> pd.DataFrame:
        """
        计算复权价格

        Args:
            price_df: 原始价格数据
            adj_factor_df: 复权因子数据
            adjust_type: 复权类型 ("qfq": 前复权, "hfq": 后复权, "none": 不复权)

        Returns:
            包含复权价格的 DataFrame
        """
        if adjust_type == "none" or adj_factor_df.empty:
            # 不复权，直接返回原始数据
            price_df["adj_type"] = "none"
            return price_df

        # 合并价格和复权因子
        merged = pd.merge(
            price_df,
            adj_factor_df[["tradedate", "symbol", "adj_factor"]],
            on=["tradedate", "symbol"],
            how="left"
        )

        if adjust_type == "qfq":
            # 前复权：adj_price = price * adj_factor
            merged["adj_open"] = merged["open"] * merged["adj_factor"]
            merged["adj_high"] = merged["high"] * merged["adj_factor"]
            merged["adj_low"] = merged["low"] * merged["adj_factor"]
            merged["adj_close"] = merged["close"] * merged["adj_factor"]
            merged["adj_type"] = "qfq"

        elif adjust_type == "hfq":
            # 后复权：需要归一化到第一天的复权因子
            for symbol in merged["symbol"].unique():
                mask = merged["symbol"] == symbol
                symbol_data = merged[mask].copy()

                # 获取第一个非空复权因子
                first_factor = symbol_data["adj_factor"].dropna().iloc[0] if not symbol_data["adj_factor"].dropna().empty else 1.0

                # 计算后复权价格
                normalized_factor = symbol_data["adj_factor"] / first_factor
                merged.loc[mask, "adj_open"] = symbol_data["open"] * normalized_factor
                merged.loc[mask, "adj_high"] = symbol_data["high"] * normalized_factor
                merged.loc[mask, "adj_low"] = symbol_data["low"] * normalized_factor
                merged.loc[mask, "adj_close"] = symbol_data["close"] * normalized_factor

            merged["adj_type"] = "hfq"

        return merged

    def download_and_save_adjusted_data(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        adjust_type: Literal["qfq", "hfq", "none"] = "qfq"
    ) -> bool:
        """
        下载并保存复权数据

        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            adjust_type: 复权类型

        Returns:
            是否成功
        """
        self.logger.info("=" * 60)
        self.logger.info(f"下载复权数据: {adjust_type}")
        self.logger.info("=" * 60)

        all_adjusted_data = []

        for i, symbol in enumerate(symbols, 1):
            self.logger.info(f"[{i}/{len(symbols)}] 处理 {symbol}")

            try:
                # 获取原始价格数据
                price_data = self.client._make_request("daily", {
                    "ts_code": symbol,
                    "start_date": start_date,
                    "end_date": end_date
                })

                if not price_data or "items" not in price_data:
                    self.logger.warning(f"⚠️  {symbol} 没有价格数据")
                    continue

                price_df = pd.DataFrame(price_data["items"], columns=price_data["fields"])
                price_df = price_df.rename(columns={
                    "ts_code": "symbol",
                    "trade_date": "tradedate"
                })

                # 获取复权因子
                adj_factor_df = self.get_adj_factor(symbol, start_date, end_date)

                # 计算复权价格
                adjusted_df = self.calculate_adjusted_price(
                    price_df,
                    adj_factor_df,
                    adjust_type
                )

                all_adjusted_data.append(adjusted_df)

            except Exception as e:
                self.logger.error(f"❌ 处理 {symbol} 失败: {e}")
                continue

        # 保存数据
        if all_adjusted_data:
            combined_df = pd.concat(all_adjusted_data, ignore_index=True)

            # 根据复权类型保存到不同文件
            if adjust_type == "qfq":
                output_file = self.data_dir / "stock_data_qfq.csv"
            elif adjust_type == "hfq":
                output_file = self.data_dir / "stock_data_hfq.csv"
            else:
                output_file = self.data_dir / "stock_data_none.csv"

            # 排序和去重
            combined_df = combined_df.sort_values(["tradedate", "symbol"])
            combined_df = combined_df.drop_duplicates(
                subset=["tradedate", "symbol"],
                keep="last"
            )

            combined_df.to_csv(output_file, index=False)

            self.logger.info(f"✅ 复权数据已保存: {output_file}")
            self.logger.info(f"   总记录数: {len(combined_df):,}")
            self.logger.info(f"   日期范围: {combined_df['tradedate'].min()} -> {combined_df['tradedate'].max()}")
            self.logger.info(f"   股票数量: {combined_df['symbol'].nunique()}")

            return True
        else:
            self.logger.error("❌ 没有数据可保存")
            return False

    def visualize_adjustment(self, symbol: str, start_date: str, end_date: str):
        """
        可视化复权效果

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
        """
        self.logger.info(f"生成 {symbol} 的复权对比图")

        try:
            # 获取原始数据
            price_data = self.client._make_request("daily", {
                "ts_code": symbol,
                "start_date": start_date,
                "end_date": end_date
            })

            if not price_data or "items" not in price_data:
                self.logger.error(f"无法获取 {symbol} 的数据")
                return

            price_df = pd.DataFrame(price_data["items"], columns=price_data["fields"])
            price_df = price_df.rename(columns={
                "ts_code": "symbol",
                "trade_date": "tradedate"
            })

            # 获取复权因子
            adj_factor_df = self.get_adj_factor(symbol, start_date, end_date)

            # 计算各种复权价格
            none_df = self.calculate_adjusted_price(price_df.copy(), adj_factor_df, "none")
            qfq_df = self.calculate_adjusted_price(price_df.copy(), adj_factor_df, "qfq")
            hfq_df = self.calculate_adjusted_price(price_df.copy(), adj_factor_df, "hfq")

            # 创建图表
            fig, axes = plt.subplots(3, 1, figsize=(15, 12))

            # 子图1: 不复权 vs 前复权
            axes[0].plot(none_df["tradedate"], none_df["close"], label="不复权", alpha=0.7)
            axes[0].plot(qfq_df["tradedate"], qfq_df["adj_close"], label="前复权", alpha=0.7)
            axes[0].set_title(f"{symbol} - 不复权 vs 前复权")
            axes[0].legend()
            axes[0].grid(True, alpha=0.3)
            axes[0].tick_params(axis='x', rotation=45)

            # 子图2: 不复权 vs 后复权
            axes[1].plot(none_df["tradedate"], none_df["close"], label="不复权", alpha=0.7)
            axes[1].plot(hfq_df["tradedate"], hfq_df["adj_close"], label="后复权", alpha=0.7)
            axes[1].set_title(f"{symbol} - 不复权 vs 后复权")
            axes[1].legend()
            axes[1].grid(True, alpha=0.3)
            axes[1].tick_params(axis='x', rotation=45)

            # 子图3: 三种对比
            axes[2].plot(none_df["tradedate"], none_df["close"], label="不复权", alpha=0.7)
            axes[2].plot(qfq_df["tradedate"], qfq_df["adj_close"], label="前复权", alpha=0.7)
            axes[2].plot(hfq_df["tradedate"], hfq_df["adj_close"], label="后复权", alpha=0.7)
            axes[2].set_title(f"{symbol} - 三种复权对比")
            axes[2].legend()
            axes[2].grid(True, alpha=0.3)
            axes[2].tick_params(axis='x', rotation=45)

            plt.tight_layout()

            # 保存图表
            output_dir = self.data_dir / "adjustment_charts"
            output_dir.mkdir(exist_ok=True)
            output_file = output_dir / f"{symbol}_adjustment_comparison.png"
            plt.savefig(output_file, dpi=150, bbox_inches='tight')
            plt.close()

            self.logger.info(f"✅ 图表已保存: {output_file}")

        except Exception as e:
            self.logger.error(f"❌ 生成图表失败: {e}")


def explain_adjustment_events():
    """
    解释各种除权除息事件
    """
    print("\n" + "=" * 60)
    print("除权除息事件类型说明")
    print("=" * 60)

    events = {
        "现金分红": {
            "说明": "公司以现金形式向股东分配利润",
            "影响": "股价需要扣除分红金额",
            "例子": "每股分红 0.5 元，股价从 10 元降到 9.5 元",
            "复权处理": "前复权：历史价格 × (1 - 分红/股价)"
        },
        "送股": {
            "说明": "公司以股票形式向股东分配利润（如 10 送 10）",
            "影响": "股数增加，股价需要按比例调整",
            "例子": "10 送 10，股数翻倍，股价从 10 元降到 5 元",
            "复权处理": "前复权：历史价格 × (1 / (1 + 送股比例))"
        },
        "转增": {
            "说明": "资本公积金转增股本（类似送股）",
            "影响": "股数增加，股价需要按比例调整",
            "例子": "10 转 10，股数翻倍，股价从 10 元降到 5 元",
            "复权处理": "前复权：历史价格 × (1 / (1 + 转增比例))"
        },
        "配股": {
            "说明": "公司向原股东按比例配售新股",
            "影响": "股价需要考虑配股价格和比例",
            "例子": "10 配 3，配股价 8 元，原价 10 元",
            "复权处理": "前复权：复杂计算，需考虑配股比例和价格"
        },
        "拆股": {
            "说明": "公司将一股拆分成多股（如 1 拆 2）",
            "影响": "股数增加，股价按比例降低",
            "例子": "1 拆 2，股数翻倍，股价从 10 元降到 5 元",
            "复权处理": "前复权：历史价格 × 拆股比例"
        },
        "增发": {
            "说明": "公司向特定投资者发行新股",
            "影响": "通常不直接导致股价调整",
            "例子": "定向增发 1000 万股",
            "复权处理": "一般不需要复权"
        }
    }

    for event_name, event_info in events.items():
        print(f"\n📌 {event_name}")
        print(f"   说明: {event_info['说明']}")
        print(f"   影响: {event_info['影响']}")
        print(f"   例子: {event_info['例子']}")
        print(f"   复权: {event_info['复权处理']}")

    print("\n" + "=" * 60)
    print("复权类型对比")
    print("=" * 60)

    adjustment_types = {
        "前复权 (qfq)": {
            "特点": "当前价格不变，调整历史价格",
            "优点": "反映当前真实价格，适合技术分析",
            "缺点": "历史价格会变化，可能与实际不符",
            "适用": "短线交易、技术分析、趋势判断"
        },
        "后复权 (hfq)": {
            "特点": "最早价格不变，调整当前价格",
            "优点": "历史价格真实，适合长期分析",
            "缺点": "当前价格可能远低于实际",
            "适用": "长期投资分析、收益率计算"
        },
        "不复权 (none)": {
            "特点": "保持原始价格",
            "优点": "完全真实的历史价格",
            "缺点": "不同时期价格不可比",
            "适用": "当日交易分析、事件研究"
        }
    }

    for adj_type, type_info in adjustment_types.items():
        print(f"\n🔹 {adj_type}")
        print(f"   特点: {type_info['特点']}")
        print(f"   优点: {type_info['优点']}")
        print(f"   缺点: {type_info['缺点']}")
        print(f"   适用: {type_info['适用']}")

    print("\n")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("股票复权处理工具")
    print("=" * 60)

    # 检查环境变量
    if not os.getenv("TUSHARE_TOKEN"):
        print("❌ 错误: 未设置 TUSHARE_TOKEN 环境变量")
        print("\n请设置 TuShare API Token:")
        print("  export TUSHARE_TOKEN='your_token_here'")
        return

    # 显示事件说明
    explain_adjustment_events()

    # 创建处理器
    handler = AdjustFactorHandler()

    # 示例：可视化复权效果
    print("\n" + "=" * 60)
    print("示例：可视化复权效果")
    print("=" * 60)

    symbol = "000001.SZ"  # 平安银行
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")

    print(f"\n股票: {symbol}")
    print(f"日期范围: {start_date} -> {end_date}")
    print(f"正在生成复权对比图...")

    handler.visualize_adjustment(symbol, start_date, end_date)

    print("\n✅ 完成！")
    print(f"\n💡 提示:")
    print(f"   - 复权数据图表保存在: {handler.data_dir}/adjustment_charts/")
    print(f"   - 可以使用 download_and_save_adjusted_data() 下载批量复权数据")


if __name__ == "__main__":
    main()
