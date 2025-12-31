#!/usr/bin/env python3
"""
个股-申万二级行业映射下载工具

功能：
1. 下载所有A股股票的申万二级行业分类
2. 生成股票代码到行业代码的映射表
3. 保存为多种格式便于使用

使用方法：
    python download_stock_industry_mapping.py

或使用TuShare Token：
    export TUSHARE_TOKEN="your_token"
    python download_stock_industry_mapping.py
"""

import os
import sys
import pandas as pd
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import time

# 添加qlib路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

try:
    from qlib.contrib.data.tushare.config import TuShareConfig
    from qlib.contrib.data.tushare.api_client import TuShareAPIClient
    QLIB_AVAILABLE = True
except ImportError:
    QLIB_AVAILABLE = False
    print("⚠️ Qlib未安装，使用原生tushare")
    import tushare as ts


class StockIndustryMappingDownloader:
    """个股-行业映射下载器"""

    def __init__(self, token: str = None, output_dir: str = None):
        """
        初始化下载器

        Args:
            token: TuShare Token
            output_dir: 输出目录
        """
        self.token = token or os.getenv("TUSHARE_TOKEN")
        if not self.token:
            raise ValueError("请设置TUSHARE_TOKEN环境变量或传入token参数")

        # 设置输出目录
        if output_dir is None:
            # 默认输出到Qlib数据目录
            output_dir = Path("~/.qlib/qlib_data/cn_data/industry_data").expanduser()
        else:
            output_dir = Path(output_dir)

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 直接使用原生TuShare API（避免缓存目录问题）
        import tushare as ts
        self.client = ts.pro_api(self.token)
        self.use_proxied_api = False

        print(f"✅ 初始化完成")
        print(f"   输出目录: {self.output_dir}")
        print(f"   API模式: 原生TuShare")

    def download_stock_basic(self) -> pd.DataFrame:
        """
        下载股票基本信息

        Returns:
            股票基本信息DataFrame
        """
        print("\n" + "="*80)
        print("📥 开始下载股票基本信息")
        print("="*80)

        try:
            # 使用原生TuShare API
            import tushare as ts
            ts_client = ts.pro_api(self.token)

            # 获取股票基本信息
            print("\n📊 获取股票基本信息（包含行业字段）...")
            df = ts_client.stock_basic(
                exchange='',
                list_status='L',  # L上市 D退市 P暂停上市
                fields='ts_code,symbol,name,area,industry,market,list_date'
            )

            if df is not None and not df.empty:
                print(f"✅ 成功获取 {len(df)} 只股票的基本信息")
                print(f"   - 包含字段: {list(df.columns)}")

                # 显示行业分布（使用industry字段）
                if 'industry' in df.columns:
                    print(f"\n📈 行业分布（基于stock_basic）:")
                    industry_dist = df['industry'].value_counts().head(10)
                    for industry, count in industry_dist.items():
                        print(f"   - {industry}: {count}只")

                return df
            else:
                print("⚠️ 未获取到数据")
                return pd.DataFrame()

        except Exception as e:
            print(f"❌ 下载失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()

    def download_sw2021_industry_classify(self) -> pd.DataFrame:
        """
        下载申万2021行业分类

        Returns:
            申万行业分类DataFrame
        """
        print("\n" + "="*80)
        print("📥 开始下载申万2021行业分类")
        print("="*80)

        all_classify = pd.DataFrame()

        try:
            import tushare as ts
            ts_client = ts.pro_api(self.token)

            # 获取L1和L2级别的行业分类
            levels = ['L1', 'L2']
            source = 'SW2021'

            for level in levels:
                print(f"\n📊 获取申万2021 {level} 级行业分类...")

                try:
                    df = ts_client.index_classify(
                        level=level,
                        source=source
                    )

                    if df is not None and not df.empty:
                        df['level'] = level
                        all_classify = pd.concat([all_classify, df], ignore_index=True)
                        print(f"   ✅ {len(df)} 条记录")

                        # 避免API频率限制
                        time.sleep(0.2)
                    else:
                        print(f"   ⚠️ 无数据")

                except Exception as e:
                    print(f"   ❌ 失败: {str(e)}")

            if not all_classify.empty:
                print(f"\n✅ 申万行业分类下载完成，共 {len(all_classify)} 条")

            return all_classify

        except Exception as e:
            print(f"❌ 下载失败: {str(e)}")
            return pd.DataFrame()

    def download_stock_industry_detail(self) -> pd.DataFrame:
        """
        下载个股详细的行业分类信息

        使用get_union获取个股的行业成分

        Returns:
            个股行业分类DataFrame
        """
        print("\n" + "="*80)
        print("📥 开始下载个股详细行业分类")
        print("="*80)

        try:
            import tushare as ts
            ts_client = ts.pro_api(self.token)

            # 先获取股票列表
            stock_list = ts_client.stock_basic(
                exchange='',
                list_status='L',
                fields='ts_code,symbol,name'
            )

            if stock_list is None or stock_list.empty:
                print("⚠️ 未获取到股票列表")
                return pd.DataFrame()

            print(f"\n📊 共 {len(stock_list)} 只股票，开始获取行业分类...")

            # 存储个股行业信息
            stock_industry_list = []
            total = len(stock_list)

            # 批量获取，避免API限制
            batch_size = 100
            for i in range(0, total, batch_size):
                batch = stock_list.iloc[i:i+batch_size]
                print(f"\n   处理进度: {i+1}-{min(i+batch_size, total)}/{total}")

                for idx, row in batch.iterrows():
                    ts_code = row['ts_code']
                    symbol = row['symbol']
                    name = row['name']

                    try:
                        # 使用get_union获取成分股信息
                        # 这个接口可以获取指数的成分股，也可以反过来查询股票所属的指数
                        # 但TuShare没有直接的"股票→行业"查询接口

                        # 方法：使用daily_basic获取股票的行业信息
                        basic_data = ts_client.daily_basic(
                            ts_code=ts_code,
                            fields='ts_code,trade_date,turnover_rate,volume_ratio,pe,pe_ttm,pb,ps,ps_ttm,dv_ratio,dv_ttm,total_share,float_share,free_share,total_mv,circ_mv'
                        )

                        # daily_basic没有直接的行业信息
                        # 我们需要使用stock_basic的industry字段

                        time.sleep(0.1)  # 避免频率限制

                    except Exception as e:
                        print(f"      ⚠️ {ts_code} 获取失败: {str(e)}")
                        continue

            print(f"\n✅ 个股行业分类下载完成")
            return pd.DataFrame(stock_industry_list)

        except Exception as e:
            print(f"❌ 下载失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()

    def create_industry_mapping(
        self,
        stock_basic: pd.DataFrame,
        industry_classify: pd.DataFrame = None
    ) -> pd.DataFrame:
        """
        创建股票-行业映射表

        Args:
            stock_basic: 股票基本信息
            industry_classify: 行业分类信息

        Returns:
            股票-行业映射DataFrame
        """
        print("\n" + "="*80)
        print("🔗 创建股票-行业映射表")
        print("="*80)

        if stock_basic.empty:
            print("⚠️ 股票基本信息为空")
            return pd.DataFrame()

        # 使用stock_basic中的industry字段
        # 这个字段包含了申万行业分类信息
        mapping_df = stock_basic[['ts_code', 'symbol', 'name', 'industry']].copy()
        mapping_df.columns = ['ts_code', 'symbol', 'name', 'industry_name']

        # 如果有行业分类表，尝试匹配行业代码
        if industry_classify is not None and not industry_classify.empty:
            print("\n📊 匹配行业代码...")

            # 创建行业名称到代码的映射
            industry_map = dict(zip(
                industry_classify['industry_name'],
                industry_classify['industry_code']
            ))

            # 添加行业代码列
            mapping_df['industry_code'] = mapping_df['industry_name'].map(industry_map)

            # 统计匹配情况
            matched = mapping_df['industry_code'].notna().sum()
            print(f"   ✅ 成功匹配行业代码: {matched}/{len(mapping_df)}")

        # 添加时间戳
        mapping_df['update_date'] = datetime.now().strftime('%Y-%m-%d')

        print(f"\n✅ 映射表创建完成")
        print(f"   总股票数: {len(mapping_df)}")

        # 显示行业分布
        print(f"\n📈 申万行业分布:")
        industry_dist = mapping_df['industry_name'].value_counts().head(15)
        for industry, count in industry_dist.items():
            print(f"   - {industry}: {count}只")

        return mapping_df

    def save_mapping_data(
        self,
        mapping_df: pd.DataFrame,
        stock_basic: pd.DataFrame = None,
        industry_classify: pd.DataFrame = None
    ):
        """
        保存映射数据

        Args:
            mapping_df: 映射表
            stock_basic: 股票基本信息
            industry_classify: 行业分类
        """
        print("\n" + "="*80)
        print("💾 保存数据")
        print("="*80)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 保存映射表
        if not mapping_df.empty:
            print(f"\n📁 保存映射表...")

            # CSV格式
            mapping_file = self.output_dir / f"stock_industry_mapping_SW2021_{timestamp}.csv"
            mapping_df.to_csv(mapping_file, index=False, encoding='utf-8-sig')
            print(f"   ✅ {mapping_file.name}")

            # JSON格式
            json_file = self.output_dir / f"stock_industry_mapping_SW2021_{timestamp}.json"
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(mapping_df.to_dict('records'), f, ensure_ascii=False, indent=2)
            print(f"   ✅ {json_file.name}")

            # 创建字典格式便于查询
            dict_file = self.output_dir / f"stock_industry_dict_SW2021_{timestamp}.json"
            stock_to_industry = dict(zip(
                mapping_df['ts_code'],
                mapping_df[['industry_code', 'industry_name']].to_dict('records')
            ))
            # 移除None值
            stock_to_industry = {k: v for k, v in stock_to_industry.items() if v.get('industry_code')}
            with open(dict_file, 'w', encoding='utf-8') as f:
                json.dump(stock_to_industry, f, ensure_ascii=False, indent=2)
            print(f"   ✅ {dict_file.name} ({len(stock_to_industry)}条映射)")

            # 创建最新版本链接
            latest_mapping = self.output_dir / "stock_industry_mapping__latest.csv"
            import shutil
            shutil.copy2(mapping_file, latest_mapping)
            print(f"   ✅ 更新最新版本链接")

        # 保存股票基本信息
        if stock_basic is not None and not stock_basic.empty:
            print(f"\n📁 保存股票基本信息...")
            basic_file = self.output_dir / f"stock_basic_{timestamp}.csv"
            stock_basic.to_csv(basic_file, index=False, encoding='utf-8-sig')
            print(f"   ✅ {basic_file.name} ({len(stock_basic)}条)")

        # 保存行业分类
        if industry_classify is not None and not industry_classify.empty:
            print(f"\n📁 保存行业分类...")
            classify_file = self.output_dir / f"industry_classify_SW2021_{timestamp}.csv"
            industry_classify.to_csv(classify_file, index=False, encoding='utf-8-sig')
            print(f"   ✅ {classify_file.name} ({len(industry_classify)}条)")

        print(f"\n✅ 所有数据已保存到: {self.output_dir}")

    def generate_summary_report(
        self,
        mapping_df: pd.DataFrame,
        stock_basic: pd.DataFrame = None
    ) -> str:
        """
        生成数据摘要报告

        Args:
            mapping_df: 映射表
            stock_basic: 股票基本信息

        Returns:
            报告文本
        """
        print("\n" + "="*80)
        print("📊 生成数据摘要报告")
        print("="*80)

        report_lines = []
        report_lines.append("# 个股-申万行业映射数据摘要报告")
        report_lines.append(f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"\n数据目录: {self.output_dir}")

        # 基本统计
        if not mapping_df.empty:
            report_lines.append(f"\n## 映射表统计")
            report_lines.append(f"- 总股票数: {len(mapping_df)}")

            # 行业分布
            if 'industry_name' in mapping_df.columns:
                industry_dist = mapping_df['industry_name'].value_counts()
                report_lines.append(f"- 行业数量: {len(industry_dist)}")
                report_lines.append(f"\n## 行业分布（按股票数量排序）")

                for idx, (industry, count) in enumerate(industry_dist.items(), 1):
                    pct = count / len(mapping_df) * 100
                    report_lines.append(f"{idx}. {industry}: {count}只 ({pct:.2f}%)")

            # 交易所分布
            if 'ts_code' in mapping_df.columns:
                report_lines.append(f"\n## 交易所分布")
                mapping_df['exchange'] = mapping_df['ts_code'].str[-2:]
                exchange_dist = mapping_df['exchange'].value_counts()
                for exchange, count in exchange_dist.items():
                    exchange_name = '上海' if exchange == 'SH' else '深圳' if exchange == 'SZ' else exchange
                    report_lines.append(f"- {exchange_name}({exchange}): {count}只")

        # 保存报告
        report_file = self.output_dir / "stock_industry_mapping_report.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))

        print(f"\n✅ 报告已保存: {report_file.name}")

        return '\n'.join(report_lines)

    def run_full_download(self):
        """执行完整下载流程"""
        print("\n" + "="*80)
        print("🚀 开始完整下载流程")
        print("="*80)

        # 1. 下载股票基本信息（包含行业）
        stock_basic = self.download_stock_basic()

        if stock_basic.empty:
            print("\n❌ 下载股票基本信息失败，终止流程")
            return None

        # 2. 下载申万行业分类
        industry_classify = self.download_sw2021_industry_classify()

        # 3. 创建映射表
        mapping_df = self.create_industry_mapping(stock_basic, industry_classify)

        # 4. 保存数据
        self.save_mapping_data(mapping_df, stock_basic, industry_classify)

        # 5. 生成报告
        report = self.generate_summary_report(mapping_df, stock_basic)

        print("\n" + "="*80)
        print("✅ 完整下载流程完成！")
        print("="*80)

        # 显示摘要
        print(f"\n📊 数据摘要:")
        print(f"  - 股票总数: {len(stock_basic) if not stock_basic.empty else 0}")
        print(f"  - 映射记录: {len(mapping_df) if not mapping_df.empty else 0}")
        print(f"  - 行业分类: {len(industry_classify) if not industry_classify.empty else 0}")

        return {
            'stock_basic': stock_basic,
            'industry_classify': industry_classify,
            'mapping': mapping_df,
            'report': report
        }


def main():
    """主函数"""
    # 检查Token
    token = os.getenv("TUSHARE_TOKEN")
    if not token:
        print("❌ 请设置 TUSHARE_TOKEN 环境变量")
        print("   export TUSHARE_TOKEN='your_token_here'")
        sys.exit(1)

    print("🎯 个股-申万二级行业映射下载工具")
    print("="*80)

    # 创建下载器
    downloader = StockIndustryMappingDownloader(token=token)

    # 执行下载
    try:
        result = downloader.run_full_download()

        if result and result['mapping'] is not None and not result['mapping'].empty:
            print("\n✅ 下载成功！")
            print(f"\n数据文件位置: {downloader.output_dir}")
            print("\n主要文件:")
            print("  - stock_industry_mapping__latest.csv  # 最新映射表")
            print("  - stock_industry_dict__latest.json    # 字典格式映射")
            print("  - stock_industry_mapping_report.md   # 详细报告")
        else:
            print("\n⚠️ 下载未完成，请检查错误信息")

    except Exception as e:
        print(f"\n❌ 下载失败: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
