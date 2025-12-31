#!/usr/bin/env python3
"""
ETF数据自动下载脚本

功能：
- 从TuShare获取ETF日线行情数据
- 支持增量更新（检测本地最新日期）
- 支持全量历史数据下载
- 自动转换为Qlib格式

使用方式：
    # 下载指定ETF数据
    python scripts/etf_auto_download.py --etf-codes 510300.SH,510500.SH

    # 下载主流ETF数据
    python scripts/etf_auto_download.py --main-etf

    # 下载数据并转换为Qlib格式
    python scripts/etf_auto_download.py --convert-qlib

环境变量：
    TUSHARE_TOKEN: TuShare API Token（必需）

配置文件：
    scripts/etf_config.yaml: ETF列表和配置
"""

import os
import sys
import logging
import time
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np
import yaml

# 添加项目路径到 sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 尝试导入TuShare客户端
try:
    from qlib.contrib.data.tushare.api_client import TuShareAPIClient
    from qlib.contrib.data.tushare.config import TuShareConfig
    TUSHARE_AVAILABLE = True
except ImportError:
    TUSHARE_AVAILABLE = False


def load_config(config_file: str = None) -> dict:
    """
    加载配置文件

    Args:
        config_file: 配置文件路径

    Returns:
        配置字典
    """
    if config_file is None:
        # 默认配置文件路径
        config_file = Path(__file__).parent / "etf_config.yaml"

    config_path = Path(config_file)

    if not config_path.exists():
        print(f"⚠️  配置文件不存在: {config_path}")
        print("使用空配置（需要通过 --etf-codes 指定ETF列表）")
        return {"etf_list": []}

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            return config or {}
    except Exception as e:
        print(f"⚠️  配置文件加载失败: {e}")
        return {"etf_list": []}


class ETFDataDownloader:
    """ETF数据下载器"""

    def __init__(
        self,
        token: str = None,
        data_dir: str = "~/.qlib/qlib_data/cn_data/etf_raw",
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """
        初始化ETF数据下载器

        Args:
            token: TuShare API Token
            data_dir: 原始数据存储目录
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
        """
        self.data_dir = Path(data_dir).expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 设置日志
        self.logger = self._setup_logger()

        # 初始化TuShare客户端
        if TUSHARE_AVAILABLE:
            config = TuShareConfig(
                token=token,
                max_retries=max_retries,
                retry_delay=retry_delay,
                rate_limit=200
            )
            self.client = TuShareAPIClient(config)
        else:
            import tushare as ts
            ts.set_token(token)
            self.client = ts.pro_api()

        # 统计信息
        self.stats = {
            "total_etfs": 0,
            "success_count": 0,
            "failed_count": 0,
            "total_records": 0,
            "errors": []
        }

    def _setup_logger(self) -> logging.Logger:
        """设置日志系统"""
        logger = logging.getLogger("ETFDownloader")
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            # 日志格式
            log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            date_format = "%Y-%m-%d %H:%M:%S"
            formatter = logging.Formatter(log_format, date_format)

            # 文件处理器
            log_file = self.data_dir / "etf_download.log"
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)

            # 控制台处理器
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(formatter)

            logger.addHandler(file_handler)
            logger.addHandler(console_handler)

        return logger

    def get_latest_date(self, etf_code: str) -> Optional[str]:
        """
        获取指定ETF的最新数据日期

        Args:
            etf_code: ETF代码

        Returns:
            最新日期字符串 (YYYY-MM-DD)，如果没有数据则返回 None
        """
        csv_file = self.data_dir / f"{etf_code}.csv"

        if not csv_file.exists():
            return None

        try:
            # 读取文件的最后一行
            df = pd.read_csv(csv_file, nrows=1)
            if not df.empty and 'trade_date' in df.columns:
                latest_date = df['trade_date'].iloc[0]
                # 处理不同的日期格式
                if pd.isna(latest_date):
                    return None
                # 如果是整数类型（numpy.int64或int），转换为字符串
                if isinstance(latest_date, (int, np.integer)):
                    latest_date = str(latest_date)
                    # 转换为 YYYY-MM-DD 格式
                    if len(latest_date) == 8:
                        latest_date = f"{latest_date[:4]}-{latest_date[4:6]}-{latest_date[6:8]}"
                # 如果是字符串类型，直接使用
                elif isinstance(latest_date, str):
                    if len(latest_date) == 8 and latest_date.isdigit():
                        # YYYYMMDD 格式转为 YYYY-MM-DD
                        latest_date = f"{latest_date[:4]}-{latest_date[4:6]}-{latest_date[6:8]}"
                return latest_date
            return None
        except Exception as e:
            self.logger.warning(f"无法读取 {etf_code} 的最新日期: {e}")
            return None

    def download_etf_data(
        self,
        etf_code: str,
        start_date: str = None,
        end_date: str = None
    ) -> Optional[pd.DataFrame]:
        """
        下载单个ETF的历史数据

        Args:
            etf_code: ETF代码
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)

        Returns:
            ETF数据DataFrame，如果失败则返回None
        """
        # 默认日期范围
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")
        if start_date is None:
            # 默认从2010年开始
            start_date = "20100101"

        try:
            self.logger.info(f"📥 正在下载 {etf_code} 数据...")

            if TUSHARE_AVAILABLE:
                # 使用Qlib的TuShare客户端
                data = self.client._make_request("fund_daily", {
                    "ts_code": etf_code,
                    "start_date": start_date,
                    "end_date": end_date
                })

                if data and "items" in data and len(data["items"]) > 0:
                    df = pd.DataFrame(data["items"], columns=data["fields"])
                else:
                    self.logger.warning(f"  ⚠️  {etf_code} 无数据")
                    return None
            else:
                # 使用原生tushare
                data = self.client.fund_daily(
                    ts_code=etf_code,
                    start_date=start_date,
                    end_date=end_date
                )
                df = pd.DataFrame(data)

            if df.empty:
                self.logger.warning(f"  ⚠️  {etf_code} 返回空数据")
                return None

            self.logger.info(f"  ✅ {etf_code} 获取到 {len(df)} 条记录")
            return df

        except Exception as e:
            self.logger.error(f"  ❌ {etf_code} 下载失败: {e}")
            self.stats["errors"].append(f"{etf_code}: {str(e)}")
            return None

    def save_to_csv(self, df: pd.DataFrame, etf_code: str):
        """
        保存ETF数据到CSV文件

        Args:
            df: ETF数据DataFrame
            etf_code: ETF代码
        """
        csv_file = self.data_dir / f"{etf_code}.csv"

        try:
            # 确保 trade_date 列是字符串类型
            if 'trade_date' in df.columns:
                # 处理整数类型的日期
                df['trade_date'] = df['trade_date'].apply(
                    lambda x: str(int(x)) if pd.notna(x) and isinstance(x, (int, np.integer)) else x
                )

            # 如果文件已存在，追加数据
            if csv_file.exists():
                existing_df = pd.read_csv(csv_file)
                # 同样处理现有数据的日期列
                if 'trade_date' in existing_df.columns:
                    existing_df['trade_date'] = existing_df['trade_date'].apply(
                        lambda x: str(int(x)) if pd.notna(x) and isinstance(x, (int, np.integer)) else x
                    )

                # 合并数据，去重
                df = pd.concat([existing_df, df], ignore_index=True)
                df = df.drop_duplicates(subset=['trade_date'], keep='last')

                # 按日期降序排序（最新的在前）
                df = df.sort_values('trade_date', ascending=False)

            # 保存到CSV
            df.to_csv(csv_file, index=False)
            self.logger.info(f"  💾 已保存到 {csv_file.name} ({len(df)} 条记录)")
            self.stats["total_records"] += len(df)

        except Exception as e:
            self.logger.error(f"  ❌ 保存失败: {e}")
            raise

    def download_incremental(self, etf_codes: List[str]) -> bool:
        """
        增量下载ETF数据

        Args:
            etf_codes: ETF代码列表

        Returns:
            是否全部成功
        """
        self.logger.info("=" * 60)
        self.logger.info("🚀 开始增量下载ETF数据")
        self.logger.info("=" * 60)

        self.stats["total_etfs"] = len(etf_codes)

        for etf_code in etf_codes:
            try:
                # 获取本地最新日期
                latest_date = self.get_latest_date(etf_code)

                if latest_date:
                    # 转换为TuShare日期格式
                    latest_date_ts = latest_date.replace("-", "")
                    # 从最新日期的下一天开始下载
                    next_date = (pd.Timestamp(latest_date) + timedelta(days=1)).strftime("%Y%m%d")
                    self.logger.info(f"📊 {etf_code} 本地最新日期: {latest_date}")
                    start_date = next_date
                else:
                    self.logger.info(f"📊 {etf_code} 首次下载")
                    start_date = None  # 使用默认起始日期

                # 下载今日数据
                end_date = datetime.now().strftime("%Y%m%d")

                # 如果start_date在end_date之后，说明数据已是最新
                if start_date and start_date > end_date:
                    self.logger.info(f"  ✅ {etf_code} 数据已是最新")
                    self.stats["success_count"] += 1
                    continue

                # 下载数据
                df = self.download_etf_data(etf_code, start_date, end_date)

                if df is not None:
                    self.save_to_csv(df, etf_code)
                    self.stats["success_count"] += 1
                else:
                    self.stats["failed_count"] += 1

                # 避免请求过快
                time.sleep(0.2)

            except Exception as e:
                self.logger.error(f"❌ {etf_code} 处理失败: {e}")
                self.stats["errors"].append(f"{etf_code}: {str(e)}")
                self.stats["failed_count"] += 1

        return self.stats["failed_count"] == 0

    def download_all(self, etf_codes: List[str]) -> bool:
        """
        全量下载ETF历史数据

        Args:
            etf_codes: ETF代码列表

        Returns:
            是否全部成功
        """
        self.logger.info("=" * 60)
        self.logger.info("🚀 开始全量下载ETF数据")
        self.logger.info("=" * 60)

        self.stats["total_etfs"] = len(etf_codes)

        for etf_code in etf_codes:
            try:
                # 下载全部历史数据
                df = self.download_etf_data(etf_code)

                if df is not None:
                    self.save_to_csv(df, etf_code)
                    self.stats["success_count"] += 1
                else:
                    self.stats["failed_count"] += 1

                # 避免请求过快
                time.sleep(0.2)

            except Exception as e:
                self.logger.error(f"❌ {etf_code} 处理失败: {e}")
                self.stats["errors"].append(f"{etf_code}: {str(e)}")
                self.stats["failed_count"] += 1

        return self.stats["failed_count"] == 0

    def print_summary(self):
        """打印下载摘要"""
        self.logger.info("\n" + "=" * 60)
        self.logger.info("📊 下载摘要")
        self.logger.info("=" * 60)
        self.logger.info(f"总ETF数量: {self.stats['total_etfs']}")
        self.logger.info(f"成功: {self.stats['success_count']}")
        self.logger.info(f"失败: {self.stats['failed_count']}")
        self.logger.info(f"总记录数: {self.stats['total_records']}")

        if self.stats["errors"]:
            self.logger.info("\n❌ 失败列表:")
            for error in self.stats["errors"][:10]:  # 只显示前10个错误
                self.logger.info(f"  - {error}")

        self.logger.info("=" * 60)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="ETF数据自动下载脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:

  # 使用配置文件下载ETF数据（增量更新）
  python scripts/etf_auto_download.py

  # 使用指定配置文件
  python scripts/etf_auto_download.py --config custom_etf_config.yaml

  # 下载指定ETF数据
  python scripts/etf_auto_download.py --etf-codes 510300.SH,510500.SH

  # 全量下载历史数据
  python scripts/etf_auto_download.py --full-download

  # 下载并转换为Qlib格式
  python scripts/etf_auto_download.py --convert-qlib
        """
    )

    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="配置文件路径（默认: scripts/etf_config.yaml）"
    )

    parser.add_argument(
        "--etf-codes",
        type=str,
        help="ETF代码列表，逗号分隔，例如: 510300.SH,510500.SH（覆盖配置文件）"
    )

    parser.add_argument(
        "--full-download",
        action="store_true",
        help="全量下载历史数据（默认增量更新）"
    )

    parser.add_argument(
        "--convert-qlib",
        action="store_true",
        help="转换为Qlib格式"
    )

    parser.add_argument(
        "--data-dir",
        type=str,
        default="~/.qlib/qlib_data/cn_data/etf_raw",
        help="原始数据存储目录"
    )

    parser.add_argument(
        "--qlib-dir",
        type=str,
        default="~/.qlib/qlib_data/cn_data/etf",
        help="Qlib格式数据存储目录"
    )

    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()

    # 检查Token
    token = os.getenv("TUSHARE_TOKEN")
    if not token:
        print("❌ 未设置 TUSHARE_TOKEN 环境变量")
        print("请设置: export TUSHARE_TOKEN='your_token_here'")
        sys.exit(1)

    # 确定ETF列表
    if args.etf_codes:
        # 命令行指定的ETF列表（优先级最高）
        etf_codes = [code.strip() for code in args.etf_codes.split(",")]
        print(f"📋 使用命令行指定的ETF列表 ({len(etf_codes)} 个)")
    else:
        # 从配置文件读取
        config = load_config(args.config)
        etf_codes = config.get("etf_list", [])

        if not etf_codes:
            print("❌ 配置文件中未找到ETF列表")
            print("请通过以下方式之一指定ETF：")
            print("  1. 在配置文件中配置 etf_list")
            print("  2. 使用 --etf-codes 参数指定")
            sys.exit(1)

        print(f"📋 使用配置文件的ETF列表 ({len(etf_codes)} 个)")

    # 打印ETF列表摘要
    if len(etf_codes) <= 10:
        print(f"   {', '.join(etf_codes)}")
    else:
        print(f"   {', '.join(etf_codes[:5])}... 等共 {len(etf_codes)} 个")

    # 创建下载器
    downloader = ETFDataDownloader(
        token=token,
        data_dir=args.data_dir
    )

    # 下载数据
    if args.full_download:
        success = downloader.download_all(etf_codes)
    else:
        success = downloader.download_incremental(etf_codes)

    # 打印摘要
    downloader.print_summary()

    # 转换为Qlib格式
    if args.convert_qlib and success:
        print("\n" + "=" * 60)
        print("🔄 开始转换为Qlib格式...")
        print("=" * 60)

        convert_script = Path(__file__).parent / "etf_convert_qlib.py"
        if convert_script.exists():
            import subprocess
            cmd = [
                sys.executable,
                str(convert_script),
                "--source-dir", args.data_dir,
                "--qlib-dir", args.qlib_dir
            ]
            subprocess.run(cmd)
        else:
            print(f"❌ 转换脚本不存在: {convert_script}")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
