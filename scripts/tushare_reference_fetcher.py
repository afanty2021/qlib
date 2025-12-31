#!/usr/bin/env python3
"""
TuShare 参考数据获取器

使用 TuShare API 获取参考数据，替代 Dolt 数据库进行数据质量比对。

优势：
- 无需下载大型 Dolt 数据库（数GB）
- 直接获取最新数据
- 速度快，可靠性高

使用方法：
    python scripts/tushare_reference_fetcher.py --symbols 000001.SZ,000002.SZ --start-date 20240101 --end-date 20241231
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import warnings
import argparse

import pandas as pd
import numpy as np

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from qlib.contrib.data.tushare.api_client import TuShareAPIClient
from qlib.contrib.data.tushare.config import TuShareConfig

warnings.filterwarnings('ignore')


class TuShareReferenceFetcher:
    """
    TuShare 参考数据获取器

    使用 TuShare API 获取参考数据用于数据质量比对。
    """

    def __init__(self):
        """初始化 TuShare 客户端"""
        self.logger = self._setup_logger()

        # 检查 Token
        token = os.getenv("TUSHARE_TOKEN")
        if not token:
            raise ValueError(
                "❌ 未设置 TUSHARE_TOKEN 环境变量\n"
                "请设置: export TUSHARE_TOKEN='your_token_here'"
            )

        # 初始化客户端
        config = TuShareConfig(token=token)
        self.client = TuShareAPIClient(config)

    def _setup_logger(self) -> logging.Logger:
        """设置日志"""
        logger = logging.getLogger("TuShareReferenceFetcher")
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def get_reference_data(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        chunk_size: int = 100
    ) -> pd.DataFrame:
        """
        获取参考数据

        Args:
            symbols: 股票代码列表
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            chunk_size: 每次请求的股票数量

        Returns:
            参考数据 DataFrame
        """
        self.logger.info(f"📡 从 TuShare 获取参考数据...")
        self.logger.info(f"   股票数量: {len(symbols)}")
        self.logger.info(f"   日期范围: {start_date} -> {end_date}")

        all_data = []

        # 分批获取数据
        for i in range(0, len(symbols), chunk_size):
            chunk_symbols = symbols[i:i + chunk_size]
            self.logger.info(f"   正在获取第 {i//chunk_size + 1} 批 ({len(chunk_symbols)} 只股票)...")

            for symbol in chunk_symbols:
                try:
                    # 调用 TuShare API
                    data = self.client._make_request("daily", {
                        "ts_code": symbol,
                        "start_date": start_date,
                        "end_date": end_date
                    })

                    if data and "items" in data and len(data["items"]) > 0:
                        df = pd.DataFrame(data["items"], columns=data["fields"])

                        # 字段映射到统一格式
                        df = df.rename(columns={
                            "ts_code": "symbol",
                            "trade_date": "tradedate"
                        })

                        # 选择需要的字段
                        df = df[["tradedate", "symbol", "open", "high", "low", "close", "vol", "amount"]]
                        df = df.rename(columns={"vol": "volume"})

                        all_data.append(df)

                except Exception as e:
                    self.logger.warning(f"   ⚠️  {symbol} 获取失败: {e}")
                    continue

        if all_data:
            result_df = pd.concat(all_data, ignore_index=True)
            result_df = result_df.sort_values(["tradedate", "symbol"])
            self.logger.info(f"✅ 获取到 {len(result_df):,} 条参考数据")
            return result_df
        else:
            self.logger.error("❌ 未获取到任何数据")
            return pd.DataFrame()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="TuShare 参考数据获取器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 获取单只股票数据
  python scripts/tushare_reference_fetcher.py \\
      --symbols 000001.SZ \\
      --start-date 20240101 \\
      --end-date 20241231 \\
      --output reference_data.csv

  # 获取多只股票数据
  python scripts/tushare_reference_fetcher.py \\
      --symbols 000001.SZ,000002.SZ,600000.SH \\
      --start-date 20240101 \\
      --end-date 20241231 \\
      --output reference_data.csv

  # 使用沪深300成分股
  python scripts/tushare_reference_fetcher.py \\
      --use-csi300 \\
      --start-date 20240101 \\
      --end-date 20241231 \\
      --output csi300_reference.csv
        """
    )

    parser.add_argument(
        "--symbols",
        type=str,
        help="股票代码列表（逗号分隔），例如: 000001.SZ,000002.SZ"
    )

    parser.add_argument(
        "--use-csi300",
        action="store_true",
        help="使用沪深300成分股"
    )

    parser.add_argument(
        "--use-csi500",
        action="store_true",
        help="使用中证500成分股"
    )

    parser.add_argument(
        "--start-date",
        type=str,
        required=True,
        help="开始日期 (YYYYMMDD)"
    )

    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="结束日期 (YYYYMMDD)，默认为今天"
    )

    parser.add_argument(
        "--output",
        type=str,
        default="reference_data.csv",
        help="输出文件路径 (默认: reference_data.csv)"
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=100,
        help="每批请求的股票数量 (默认: 100)"
    )

    args = parser.parse_args()

    # 检查参数
    if not args.symbols and not args.use_csi300 and not args.use_csi500:
        parser.error("必须指定 --symbols, --use-csi300 或 --use-csi500")

    # 设置结束日期
    if args.end_date is None:
        args.end_date = datetime.now().strftime("%Y%m%d")

    print("\n" + "=" * 60)
    print("TuShare 参考数据获取器")
    print("=" * 60)

    try:
        # 创建获取器
        fetcher = TuShareReferenceFetcher()

        # 确定股票列表
        symbols = []
        if args.symbols:
            symbols = [s.strip() for s in args.symbols.split(",")]

        elif args.use_csi300 or args.use_csi500:
            # 获取指数成分股
            index_code = "000300.SH" if args.use_csi300 else "000905.SH"
            index_name = "沪深300" if args.use_csi300 else "中证500"

            print(f"\n📊 获取 {index_name} 成分股...")

            data = fetcher.client._make_request("index_weight", {
                "index_code": index_code,
                "start_date": args.end_date,
                "end_date": args.end_date
            })

            if data and "items" in data:
                df = pd.DataFrame(data["items"], columns=data["fields"])
                symbols = df["con_code"].unique().tolist()

                # 转换为 TuShare 格式
                formatted_symbols = []
                for s in symbols:
                    if s.endswith(".SH") or s.endswith(".SZ"):
                        formatted_symbols.append(s)
                    elif s.startswith("6"):
                        formatted_symbols.append(f"{s}.SH")
                    else:
                        formatted_symbols.append(f"{s}.SZ")

                symbols = formatted_symbols

                print(f"✅ 获取到 {len(symbols)} 只成分股")
            else:
                print(f"❌ 获取 {index_name} 成分股失败")
                return 1

        # 获取参考数据
        reference_df = fetcher.get_reference_data(
            symbols=symbols,
            start_date=args.start_date,
            end_date=args.end_date,
            chunk_size=args.chunk_size
        )

        if reference_df.empty:
            print("\n❌ 未获取到任何数据")
            return 1

        # 保存数据
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        reference_df.to_csv(output_path, index=False)

        print(f"\n✅ 参考数据已保存: {output_path}")
        print(f"   总记录数: {len(reference_df):,}")
        print(f"   日期范围: {reference_df['tradedate'].min()} -> {reference_df['tradedate'].max()}")
        print(f"   股票数量: {reference_df['symbol'].nunique()}")

        return 0

    except ValueError as e:
        print(f"\n❌ {e}")
        return 1
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
