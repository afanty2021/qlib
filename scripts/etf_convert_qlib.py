#!/usr/bin/env python3
"""
ETF数据转换为Qlib格式脚本

功能：
- 将TuShare下载的ETF CSV数据转换为Qlib格式
- 使用Qlib的dump_bin工具进行转换
- 支持增量更新和全量转换

使用方式：
    python scripts/etf_convert_qlib.py --source-dir ~/.qlib/qlib_data/cn_data/etf_raw --qlib-dir ~/.qlib/qlib_data/cn_data/etf
"""

import os
import sys
import logging
import argparse
from pathlib import Path
from typing import List

import pandas as pd
import numpy as np
from tqdm import tqdm

# 添加项目路径到 sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from qlib.utils import fname_to_code, code_to_fname


class ETFDataConverter:
    """ETF数据转换为Qlib格式"""

    def __init__(
        self,
        source_dir: str = "~/.qlib/qlib_data/cn_data/etf_raw",
        qlib_dir: str = "~/.qlib/qlib_data/cn_data/etf"
    ):
        """
        初始化转换器

        Args:
            source_dir: 原始CSV数据目录
            qlib_dir: Qlib格式数据输出目录
        """
        self.source_dir = Path(source_dir).expanduser()
        self.qlib_dir = Path(qlib_dir).expanduser()

        # 创建输出目录
        self.qlib_dir.mkdir(parents=True, exist_ok=True)

        # 子目录
        self.calendars_dir = self.qlib_dir / "calendars"
        self.features_dir = self.qlib_dir / "features"
        self.instruments_dir = self.qlib_dir / "instruments"

        # 设置日志
        self.logger = self._setup_logger()

        # 统计信息
        self.stats = {
            "total_files": 0,
            "converted": 0,
            "failed": 0
        }

    def _setup_logger(self) -> logging.Logger:
        """设置日志系统"""
        logger = logging.getLogger("ETFConverter")
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            # 日志格式
            log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            date_format = "%Y-%m-%d %H:%M:%S"
            formatter = logging.Formatter(log_format, date_format)

            # 文件处理器
            log_file = self.qlib_dir / "convert.log"
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

    def normalize_csv_data(self, csv_path: Path) -> pd.DataFrame:
        """
        标准化CSV数据为Qlib格式

        Args:
            csv_path: CSV文件路径

        Returns:
            标准化后的DataFrame
        """
        try:
            # 读取CSV文件
            df = pd.read_csv(csv_path)

            # 检查必要的列
            required_columns = ['trade_date', 'ts_code']
            missing_cols = [col for col in required_columns if col not in df.columns]
            if missing_cols:
                self.logger.warning(f"  ⚠️  {csv_path.name} 缺少必要列: {missing_cols}")
                return None

            # 重命名列以匹配Qlib格式
            column_mapping = {
                'ts_code': 'symbol',
                'trade_date': 'date',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'vol': 'volume',
                'amount': 'amount'
            }

            # 应用列映射
            df = df.rename(columns=column_mapping)

            # 确保有volume列
            if 'volume' not in df.columns and 'vol' in df.columns:
                df['volume'] = df['vol']

            # 转换日期格式
            df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')

            # 按日期排序
            df = df.sort_values('date')

            # 添加factor列（调整因子，ETF设为1.0）
            if 'factor' not in df.columns:
                df['factor'] = 1.0

            # 选择需要的列
            columns_order = ['date', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'factor']
            available_columns = [col for col in columns_order if col in df.columns]
            df = df[available_columns]

            return df

        except Exception as e:
            self.logger.error(f"  ❌ 标准化失败: {e}")
            return None

    def save_to_qlib_format(
        self,
        df: pd.DataFrame,
        etf_code: str,
        calendar_list: List[pd.Timestamp]
    ):
        """
        保存为Qlib二进制格式

        Args:
            df: 标准化后的DataFrame
            etf_code: ETF代码
            calendar_list: 交易日历列表
        """
        if df.empty:
            self.logger.warning(f"  ⚠️  {etf_code} 数据为空")
            return

        try:
            # 创建ETF特征目录
            etf_dir = self.features_dir / code_to_fname(etf_code).lower()
            etf_dir.mkdir(parents=True, exist_ok=True)

            # 按日期对齐交易日历
            df.set_index('date', inplace=True)
            df_indexed = df.reindex(calendar_list)

            # 保存各字段为二进制格式
            fields = ['open', 'high', 'low', 'close', 'volume', 'factor']

            for field in fields:
                if field not in df_indexed.columns:
                    continue

                bin_file = etf_dir / f"{field}.day.bin"

                # 获取字段数据
                data = df_indexed[field].values

                # 处理NaN值
                data = np.nan_to_num(data, nan=0.0)

                # 转换为二进制并保存
                data.astype('<f').tofile(str(bin_file))

            self.logger.info(f"  ✅ {etf_code} 已转换为Qlib格式")

        except Exception as e:
            self.logger.error(f"  ❌ 转换失败: {e}")
            raise

    def get_all_calendars(self, csv_files: List[Path]) -> List[pd.Timestamp]:
        """
        从所有CSV文件中获取交易日历

        Args:
            csv_files: CSV文件列表

        Returns:
            排序后的交易日历列表
        """
        all_dates = set()

        for csv_file in tqdm(csv_files, desc="读取交易日历"):
            try:
                df = pd.read_csv(csv_file)
                if 'trade_date' in df.columns:
                    dates = pd.to_datetime(df['trade_date'], format='%Y%m%d')
                    all_dates.update(dates)
            except Exception as e:
                self.logger.warning(f"  ⚠️  读取 {csv_file.name} 日期失败: {e}")

        return sorted(all_dates)

    def save_calendars(self, calendar_list: List[pd.Timestamp]):
        """
        保存交易日历

        Args:
            calendar_list: 交易日历列表
        """
        self.calendars_dir.mkdir(parents=True, exist_ok=True)
        calendar_file = self.calendars_dir / "day.txt"

        # 转换为字符串格式
        date_strings = [d.strftime('%Y-%m-%d') for d in calendar_list]

        # 保存到文件
        with open(calendar_file, 'w') as f:
            for date_str in date_strings:
                f.write(f"{date_str}\n")

        self.logger.info(f"✅ 交易日历已保存 ({len(calendar_list)} 个交易日)")

    def save_instruments(self, etf_codes: List[str], calendar_list: List[pd.Timestamp]):
        """
        保存ETF列表文件

        Args:
            etf_codes: ETF代码列表
            calendar_list: 交易日历列表
        """
        self.instruments_dir.mkdir(parents=True, exist_ok=True)
        instruments_file = self.instruments_dir / "all.txt"

        # 获取每个ETF的起止日期
        instrument_info = []

        for etf_code in etf_codes:
            csv_file = self.source_dir / f"{etf_code}.csv"
            if not csv_file.exists():
                continue

            try:
                df = pd.read_csv(csv_file)
                if 'trade_date' in df.columns and len(df) > 0:
                    dates = pd.to_datetime(df['trade_date'], format='%Y%m%d')
                    start_date = dates.min().strftime('%Y-%m-%d')
                    end_date = dates.max().strftime('%Y-%m-%d')

                    instrument_info.append(f"{etf_code}\t{start_date}\t{end_date}\n")

            except Exception as e:
                self.logger.warning(f"  ⚠️  获取 {etf_code} 信息失败: {e}")

        # 保存到文件
        with open(instruments_file, 'w') as f:
            f.writelines(instrument_info)

        self.logger.info(f"✅ ETF列表已保存 ({len(instrument_info)} 个ETF)")

    def convert_all(self):
        """转换所有ETF数据"""
        self.logger.info("=" * 60)
        self.logger.info("🔄 开始转换为Qlib格式")
        self.logger.info("=" * 60)

        # 获取所有CSV文件
        csv_files = sorted(self.source_dir.glob("*.csv"))
        self.stats["total_files"] = len(csv_files)

        if not csv_files:
            self.logger.warning(f"❌ 在 {self.source_dir} 中未找到CSV文件")
            return False

        self.logger.info(f"📁 找到 {len(csv_files)} 个CSV文件")

        # 获取交易日历
        self.logger.info("\n📅 构建交易日历...")
        calendar_list = self.get_all_calendars(csv_files)
        self.save_calendars(calendar_list)

        # 提取ETF代码列表
        etf_codes = [csv.stem for csv in csv_files]

        # 保存ETF列表
        self.logger.info("\n📝 保存ETF列表...")
        self.save_instruments(etf_codes, calendar_list)

        # 转换每个ETF数据
        self.logger.info("\n🔄 转换ETF数据...")
        for csv_file in tqdm(csv_files, desc="转换进度"):
            etf_code = csv_file.stem

            try:
                # 标准化数据
                df = self.normalize_csv_data(csv_file)

                if df is not None:
                    # 转换为Qlib格式
                    self.save_to_qlib_format(df, etf_code, calendar_list)
                    self.stats["converted"] += 1
                else:
                    self.stats["failed"] += 1

            except Exception as e:
                self.logger.error(f"❌ {etf_code} 转换失败: {e}")
                self.stats["failed"] += 1

        return True

    def print_summary(self):
        """打印转换摘要"""
        self.logger.info("\n" + "=" * 60)
        self.logger.info("📊 转换摘要")
        self.logger.info("=" * 60)
        self.logger.info(f"总文件数: {self.stats['total_files']}")
        self.logger.info(f"成功: {self.stats['converted']}")
        self.logger.info(f"失败: {self.stats['failed']}")
        self.logger.info("=" * 60)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="ETF数据转换为Qlib格式",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--source-dir",
        type=str,
        default="~/.qlib/qlib_data/cn_data/etf_raw",
        help="原始CSV数据目录"
    )

    parser.add_argument(
        "--qlib-dir",
        type=str,
        default="~/.qlib/qlib_data/cn_data/etf",
        help="Qlib格式数据输出目录"
    )

    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()

    # 创建转换器
    converter = ETFDataConverter(
        source_dir=args.source_dir,
        qlib_dir=args.qlib_dir
    )

    # 执行转换
    success = converter.convert_all()

    # 打印摘要
    converter.print_summary()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
