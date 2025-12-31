#!/usr/bin/env python3
"""
A股全市场数据获取脚本

功能：
- 获取所有A股股票和指数的历史日线数据
- 自动频率控制，避免超过TuShare API限制
- 支持断点续传，可中断后继续获取
- 实时进度显示和统计信息
- 数据保存到Qlib可用格式

使用方式：
    # 设置TuShare Token环境变量
    export TUSHARE_TOKEN="your_token_here"

    # 运行脚本
    python fetch_all_a_stocks.py

    # 或指定参数
    python fetch_all_a_stocks.py --start-date 20200101 --batch-size 100
"""

import os
import sys
import time
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict

import pandas as pd
import numpy as np

# 添加Qlib路径
sys.path.insert(0, str(Path(__file__).parent))

from qlib.contrib.data.tushare import TuShareConfig, TuShareProvider
from qlib.contrib.data.tushare.api_client import TuShareAPIClient
from qlib.contrib.data.tushare.utils import TuShareCodeConverter


@dataclass
class FetchConfig:
    """数据获取配置"""
    # TuShare Token配置
    token: str = field(default_factory=lambda: os.getenv("TUSHARE_TOKEN", ""))

    # 数据范围配置
    start_date: str = "20000101"  # 开始日期（TuShare格式：YYYYMMDD）
    end_date: str = None  # 结束日期（默认今天）

    # 批量获取配置
    batch_size: int = 100  # 每批获取的股票数量
    max_parallel: int = 1  # 最大并行数（暂未实现）

    # 频率控制配置
    rate_limit: int = 180  # 每分钟请求数（略低于TuShare限制200）
    request_interval: float = 0.35  # 请求间隔（秒）

    # 重试配置
    max_retries: int = 3
    retry_delay: float = 2.0

    # 存储配置
    data_dir: str = field(default_factory=lambda: str(Path.home() / ".qlib" / "qlib_data" / "cn_data"))
    progress_db: str = field(default_factory=lambda: str(Path.home() / ".qlib" / "fetch_progress.db"))

    # 其他配置
    enable_cache: bool = True
    adjust_price: bool = True  # 是否复权
    skip_existing: bool = True  # 跳过已存在的数据

    def __post_init__(self):
        if self.end_date is None:
            self.end_date = datetime.now().strftime("%Y%m%d")


@dataclass
class FetchStats:
    """获取统计信息"""
    start_time: float = field(default_factory=time.time)
    total_stocks: int = 0
    total_indices: int = 0
    success_stocks: int = 0
    success_indices: int = 0
    failed_stocks: int = 0
    failed_indices: int = 0
    skipped_stocks: int = 0
    total_requests: int = 0
    total_data_points: int = 0
    failed_codes: Dict[str, str] = field(default_factory=dict)

    @property
    def elapsed_time(self) -> float:
        return time.time() - self.start_time

    @property
    def progress_percent(self) -> float:
        total = self.total_stocks + self.total_indices
        if total == 0:
            return 0.0
        completed = self.success_stocks + self.success_indices + self.failed_stocks + self.failed_indices
        return (completed / total) * 100


class ProgressManager:
    """进度管理器 - 使用SQLite保存进度，支持断点续传"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS fetch_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                type TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                status TEXT NOT NULL,
                data_count INTEGER DEFAULT 0,
                last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0
            )
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_code ON fetch_progress(code)
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_status ON fetch_progress(status)
        """)

        self.conn.commit()

    def save_progress(self, code: str, data_type: str, start_date: str,
                     end_date: str, status: str, data_count: int = 0,
                     error_message: str = None):
        """保存进度"""
        self.conn.execute("""
            INSERT OR REPLACE INTO fetch_progress
            (code, type, start_date, end_date, status, data_count, error_message, last_update)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (code, data_type, start_date, end_date, status, data_count, error_message))
        self.conn.commit()

    def get_progress(self, code: str, data_type: str,
                    start_date: str, end_date: str) -> Optional[dict]:
        """获取进度"""
        cursor = self.conn.execute("""
            SELECT * FROM fetch_progress
            WHERE code = ? AND type = ? AND start_date = ? AND end_date = ?
        """, (code, data_type, start_date, end_date))
        row = cursor.fetchone()
        if row:
            return {
                "id": row[0],
                "code": row[1],
                "type": row[2],
                "start_date": row[3],
                "end_date": row[4],
                "status": row[5],
                "data_count": row[6],
                "last_update": row[7],
                "error_message": row[8],
                "retry_count": row[9]
            }
        return None

    def get_pending_codes(self, data_type: str, start_date: str,
                         end_date: str) -> List[str]:
        """获取待处理的代码"""
        cursor = self.conn.execute("""
            SELECT DISTINCT code FROM fetch_progress
            WHERE type = ? AND start_date = ? AND end_date = ?
            AND status IN ('pending', 'failed')
            ORDER BY code
        """, (data_type, start_date, end_date))
        return [row[0] for row in cursor.fetchall()]

    def get_all_codes(self, data_type: str, start_date: str,
                     end_date: str) -> List[Tuple[str, str]]:
        """获取所有代码及其状态"""
        cursor = self.conn.execute("""
            SELECT code, status FROM fetch_progress
            WHERE type = ? AND start_date = ? AND end_date = ?
            ORDER BY code
        """, (data_type, start_date, end_date))
        return [(row[0], row[1]) for row in cursor.fetchall()]

    def get_stats(self, data_type: str, start_date: str,
                 end_date: str) -> Dict[str, int]:
        """获取统计信息"""
        cursor = self.conn.execute("""
            SELECT status, COUNT(*) as count
            FROM fetch_progress
            WHERE type = ? AND start_date = ? AND end_date = ?
            GROUP BY status
        """, (data_type, start_date, end_date))
        return {row[0]: row[1] for row in cursor.fetchall()}

    def reset_failed(self, data_type: str, start_date: str, end_date: str):
        """重置失败的任务"""
        self.conn.execute("""
            UPDATE fetch_progress
            SET status = 'pending', retry_count = 0, error_message = NULL
            WHERE type = ? AND start_date = ? AND end_date = ?
            AND status = 'failed'
        """, (data_type, start_date, end_date))
        self.conn.commit()

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()


class AStockFetcher:
    """A股数据获取器"""

    def __init__(self, config: FetchConfig):
        self.config = config
        self.stats = FetchStats()
        self.progress = None
        self.provider = None
        self.api_client = None

        # 创建数据目录
        self.data_dir = Path(config.data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 初始化进度管理器
        self.progress = ProgressManager(config.progress_db)

        # 打印配置信息
        self._print_config()

    def _print_config(self):
        """打印配置信息"""
        print("=" * 80)
        print("📊 A股全市场数据获取脚本")
        print("=" * 80)
        print(f"数据范围: {self.config.start_date} - {self.config.end_date}")
        print(f"批量大小: {self.config.batch_size}")
        print(f"频率限制: {self.config.rate_limit} 请求/分钟")
        print(f"请求间隔: {self.config.request_interval:.2f} 秒")
        print(f"数据目录: {self.config.data_dir}")
        print(f"进度数据库: {self.config.progress_db}")
        print(f"复权: {'是' if self.config.adjust_price else '否'}")
        print(f"跳过已存在: {'是' if self.config.skip_existing else '否'}")
        print("=" * 80)
        print()

    def _init_provider(self):
        """初始化TuShare提供者"""
        tushare_config = TuShareConfig(
            token=self.config.token,
            rate_limit=self.config.rate_limit,
            max_retries=self.config.max_retries,
            retry_delay=self.config.retry_delay,
            adjust_price=self.config.adjust_price,
            enable_cache=self.config.enable_cache,
            enable_api_logging=True,
            log_level="INFO"
        )

        self.provider = TuShareProvider(tushare_config)
        self.api_client = self.provider.api_client

        print("✅ TuShare提供者初始化完成")
        print()

    def get_all_stock_codes(self) -> List[Tuple[str, str]]:
        """获取所有A股股票代码"""
        print("📈 获取所有A股股票代码...")

        try:
            # 获取股票基本信息
            stock_basic = self.api_client.get_stock_basic(
                list_status="L",  # 只获取上市股票
                fields="ts_code,symbol,name,area,industry,market,list_date"
            )

            if stock_basic.empty:
                print("❌ 未获取到股票代码")
                return []

            # 处理字段映射后的列名（ts_code -> instrument 或保持 ts_code）
            code_col = "instrument" if "instrument" in stock_basic.columns else "ts_code"
            codes = [(row[code_col], row["name"]) for _, row in stock_basic.iterrows()]
            print(f"✅ 获取到 {len(codes)} 只A股股票")
            print()

            return codes

        except Exception as e:
            print(f"❌ 获取股票代码失败: {e}")
            return []

    def get_all_index_codes(self) -> List[Tuple[str, str]]:
        """获取所有指数代码"""
        print("📊 获取所有指数代码...")

        try:
            # 主要指数代码列表
            index_codes = [
                ("000001.SH", "上证指数"),
                ("399001.SZ", "深证成指"),
                ("399006.SZ", "创业板指"),
                ("000300.SH", "沪深300"),
                ("000016.SH", "上证50"),
                ("399905.SZ", "中证500"),
                ("000688.SH", "科创50"),
                ("000905.SH", "中证1000"),
            ]

            print(f"✅ 获取到 {len(index_codes)} 个主要指数")
            print()

            return index_codes

        except Exception as e:
            print(f"❌ 获取指数代码失败: {e}")
            return []

    def fetch_stock_data(self, code: str, name: str) -> bool:
        """获取单只股票数据"""
        try:
            # 转换为Qlib格式
            qlib_code = TuShareCodeConverter.to_qlib_format(code)

            # 检查是否已存在
            if self.config.skip_existing:
                stock_file = self.data_dir / "stock_data" / f"{qlib_code}.csv"
                if stock_file.exists():
                    existing_df = pd.read_csv(stock_file, parse_dates=["date"])
                    if not existing_df.empty:
                        last_date = existing_df["date"].max().strftime("%Y%m%d")
                        if last_date >= self.config.end_date:
                            # 数据已经是最新的
                            self.stats.skipped_stocks += 1
                            self.progress.save_progress(
                                code, "stock", self.config.start_date, self.config.end_date,
                                "skipped", len(existing_df)
                            )
                            return True

            # 获取日线数据
            df = self.api_client.get_daily_data(
                ts_code=code,
                start_date=self.config.start_date,
                end_date=self.config.end_date,
                adj="qfq" if self.config.adjust_price else None
            )

            if df.empty:
                # 没有数据（可能是新股）
                self.progress.save_progress(
                    code, "stock", self.config.start_date, self.config.end_date,
                    "no_data", 0, "No data available"
                )
                return False

            # 保存数据
            stock_file = self.data_dir / "stock_data" / f"{qlib_code}.csv"
            stock_file.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(stock_file, index=False)

            self.stats.success_stocks += 1
            self.stats.total_data_points += len(df)
            self.stats.total_requests += 1

            self.progress.save_progress(
                code, "stock", self.config.start_date, self.config.end_date,
                "success", len(df)
            )

            return True

        except Exception as e:
            error_msg = str(e)
            self.stats.failed_codes[code] = error_msg
            self.stats.failed_stocks += 1

            self.progress.save_progress(
                code, "stock", self.config.start_date, self.config.end_date,
                "failed", 0, error_msg
            )

            print(f"  ❌ 获取股票数据失败 {code} ({name}): {error_msg}")
            return False

    def fetch_index_data(self, code: str, name: str) -> bool:
        """获取单个指数数据"""
        try:
            # 转换为Qlib格式
            qlib_code = TuShareCodeConverter.to_qlib_format(code)

            # 检查是否已存在
            if self.config.skip_existing:
                index_file = self.data_dir / "index_data" / f"{qlib_code}.csv"
                if index_file.exists():
                    existing_df = pd.read_csv(index_file, parse_dates=["date"])
                    if not existing_df.empty:
                        last_date = existing_df["date"].max().strftime("%Y%m%d")
                        if last_date >= self.config.end_date:
                            # 数据已经是最新的
                            self.stats.skipped_stocks += 1
                            self.progress.save_progress(
                                code, "index", self.config.start_date, self.config.end_date,
                                "skipped", len(existing_df)
                            )
                            return True

            # 获取指数日线数据
            df = self.api_client.get_index_daily(
                ts_code=code,
                start_date=self.config.start_date,
                end_date=self.config.end_date
            )

            if df.empty:
                # 没有数据
                self.progress.save_progress(
                    code, "index", self.config.start_date, self.config.end_date,
                    "no_data", 0, "No data available"
                )
                return False

            # 保存数据
            index_file = self.data_dir / "index_data" / f"{qlib_code}.csv"
            index_file.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(index_file, index=False)

            self.stats.success_indices += 1
            self.stats.total_data_points += len(df)
            self.stats.total_requests += 1

            self.progress.save_progress(
                code, "index", self.config.start_date, self.config.end_date,
                "success", len(df)
            )

            return True

        except Exception as e:
            error_msg = str(e)
            self.stats.failed_codes[code] = error_msg
            self.stats.failed_indices += 1

            self.progress.save_progress(
                code, "index", self.config.start_date, self.config.end_date,
                "failed", 0, error_msg
            )

            print(f"  ❌ 获取指数数据失败 {code} ({name}): {error_msg}")
            return False

    def fetch_stocks_batch(self, codes: List[Tuple[str, str]], batch_idx: int, total_batches: int):
        """批量获取股票数据"""
        batch_size = len(codes)
        print(f"📦 批次 {batch_idx}/{total_batches} ({batch_size} 只股票)")

        for i, (code, name) in enumerate(codes, 1):
            # 显示进度
            print(f"  [{i}/{batch_size}] {code} {name}...", end="\r")

            # 频率控制
            time.sleep(self.config.request_interval)

            # 获取数据
            success = self.fetch_stock_data(code, name)

            if success:
                print(f"  [{i}/{batch_size}] ✅ {code} {name}")

            # 定期显示统计信息
            if i % 10 == 0:
                self._print_progress()

    def fetch_indices_batch(self, codes: List[Tuple[str, str]]):
        """批量获取指数数据"""
        print(f"📊 获取指数数据 ({len(codes)} 个指数)")

        for i, (code, name) in enumerate(codes, 1):
            # 显示进度
            print(f"  [{i}/{len(codes)}] {code} {name}...", end="\r")

            # 频率控制
            time.sleep(self.config.request_interval)

            # 获取数据
            success = self.fetch_index_data(code, name)

            if success:
                print(f"  [{i}/{len(codes)}] ✅ {code} {name}")

        self._print_progress()

    def _print_progress(self):
        """打印进度信息"""
        elapsed = self.stats.elapsed_time
        success = self.stats.success_stocks + self.stats.success_indices
        failed = self.stats.failed_stocks + self.stats.failed_indices
        skipped = self.stats.skipped_stocks
        total = self.stats.total_stocks + self.stats.total_indices

        print(f"    进度: {success}/{total} ({self.stats.progress_percent:.1f}%) | "
              f"成功: {success} | 失败: {failed} | 跳过: {skipped} | "
              f"耗时: {elapsed:.0f}秒 | 数据点: {self.stats.total_data_points:,}")

    def _print_final_stats(self):
        """打印最终统计信息"""
        elapsed = self.stats.elapsed_time
        success_stocks = self.stats.success_stocks
        success_indices = self.stats.success_indices
        failed_stocks = self.stats.failed_stocks
        failed_indices = self.stats.failed_indices
        skipped_stocks = self.stats.skipped_stocks
        total_stocks = self.stats.total_stocks
        total_indices = self.stats.total_indices

        print()
        print("=" * 80)
        print("📊 数据获取完成！")
        print("=" * 80)
        print(f"股票统计:")
        print(f"  总数: {total_stocks}")
        print(f"  成功: {success_stocks}")
        print(f"  失败: {failed_stocks}")
        print(f"  跳过: {skipped_stocks}")
        print()
        print(f"指数统计:")
        print(f"  总数: {total_indices}")
        print(f"  成功: {success_indices}")
        print(f"  失败: {failed_indices}")
        print()
        print(f"数据统计:")
        print(f"  总数据点: {self.stats.total_data_points:,}")
        print(f"  总请求数: {self.stats.total_requests}")
        print(f"  总耗时: {elapsed:.0f}秒 ({elapsed/60:.1f}分钟)")
        print()
        print(f"数据保存位置: {self.data_dir}")
        print("=" * 80)

        if self.stats.failed_codes:
            print()
            print(f"⚠️ 失败的股票代码 ({len(self.stats.failed_codes)}):")
            for code, error in list(self.stats.failed_codes.items())[:10]:
                print(f"  {code}: {error}")
            if len(self.stats.failed_codes) > 10:
                print(f"  ... 还有 {len(self.stats.failed_codes) - 10} 个失败")

    def run(self, resume: bool = False):
        """运行数据获取"""
        try:
            # 初始化提供者
            self._init_provider()

            # 获取所有股票代码
            stock_codes = self.get_all_stock_codes()
            if not stock_codes:
                print("❌ 未获取到股票代码，退出")
                return

            self.stats.total_stocks = len(stock_codes)

            # 获取所有指数代码
            index_codes = self.get_all_index_codes()
            self.stats.total_indices = len(index_codes)

            # 初始化进度记录
            if not resume:
                # 清除旧的进度记录
                self.progress.conn.execute("""
                    DELETE FROM fetch_progress
                    WHERE start_date = ? AND end_date = ?
                """, (self.config.start_date, self.config.end_date))
                self.progress.conn.commit()

                # 添加新的进度记录
                for code, name in stock_codes:
                    self.progress.save_progress(
                        code, "stock", self.config.start_date, self.config.end_date,
                        "pending", 0
                    )

                for code, name in index_codes:
                    self.progress.save_progress(
                        code, "index", self.config.start_date, self.config.end_date,
                        "pending", 0
                    )
            else:
                # 从进度恢复
                pending_stocks = self.progress.get_pending_codes(
                    "stock", self.config.start_date, self.config.end_date
                )
                stock_codes = [(c, "") for c in pending_stocks if c in [sc[0] for sc in stock_codes]]

                print(f"🔄 从断点恢复，剩余 {len(stock_codes)} 只股票待获取")
                print()

            # 分批获取股票数据
            batch_size = self.config.batch_size
            total_batches = (len(stock_codes) + batch_size - 1) // batch_size

            for batch_idx in range(1, total_batches + 1):
                start_idx = (batch_idx - 1) * batch_size
                end_idx = min(start_idx + batch_size, len(stock_codes))
                batch_codes = stock_codes[start_idx:end_idx]

                self.fetch_stocks_batch(batch_codes, batch_idx, total_batches)

                # 保存统计数据
                self._save_stats()

            # 获取指数数据
            if index_codes:
                self.fetch_indices_batch(index_codes)

            # 打印最终统计
            self._print_final_stats()

        except KeyboardInterrupt:
            print()
            print()
            print("⚠️ 用户中断，数据获取已暂停")
            print(f"💾 进度已保存，可以使用 --resume 参数继续获取")
            print()
            self._print_progress()
            self._save_stats()

        except Exception as e:
            print()
            print(f"❌ 发生错误: {e}")
            import traceback
            traceback.print_exc()

        finally:
            # 清理资源
            if self.provider:
                self.provider.close()
            if self.progress:
                self.progress.close()

    def _save_stats(self):
        """保存统计数据到文件"""
        stats_file = self.data_dir / "fetch_stats.json"
        stats_data = {
            "start_date": self.config.start_date,
            "end_date": self.config.end_date,
            "total_stocks": self.stats.total_stocks,
            "total_indices": self.stats.total_indices,
            "success_stocks": self.stats.success_stocks,
            "success_indices": self.stats.success_indices,
            "failed_stocks": self.stats.failed_stocks,
            "failed_indices": self.stats.failed_indices,
            "skipped_stocks": self.stats.skipped_stocks,
            "total_data_points": self.stats.total_data_points,
            "total_requests": self.stats.total_requests,
            "last_update": datetime.now().isoformat()
        }
        with open(stats_file, "w", encoding="utf-8") as f:
            json.dump(stats_data, f, indent=2, ensure_ascii=False)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="A股全市场数据获取脚本")
    parser.add_argument("--token", type=str, default=os.getenv("TUSHARE_TOKEN", ""),
                       help="TuShare Token（默认从环境变量TUSHARE_TOKEN读取）")
    parser.add_argument("--start-date", type=str, default="20000101",
                       help="开始日期（格式：YYYYMMDD，默认：20000101）")
    parser.add_argument("--end-date", type=str, default=None,
                       help="结束日期（格式：YYYYMMDD，默认：今天）")
    parser.add_argument("--batch-size", type=int, default=100,
                       help="批量大小（默认：100）")
    parser.add_argument("--rate-limit", type=int, default=180,
                       help="频率限制（请求/分钟，默认：180）")
    parser.add_argument("--data-dir", type=str,
                       default=str(Path.home() / ".qlib" / "qlib_data" / "cn_data"),
                       help="数据保存目录")
    parser.add_argument("--resume", action="store_true",
                       help="从断点恢复")
    parser.add_argument("--no-adjust", action="store_true",
                       help="不复权")
    parser.add_argument("--no-skip", action="store_true",
                       help="不跳过已存在的数据")

    args = parser.parse_args()

    # 检查Token
    if not args.token:
        print("❌ 错误: 未设置TuShare Token")
        print("请通过以下方式之一设置Token：")
        print("  1. 环境变量: export TUSHARE_TOKEN='your_token'")
        print("  2. 命令行参数: --token your_token")
        sys.exit(1)

    # 创建配置
    config = FetchConfig(
        token=args.token,
        start_date=args.start_date,
        end_date=args.end_date,
        batch_size=args.batch_size,
        rate_limit=args.rate_limit,
        data_dir=args.data_dir,
        adjust_price=not args.no_adjust,
        skip_existing=not args.no_skip
    )

    # 创建获取器并运行
    fetcher = AStockFetcher(config)
    fetcher.run(resume=args.resume)


if __name__ == "__main__":
    main()
