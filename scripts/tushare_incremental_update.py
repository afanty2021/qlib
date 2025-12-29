#!/usr/bin/env python3
"""
TuShare A股数据增量更新脚本

借鉴 investment_data 项目的增量更新思路，结合 Qlib 的 TuShare 集成，
实现本地 A股行情数据的增量更新功能。

主要功能：
- 自动检测最新数据日期
- 增量更新股票日线数据
- 增量更新指数数据
- 增量更新指数权重数据
- 数据验证和错误处理
- 进度跟踪和日志记录

使用方式：
    python scripts/tushare_incremental_update.py

环境变量：
    TUSHARE_TOKEN: TuShare API Token（必需）

配置文件：
    scripts/tushare_incremental_config.yaml: 增量更新配置
"""

import os
import sys
import logging
import time
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np
import yaml

# 添加项目路径到 sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from qlib.contrib.data.tushare.api_client import TuShareAPIClient
from qlib.contrib.data.tushare.config import TuShareConfig
from qlib.contrib.data.tushare.utils import (
    TuShareCodeConverter,
    TuShareDateUtils
)


class IncrementalDataUpdater:
    """
    增量数据更新器

    实现本地数据的增量更新逻辑，避免重复下载已有数据。
    """

    def __init__(self, config: Dict, data_dir: str = None):
        """
        初始化增量更新器

        Args:
            config: 配置字典
            data_dir: 数据存储目录
        """
        self.config = config
        self.data_dir = Path(data_dir or config.get("data_dir", "~/.qlib/qlib_data/cn_data"))
        self.data_dir = self.data_dir.expanduser()

        # 创建数据目录
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 初始化 TuShare 客户端
        tushare_config = TuShareConfig(
            token=os.getenv("TUSHARE_TOKEN"),
            max_retries=config.get("max_retries", 3),
            retry_delay=config.get("retry_delay", 1.0),
            rate_limit=config.get("rate_limit", 200),
            enable_api_logging=config.get("enable_api_logging", False)
        )
        self.client = TuShareAPIClient(tushare_config)

        # 设置日志
        self._setup_logging()

        # 跟踪统计
        self.stats = {
            "start_time": datetime.now(),
            "stocks_updated": 0,
            "indices_updated": 0,
            "index_weights_updated": 0,
            "errors": []
        }

    def _setup_logging(self):
        """设置日志系统"""
        log_level = self.config.get("log_level", "INFO")
        log_file = self.data_dir / "incremental_update.log"

        # 配置日志格式
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        date_format = "%Y-%m-%d %H:%M:%S"

        # 创建日志器
        self.logger = logging.getLogger("IncrementalUpdater")
        self.logger.setLevel(getattr(logging, log_level))

        # 清除现有处理器
        self.logger.handlers.clear()

        # 文件处理器
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(log_format, date_format))

        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, log_level))
        console_handler.setFormatter(logging.Formatter(log_format, date_format))

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

        self.logger.info("=" * 60)
        self.logger.info("增量数据更新开始")
        self.logger.info("=" * 60)

    def get_latest_date(self, data_type: str) -> Optional[str]:
        """
        获取指定数据类型的最新日期

        Args:
            data_type: 数据类型 ('stock', 'index', 'index_weight')

        Returns:
            最新日期字符串 (YYYYMMDD)，如果没有数据则返回 None
        """
        file_map = {
            "stock": self.data_dir / "stock_data.csv",
            "index": self.data_dir / "index_data.csv",
            "index_weight": self.data_dir / "index_weight.csv"
        }

        file_path = file_map.get(data_type)
        if not file_path or not file_path.exists():
            return None

        try:
            # 读取CSV文件获取最新日期
            df = pd.read_csv(file_path, nrows=1)

            # 根据数据类型确定日期列
            date_columns = {
                "stock": ["trade_date", "date", "tradedate"],
                "index": ["trade_date", "date", "tradedate"],
                "index_weight": ["trade_date", "date", "tradedate"]
            }

            for col in date_columns.get(data_type, []):
                if col in df.columns:
                    latest_date = df[col].iloc[0]
                    # 转换为 TuShare 日期格式
                    if isinstance(latest_date, str):
                        latest_date = latest_date.replace("-", "")
                    return latest_date

            return None
        except Exception as e:
            self.logger.warning(f"无法读取 {data_type} 数据的最新日期: {e}")
            return None

    def update_stock_data(self) -> bool:
        """
        增量更新股票日线数据

        Returns:
            更新是否成功
        """
        self.logger.info("\n" + "=" * 60)
        self.logger.info("开始更新股票日线数据")
        self.logger.info("=" * 60)

        try:
            # 获取最新数据日期
            latest_date = self.get_latest_date("stock")
            if latest_date:
                self.logger.info(f"本地数据最新日期: {latest_date}")
                start_date = latest_date
            else:
                self.logger.info("未找到本地数据，下载全部历史数据")
                start_date = self.config.get("stock_start_date", "20200101")

            # 获取当前日期
            end_date = datetime.now().strftime("%Y%m%d")

            # 获取交易日历
            self.logger.info(f"获取交易日历: {start_date} -> {end_date}")
            trade_cal = self.client.get_trade_cal(
                exchange="SSE",
                start_date=start_date,
                end_date=end_date,
                is_open="1"
            )

            if trade_cal.empty:
                self.logger.warning("没有新的交易日")
                return True

            trade_dates = trade_cal["cal_date"].tolist()
            self.logger.info(f"发现 {len(trade_dates)} 个新交易日")

            # 获取股票列表
            self.logger.info("获取股票列表...")
            stock_basic = self.client.get_stock_basic(
                exchange="",
                list_status="L"
            )

            if stock_basic.empty:
                self.logger.error("无法获取股票列表")
                return False

            stock_codes = stock_basic["ts_code"].tolist()
            self.logger.info(f"共有 {len(stock_codes)} 只股票")

            # 按交易日更新数据
            output_file = self.data_dir / "stock_data.csv"
            all_data = []

            for i, trade_date in enumerate(trade_dates, 1):
                self.logger.info(f"[{i}/{len(trade_dates)}] 更新 {trade_date} 的数据")

                try:
                    # 获取当日所有股票数据
                    data = self.client._make_request("daily", {
                        "trade_date": trade_date
                    })

                    if data and "items" in data and len(data["items"]) > 0:
                        # 转换为 DataFrame
                        df = pd.DataFrame(data["items"], columns=data["fields"])

                        # 字段映射
                        column_mapping = {
                            "ts_code": "symbol",
                            "trade_date": "tradedate",
                            "open": "open",
                            "high": "high",
                            "low": "low",
                            "close": "close",
                            "vol": "volume",
                            "amount": "amount"
                        }

                        # 选择需要的列并重命名
                        existing_cols = [col for col in column_mapping.keys() if col in df.columns]
                        df = df[existing_cols].rename(columns={k: column_mapping[k] for k in existing_cols})

                        all_data.append(df)
                        self.stats["stocks_updated"] += len(df)

                    # 避免频率限制
                    time.sleep(0.5)

                except Exception as e:
                    self.logger.error(f"更新 {trade_date} 数据失败: {e}")
                    self.stats["errors"].append(f"stock_{trade_date}: {str(e)}")
                    continue

            # 保存数据
            if all_data:
                combined_df = pd.concat(all_data, ignore_index=True)

                # 如果存在旧数据，合并后去重
                if output_file.exists():
                    old_df = pd.read_csv(output_file)
                    combined_df = pd.concat([old_df, combined_df])
                    combined_df = combined_df.drop_duplicates(
                        subset=["tradedate", "symbol"],
                        keep="last"
                    )
                    combined_df = combined_df.sort_values(["tradedate", "symbol"])

                combined_df.to_csv(output_file, index=False)
                self.logger.info(f"✅ 股票数据已保存到 {output_file}")
                self.logger.info(f"   共更新 {len(all_data)} 条记录")
                return True
            else:
                self.logger.warning("没有新数据需要保存")
                return True

        except Exception as e:
            self.logger.error(f"更新股票数据失败: {e}", exc_info=True)
            return False

    def update_index_data(self) -> bool:
        """
        增量更新指数日线数据

        Returns:
            更新是否成功
        """
        self.logger.info("\n" + "=" * 60)
        self.logger.info("开始更新指数日线数据")
        self.logger.info("=" * 60)

        try:
            # 获取需要更新的指数列表
            index_list = self.config.get("index_list", [
                "399300.SZ",  # 沪深300
                "000905.SH",  # 中证500
                "000300.SH",  # 沪深300
                "000906.SH",  # 中证800
                "000852.SH",  # 中证1000
                "000985.SH"   # 中证全指
            ])

            self.logger.info(f"需要更新的指数: {', '.join(index_list)}")

            # 获取最新数据日期
            latest_date = self.get_latest_date("index")
            if latest_date:
                self.logger.info(f"本地数据最新日期: {latest_date}")
                start_date = latest_date
            else:
                self.logger.info("未找到本地数据，下载全部历史数据")
                start_date = self.config.get("index_start_date", "20200101")

            end_date = datetime.now().strftime("%Y%m%d")

            # 获取交易日历
            self.logger.info(f"获取交易日历: {start_date} -> {end_date}")
            trade_cal = self.client.get_trade_cal(
                exchange="SSE",
                start_date=start_date,
                end_date=end_date,
                is_open="1"
            )

            if trade_cal.empty:
                self.logger.warning("没有新的交易日")
                return True

            trade_dates = trade_cal["cal_date"].tolist()
            self.logger.info(f"发现 {len(trade_dates)} 个新交易日")

            # 更新每个指数的数据
            all_data = []

            for index_code in index_list:
                self.logger.info(f"更新指数 {index_code}")

                try:
                    # 获取指数数据
                    data = self.client.get_index_daily(
                        ts_code=index_code,
                        start_date=start_date,
                        end_date=end_date
                    )

                    if not data.empty:
                        # 字段映射
                        df = data.rename(columns={
                            "ts_code": "symbol",
                            "trade_date": "tradedate"
                        })

                        all_data.append(df)
                        self.stats["indices_updated"] += len(df)

                    # 避免频率限制
                    time.sleep(0.3)

                except Exception as e:
                    self.logger.error(f"更新指数 {index_code} 失败: {e}")
                    self.stats["errors"].append(f"index_{index_code}: {str(e)}")
                    continue

            # 保存数据
            if all_data:
                combined_df = pd.concat(all_data, ignore_index=True)

                output_file = self.data_dir / "index_data.csv"

                # 如果存在旧数据，合并后去重
                if output_file.exists():
                    old_df = pd.read_csv(output_file)
                    combined_df = pd.concat([old_df, combined_df])
                    combined_df = combined_df.drop_duplicates(
                        subset=["tradedate", "symbol"],
                        keep="last"
                    )
                    combined_df = combined_df.sort_values(["tradedate", "symbol"])

                combined_df.to_csv(output_file, index=False)
                self.logger.info(f"✅ 指数数据已保存到 {output_file}")
                self.logger.info(f"   共更新 {len(all_data)} 条记录")
                return True
            else:
                self.logger.warning("没有新数据需要保存")
                return True

        except Exception as e:
            self.logger.error(f"更新指数数据失败: {e}", exc_info=True)
            return False

    def update_index_weight(self) -> bool:
        """
        增量更新指数权重数据

        Returns:
            更新是否成功
        """
        self.logger.info("\n" + "=" * 60)
        self.logger.info("开始更新指数权重数据")
        self.logger.info("=" * 60)

        try:
            # 获取需要更新的指数列表
            index_list = self.config.get("index_weight_list", [
                "000905.SH",  # 中证500
                "399300.SZ",  # 沪深300
                "000906.SH",  # 中证800
                "000852.SH",  # 中证1000
                "000985.SH"   # 中证全指
            ])

            self.logger.info(f"需要更新权重的指数: {', '.join(index_list)}")

            # 获取最新数据日期
            latest_date = self.get_latest_date("index_weight")
            if latest_date:
                self.logger.info(f"本地数据最新日期: {latest_date}")
                start_date_obj = datetime.strptime(latest_date, "%Y%m%d")
                start_date = start_date_obj.strftime("%Y%m%d")
            else:
                self.logger.info("未找到本地数据，下载全部历史数据")
                start_date = None

            end_date = datetime.now().strftime("%Y%m%d")

            all_data = []

            for index_code in index_list:
                self.logger.info(f"更新指数 {index_code} 的权重")

                try:
                    # 获取指数基本信息
                    if not start_date:
                        stock_basic = self.client.get_stock_basic()
                        index_info = stock_basic[stock_basic["ts_code"] == index_code]
                        if not index_info.empty:
                            list_date = index_info["list_date"].iloc[0]
                            start_date_obj = datetime.strptime(list_date, "%Y%m%d")
                        else:
                            start_date_obj = datetime.now() - timedelta(days=365)
                    else:
                        start_date_obj = datetime.strptime(start_date, "%Y%m%d")

                    # 按15天步长获取数据
                    time_step = timedelta(days=15)
                    index_start_date = start_date_obj
                    index_end_date = index_start_date + time_step

                    empty_count = 0
                    index_data_list = []

                    while index_end_date < datetime.now():
                        try:
                            data = self.client.get_index_weight(
                                index_code=index_code,
                                start_date=index_start_date.strftime("%Y%m%d"),
                                end_date=index_end_date.strftime("%Y%m%d")
                            )

                            if not data.empty:
                                index_data_list.append(data)
                                empty_count = 0
                            else:
                                empty_count += 1
                                if empty_count >= 20:
                                    self.logger.warning(
                                        f"指数 {index_code} 连续20次无数据，停止获取"
                                    )
                                    break

                            # 避免频率限制
                            time.sleep(0.3)

                        except Exception as e:
                            self.logger.error(f"获取 {index_code} 权重失败: {e}")

                        index_start_date += time_step
                        index_end_date += time_step

                    if index_data_list:
                        combined_index_data = pd.concat(index_data_list, ignore_index=True)

                        # 字段映射
                        df = combined_index_data.rename(columns={
                            "con_code": "stock_code",
                            "index_code": "symbol",
                            "trade_date": "tradedate"
                        })

                        all_data.append(df)
                        self.stats["index_weights_updated"] += len(df)

                except Exception as e:
                    self.logger.error(f"更新指数 {index_code} 权重失败: {e}")
                    self.stats["errors"].append(f"index_weight_{index_code}: {str(e)}")
                    continue

            # 保存数据
            if all_data:
                combined_df = pd.concat(all_data, ignore_index=True)

                output_file = self.data_dir / "index_weight.csv"

                # 如果存在旧数据，合并后去重
                if output_file.exists():
                    old_df = pd.read_csv(output_file)
                    combined_df = pd.concat([old_df, combined_df])
                    combined_df = combined_df.drop_duplicates(
                        subset=["tradedate", "symbol", "stock_code"],
                        keep="last"
                    )
                    combined_df = combined_df.sort_values(["tradedate", "symbol", "stock_code"])

                combined_df.to_csv(output_file, index=False)
                self.logger.info(f"✅ 指数权重数据已保存到 {output_file}")
                self.logger.info(f"   共更新 {len(all_data)} 条记录")
                return True
            else:
                self.logger.warning("没有新数据需要保存")
                return True

        except Exception as e:
            self.logger.error(f"更新指数权重数据失败: {e}", exc_info=True)
            return False

    def validate_data(self) -> bool:
        """
        验证更新后的数据质量

        Returns:
            验证是否通过
        """
        self.logger.info("\n" + "=" * 60)
        self.logger.info("开始数据验证")
        self.logger.info("=" * 60)

        validation_passed = True

        # 验证股票数据
        stock_file = self.data_dir / "stock_data.csv"
        if stock_file.exists():
            try:
                df = pd.read_csv(stock_file)
                self.logger.info(f"股票数据: {len(df)} 条记录")
                self.logger.info(f"  日期范围: {df['tradedate'].min()} -> {df['tradedate'].max()}")
                self.logger.info(f"  股票数量: {df['symbol'].nunique()}")
            except Exception as e:
                self.logger.error(f"股票数据验证失败: {e}")
                validation_passed = False

        # 验证指数数据
        index_file = self.data_dir / "index_data.csv"
        if index_file.exists():
            try:
                df = pd.read_csv(index_file)
                self.logger.info(f"指数数据: {len(df)} 条记录")
                self.logger.info(f"  日期范围: {df['tradedate'].min()} -> {df['tradedate'].max()}")
                self.logger.info(f"  指数数量: {df['symbol'].nunique()}")
            except Exception as e:
                self.logger.error(f"指数数据验证失败: {e}")
                validation_passed = False

        # 验证指数权重数据
        weight_file = self.data_dir / "index_weight.csv"
        if weight_file.exists():
            try:
                df = pd.read_csv(weight_file)
                self.logger.info(f"指数权重数据: {len(df)} 条记录")
                self.logger.info(f"  日期范围: {df['tradedate'].min()} -> {df['tradedate'].max()}")
                self.logger.info(f"  指数数量: {df['symbol'].nunique()}")
            except Exception as e:
                self.logger.error(f"指数权重数据验证失败: {e}")
                validation_passed = False

        if validation_passed:
            self.logger.info("✅ 数据验证通过")
        else:
            self.logger.error("❌ 数据验证失败")

        return validation_passed

    def run(self) -> bool:
        """
        执行完整的增量更新流程

        Returns:
            更新是否全部成功
        """
        self.logger.info(f"配置信息:")
        self.logger.info(f"  数据目录: {self.data_dir}")
        self.logger.info(f"  开始时间: {self.stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")

        try:
            # 更新股票数据
            if self.config.get("update_stock", True):
                if not self.update_stock_data():
                    self.logger.error("股票数据更新失败")
                    return False

            # 更新指数数据
            if self.config.get("update_index", True):
                if not self.update_index_data():
                    self.logger.error("指数数据更新失败")
                    return False

            # 更新指数权重
            if self.config.get("update_index_weight", True):
                if not self.update_index_weight():
                    self.logger.error("指数权重更新失败")
                    return False

            # 验证数据
            if self.config.get("validate_data", True):
                self.validate_data()

            # 输出统计信息
            self._print_summary()

            return True

        except Exception as e:
            self.logger.error(f"增量更新失败: {e}", exc_info=True)
            return False

    def _print_summary(self):
        """输出更新统计摘要"""
        elapsed_time = (datetime.now() - self.stats["start_time"]).total_seconds()

        self.logger.info("\n" + "=" * 60)
        self.logger.info("增量更新完成 - 统计摘要")
        self.logger.info("=" * 60)
        self.logger.info(f"⏱️  耗时: {elapsed_time:.2f} 秒")
        self.logger.info(f"📊 股票数据更新: {self.stats['stocks_updated']} 条")
        self.logger.info(f"📈 指数数据更新: {self.stats['indices_updated']} 条")
        self.logger.info(f"⚖️  指数权重更新: {self.stats['index_weights_updated']} 条")

        if self.stats["errors"]:
            self.logger.warning(f"⚠️  错误数量: {len(self.stats['errors'])}")
            for error in self.stats["errors"][:5]:  # 只显示前5个错误
                self.logger.warning(f"   - {error}")
            if len(self.stats["errors"]) > 5:
                self.logger.warning(f"   ... 还有 {len(self.stats['errors']) - 5} 个错误")
        else:
            self.logger.info("✅ 没有错误")

        self.logger.info("=" * 60)


def load_config(config_path: str = None) -> Dict:
    """
    加载配置文件

    Args:
        config_path: 配置文件路径

    Returns:
        配置字典
    """
    if config_path is None:
        # 默认配置文件路径
        script_dir = Path(__file__).parent
        config_path = script_dir / "tushare_incremental_config.yaml"

    config_file = Path(config_path)

    if config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    else:
        # 返回默认配置
        return {
            "data_dir": "~/.qlib/qlib_data/cn_data",
            "max_retries": 3,
            "retry_delay": 1.0,
            "rate_limit": 200,
            "log_level": "INFO",
            "enable_api_logging": False,
            "update_stock": True,
            "update_index": True,
            "update_index_weight": True,
            "validate_data": True,
            "stock_start_date": "20200101",
            "index_start_date": "20200101",
            "index_list": [
                "399300.SZ",  # 沪深300
                "000905.SH",  # 中证500
                "000300.SH",  # 沪深300
                "000906.SH",  # 中证800
                "000852.SH",  # 中证1000
                "000985.SH"   # 中证全指
            ],
            "index_weight_list": [
                "000905.SH",  # 中证500
                "399300.SZ",  # 沪深300
                "000906.SH",  # 中证800
                "000852.SH",  # 中证1000
                "000985.SH"   # 中证全指
            ]
        }


def main():
    """主函数"""
    print("=" * 60)
    print("TuShare A股数据增量更新脚本")
    print("=" * 60)

    # 检查环境变量
    if not os.getenv("TUSHARE_TOKEN"):
        print("❌ 错误: 未设置 TUSHARE_TOKEN 环境变量")
        print("请设置 TuShare API Token:")
        print("  export TUSHARE_TOKEN='your_token_here'")
        sys.exit(1)

    # 加载配置
    config = load_config()

    # 创建更新器并执行更新
    updater = IncrementalDataUpdater(config)

    success = updater.run()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
