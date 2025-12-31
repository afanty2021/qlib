#!/usr/bin/env python3
"""
ETF数据每日自动更新完整脚本

功能：
- 自动从TuShare获取ETF当日数据
- 如果历史数据不存在则自动补充
- 自动转换为Qlib格式
- 完善的错误处理和日志记录
- 可选的通知功能

使用方式：
    # 直接运行（使用默认配置）
    python scripts/etf_daily_update.py

    # 指定配置文件
    python scripts/etf_daily_update.py --config etf_config.yaml

    # 全量下载历史数据
    python scripts/etf_daily_update.py --full-download

环境变量：
    TUSHARE_TOKEN: TuShare API Token（必需）
"""

import os
import sys
import logging
import time
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
import yaml

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class ETFDailyUpdater:
    """ETF数据每日更新器（完整版）"""

    def __init__(
        self,
        token: str = None,
        data_dir: str = "~/.qlib/qlib_data/cn_data/etf_raw",
        qlib_dir: str = "~/.qlib/qlib_data/cn_data/etf",
        config_file: str = None
    ):
        """
        初始化更新器

        Args:
            token: TuShare API Token
            data_dir: 原始数据存储目录
            qlib_dir: Qlib格式数据目录
            config_file: 配置文件路径
        """
        self.data_dir = Path(data_dir).expanduser()
        self.qlib_dir = Path(qlib_dir).expanduser()

        # 创建目录
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.qlib_dir.mkdir(parents=True, exist_ok=True)

        # 加载配置
        self.config = self._load_config(config_file)

        # 设置日志
        self.logger = self._setup_logger()

        # 初始化TuShare客户端
        self._init_tushare_client(token)

        # 统计信息
        self.stats = {
            "start_time": datetime.now(),
            "etf_list": [],
            "downloaded": [],
            "failed": [],
            "converted": [],
            "errors": []
        }

    def _load_config(self, config_file: str = None) -> dict:
        """加载配置文件"""
        default_config = {
            "etf_list": [],  # 从配置文件读取，不再使用硬编码
            "download_interval": 0.2,  # 下载间隔（秒）
            "max_retries": 3,
            "convert_to_qlib": True,
            "enable_notification": False,
            "log_level": "INFO"
        }

        # 默认配置文件路径
        if config_file is None:
            config_file = Path(__file__).parent / "etf_config.yaml"

        config_path = Path(config_file)

        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    user_config = yaml.safe_load(f)
                    if user_config:
                        default_config.update(user_config)
            except Exception as e:
                self.logger = logging.getLogger("ETFDailyUpdater")
                self.logger.warning(f"配置文件加载失败: {e}，使用默认配置")
        else:
            # 如果配置文件不存在，记录警告
            print(f"⚠️  配置文件不存在: {config_path}")
            print("请在配置文件中配置 etf_list")

        return default_config

    def _setup_logger(self) -> logging.Logger:
        """设置日志系统"""
        logger = logging.getLogger("ETFDailyUpdater")
        logger.setLevel(getattr(logging, self.config.get("log_level", "INFO")))

        if not logger.handlers:
            # 日志格式
            log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            date_format = "%Y-%m-%d %H:%M:%S"
            formatter = logging.Formatter(log_format, date_format)

            # 文件处理器（按日期分割）
            log_file = self.data_dir / f"update_{datetime.now().strftime('%Y%m%d')}.log"
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

    def _init_tushare_client(self, token: str):
        """初始化TuShare客户端"""
        if token is None:
            token = os.getenv("TUSHARE_TOKEN")

        if not token:
            raise ValueError("未设置TUSHARE_TOKEN环境变量或参数")

        try:
            from qlib.contrib.data.tushare.api_client import TuShareAPIClient
            from qlib.contrib.data.tushare.config import TuShareConfig

            config = TuShareConfig(
                token=token,
                max_retries=self.config.get("max_retries", 3),
                retry_delay=1.0,
                rate_limit=200
            )
            self.client = TuShareAPIClient(config)
            self.tushare_available = True

        except ImportError:
            import tushare as ts
            ts.set_token(token)
            self.client = ts.pro_api()
            self.tushare_available = False

    def get_latest_date(self, etf_code: str) -> Optional[str]:
        """获取本地最新数据日期"""
        csv_file = self.data_dir / f"{etf_code}.csv"

        if not csv_file.exists():
            return None

        try:
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
        except Exception:
            return None

    def download_etf_data(
        self,
        etf_code: str,
        start_date: str = None,
        end_date: str = None
    ) -> Optional[pd.DataFrame]:
        """下载ETF数据"""
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")

        try:
            if self.tushare_available:
                data = self.client._make_request("fund_daily", {
                    "ts_code": etf_code,
                    "start_date": start_date or "20100101",
                    "end_date": end_date
                })

                if data and "items" in data and len(data["items"]) > 0:
                    return pd.DataFrame(data["items"], columns=data["fields"])
            else:
                df = self.client.fund_daily(
                    ts_code=etf_code,
                    start_date=start_date or "20100101",
                    end_date=end_date
                )
                return pd.DataFrame(df)

        except Exception as e:
            self.logger.error(f"❌ {etf_code} 下载失败: {e}")
            self.stats["errors"].append(f"{etf_code}: {str(e)}")

        return None

    def save_to_csv(self, df: pd.DataFrame, etf_code: str):
        """保存数据到CSV"""
        csv_file = self.data_dir / f"{etf_code}.csv"

        try:
            # 确保 trade_date 列是字符串类型
            if 'trade_date' in df.columns:
                # 处理整数类型的日期
                df['trade_date'] = df['trade_date'].apply(
                    lambda x: str(int(x)) if pd.notna(x) and isinstance(x, (int, np.integer)) else x
                )

            if csv_file.exists():
                existing_df = pd.read_csv(csv_file)
                # 同样处理现有数据的日期列
                if 'trade_date' in existing_df.columns:
                    existing_df['trade_date'] = existing_df['trade_date'].apply(
                        lambda x: str(int(x)) if pd.notna(x) and isinstance(x, (int, np.integer)) else x
                    )

                df = pd.concat([existing_df, df], ignore_index=True)
                df = df.drop_duplicates(subset=['trade_date'], keep='last')
                df = df.sort_values('trade_date', ascending=False)

            df.to_csv(csv_file, index=False)

        except Exception as e:
            self.logger.error(f"❌ {etf_code} 保存失败: {e}")
            raise

    def convert_to_qlib(self):
        """转换为Qlib格式"""
        self.logger.info("🔄 开始转换为Qlib格式...")

        # 调用转换脚本
        convert_script = Path(__file__).parent / "etf_convert_qlib.py"

        if convert_script.exists():
            import subprocess
            cmd = [
                sys.executable,
                str(convert_script),
                "--source-dir", str(self.data_dir),
                "--qlib-dir", str(self.qlib_dir)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                self.logger.info("✅ Qlib格式转换完成")
                return True
            else:
                self.logger.error(f"❌ 转换失败: {result.stderr}")
                return False
        else:
            self.logger.warning(f"⚠️  转换脚本不存在: {convert_script}")
            return False

    def run(self, full_download: bool = False):
        """执行更新"""
        self.logger.info("=" * 60)
        self.logger.info("🚀 ETF数据每日更新开始")
        self.logger.info("=" * 60)

        etf_list = self.config.get("etf_list", [])

        if not etf_list:
            self.logger.error("❌ 配置文件中未找到ETF列表")
            self.logger.error("请在 etf_config.yaml 中配置 etf_list")
            return

        self.stats["etf_list"] = etf_list
        self.logger.info(f"📋 共 {len(etf_list)} 个ETF待更新")

        for etf_code in etf_list:
            try:
                # 确定下载日期范围
                if full_download:
                    start_date = None
                    self.logger.info(f"📥 {etf_code} 全量下载...")
                else:
                    latest_date = self.get_latest_date(etf_code)
                    if latest_date:
                        next_date = (pd.Timestamp(latest_date) + timedelta(days=1)).strftime("%Y%m%d")
                        if next_date > datetime.now().strftime("%Y%m%d"):
                            self.logger.info(f"✅ {etf_code} 数据已是最新")
                            continue
                        start_date = next_date
                        self.logger.info(f"📥 {etf_code} 增量更新 (从{latest_date})...")
                    else:
                        start_date = None
                        self.logger.info(f"📥 {etf_code} 首次下载...")

                # 下载数据
                df = self.download_etf_data(etf_code, start_date)

                if df is not None and not df.empty:
                    self.save_to_csv(df, etf_code)
                    self.stats["downloaded"].append(etf_code)
                    self.logger.info(f"✅ {etf_code} 下载成功 ({len(df)} 条)")
                else:
                    self.stats["failed"].append(etf_code)
                    self.logger.warning(f"⚠️  {etf_code} 无数据或下载失败")

                # 避免请求过快
                time.sleep(self.config.get("download_interval", 0.2))

            except Exception as e:
                self.logger.error(f"❌ {etf_code} 处理失败: {e}")
                self.stats["failed"].append(etf_code)
                self.stats["errors"].append(f"{etf_code}: {str(e)}")

        # 转换为Qlib格式
        if self.config.get("convert_to_qlib", True) and self.stats["downloaded"]:
            self.convert_to_qlib()

        # 打印摘要
        self.print_summary()

    def print_summary(self):
        """打印更新摘要"""
        duration = (datetime.now() - self.stats["start_time"]).total_seconds()

        self.logger.info("\n" + "=" * 60)
        self.logger.info("📊 更新摘要")
        self.logger.info("=" * 60)
        self.logger.info(f"总ETF数量: {len(self.stats['etf_list'])}")
        self.logger.info(f"成功更新: {len(self.stats['downloaded'])}")
        self.logger.info(f"失败: {len(self.stats['failed'])}")
        self.logger.info(f"耗时: {duration:.2f} 秒")

        if self.stats["failed"]:
            self.logger.info("\n❌ 失败列表:")
            for etf in self.stats["failed"][:10]:
                self.logger.info(f"  - {etf}")

        self.logger.info("=" * 60)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="ETF数据每日自动更新",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--config",
        type=str,
        help="配置文件路径"
    )

    parser.add_argument(
        "--full-download",
        action="store_true",
        help="全量下载历史数据"
    )

    parser.add_argument(
        "--data-dir",
        type=str,
        default="~/.qlib/qlib_data/cn_data/etf_raw",
        help="原始数据目录"
    )

    parser.add_argument(
        "--qlib-dir",
        type=str,
        default="~/.qlib/qlib_data/cn_data/etf",
        help="Qlib格式数据目录"
    )

    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()

    try:
        updater = ETFDailyUpdater(
            data_dir=args.data_dir,
            qlib_dir=args.qlib_dir,
            config_file=args.config
        )

        updater.run(full_download=args.full_download)

        sys.exit(0 if not updater.stats["failed"] else 1)

    except Exception as e:
        print(f"❌ 执行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
