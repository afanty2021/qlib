#!/usr/bin/env python3
"""
TuShare财务数据集成示例

演示如何从TuShare下载财务数据并集成到Qlib作为因子使用
"""

import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Union

# 添加qlib路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))


# ============================================================
# TuShare财务数据下载器
# ============================================================

class TuShareFinancialDataDownloader:
    """TuShare财务数据下载器"""

    def __init__(self, token: str = None):
        """
        初始化下载器

        Args:
            token: TuShare Token (默认从环境变量读取)
        """
        self.token = token or os.getenv("TUSHARE_TOKEN")
        if not self.token:
            raise ValueError("请设置TUSHARE_TOKEN环境变量或传入token参数")

        import tushare as ts
        self.pro = ts.pro_api(self.token)

        print(f"✅ TuShare财务数据下载器初始化完成")

    # --------------------------------------------------------
    # 1. 利润表数据
    # --------------------------------------------------------

    def download_income(
        self,
        ts_code: str = None,
        start_date: str = None,
        end_date: str = None,
        period: str = None
    ) -> pd.DataFrame:
        """
        下载利润表数据

        Args:
            ts_code: 股票代码 (例如: "000001.SZ")
            start_date: 开始日期 (例如: "20200101")
            end_date: 结束日期 (例如: "20241231")
            period: 报告期 (例如: "20241231")

        Returns:
            利润表DataFrame
        """
        print("📊 下载利润表数据...")

        df = self.pro.income(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            period=period
        )

        if df is not None and not df.empty:
            print(f"✅ 利润表数据: {len(df)} 条记录")
        else:
            print("⚠️ 无利润表数据")

        return df

    # --------------------------------------------------------
    # 2. 资产负债表数据
    # --------------------------------------------------------

    def download_balancesheet(
        self,
        ts_code: str = None,
        start_date: str = None,
        end_date: str = None,
        period: str = None
    ) -> pd.DataFrame:
        """
        下载资产负债表数据

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            period: 报告期

        Returns:
            资产负债表DataFrame
        """
        print("📊 下载资产负债表数据...")

        df = self.pro.balancesheet(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            period=period
        )

        if df is not None and not df.empty:
            print(f"✅ 资产负债表数据: {len(df)} 条记录")
        else:
            print("⚠️ 无资产负债表数据")

        return df

    # --------------------------------------------------------
    # 3. 现金流量表数据
    # --------------------------------------------------------

    def download_cashflow(
        self,
        ts_code: str = None,
        start_date: str = None,
        end_date: str = None,
        period: str = None
    ) -> pd.DataFrame:
        """
        下载现金流量表数据

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            period: 报告期

        Returns:
            现金流量表DataFrame
        """
        print("📊 下载现金流量表数据...")

        df = self.pro.cashflow(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            period=period
        )

        if df is not None and not df.empty:
            print(f"✅ 现金流量表数据: {len(df)} 条记录")
        else:
            print("⚠️ 无现金流量表数据")

        return df

    # --------------------------------------------------------
    # 4. 财务指标数据
    # --------------------------------------------------------

    def download_fina_indicator(
        self,
        ts_code: str = None,
        start_date: str = None,
        end_date: str = None,
        period: str = None
    ) -> pd.DataFrame:
        """
        下载财务指标数据 (最常用)

        包含：ROE、ROA、毛利率、净利率、负债率等

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            period: 报告期

        Returns:
            财务指标DataFrame
        """
        print("📊 下载财务指标数据...")

        df = self.pro.fina_indicator(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            period=period
        )

        if df is not None and not df.empty:
            print(f"✅ 财务指标数据: {len(df)} 条记录")
        else:
            print("⚠️ 无财务指标数据")

        return df

    # --------------------------------------------------------
    # 5. 分红送股数据
    # --------------------------------------------------------

    def download_dividend(
        self,
        ts_code: str = None,
        start_date: str = None,
        end_date: str = None
    ) -> pd.DataFrame:
        """
        下载分红送股数据

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            分红送股DataFrame
        """
        print("📊 下载分红送股数据...")

        df = self.pro.dividend(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date
        )

        if df is not None and not df.empty:
            print(f"✅ 分红送股数据: {len(df)} 条记录")
        else:
            print("⚠️ 无分红送股数据")

        return df

    # --------------------------------------------------------
    # 6. 业绩预告/快报
    # --------------------------------------------------------

    def download_forecast(
        self,
        ts_code: str = None,
        start_date: str = None,
        end_date: str = None,
        period: str = None
    ) -> pd.DataFrame:
        """
        下载业绩预告数据

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            period: 报告期

        Returns:
            业绩预告DataFrame
        """
        print("📊 下载业绩预告数据...")

        df = self.pro.forecast(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            period=period
        )

        if df is not None and not df.empty:
            print(f"✅ 业绩预告数据: {len(df)} 条记录")
        else:
            print("⚠️ 无业绩预告数据")

        return df

    # --------------------------------------------------------
    # 批量下载
    # --------------------------------------------------------

    def download_all_financial_data(
        self,
        ts_code: str,
        start_date: str = None,
        end_date: str = None
    ) -> Dict[str, pd.DataFrame]:
        """
        下载所有财务数据

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            所有财务数据的字典
        """
        print(f"\n🚀 开始下载 {ts_code} 的所有财务数据...")
        print("="*80)

        all_data = {}

        # 1. 利润表
        try:
            all_data['income'] = self.download_income(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )
        except Exception as e:
            print(f"❌ 利润表下载失败: {str(e)}")

        # 2. 资产负债表
        try:
            all_data['balancesheet'] = self.download_balancesheet(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )
        except Exception as e:
            print(f"❌ 资产负债表下载失败: {str(e)}")

        # 3. 现金流量表
        try:
            all_data['cashflow'] = self.download_cashflow(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )
        except Exception as e:
            print(f"❌ 现金流量表下载失败: {str(e)}")

        # 4. 财务指标
        try:
            all_data['fina_indicator'] = self.download_fina_indicator(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )
        except Exception as e:
            print(f"❌ 财务指标下载失败: {str(e)}")

        # 5. 分红送股
        try:
            all_data['dividend'] = self.download_dividend(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )
        except Exception as e:
            print(f"❌ 分红送股下载失败: {str(e)}")

        print("="*80)
        print(f"✅ {ts_code} 财务数据下载完成")

        return all_data


# ============================================================
# 财务因子计算器
# ============================================================

class FinancialFactorCalculator:
    """财务因子计算器"""

    def __init__(self, financial_data: Dict[str, pd.DataFrame]):
        """
        初始化因子计算器

        Args:
            financial_data: 财务数据字典
        """
        self.financial_data = financial_data
        print("✅ 财务因子计算器初始化完成")

    # --------------------------------------------------------
    # 盈利能力因子
    # --------------------------------------------------------

    def calculate_roe(self) -> pd.DataFrame:
        """
        计算ROE (净资产收益率)

        Returns:
            ROE数据DataFrame
        """
        if 'fina_indicator' not in self.financial_data:
            print("⚠️ 缺少财务指标数据")
            return pd.DataFrame()

        df = self.financial_data['fina_indicator'].copy()

        # 提取ROE
        if 'roe' in df.columns:
            roe_df = df[['ts_code', 'end_date', 'roe']].copy()
            roe_df.columns = ['stock_code', 'date', 'roe']
            print("✅ 计算ROE因子")
            return roe_df
        else:
            print("⚠️ 数据中没有roe字段")
            return pd.DataFrame()

    def calculate_roa(self) -> pd.DataFrame:
        """
        计算ROA (总资产收益率)

        Returns:
            ROA数据DataFrame
        """
        if 'fina_indicator' not in self.financial_data:
            return pd.DataFrame()

        df = self.financial_data['fina_indicator'].copy()

        if 'roa' in df.columns:
            roa_df = df[['ts_code', 'end_date', 'roa']].copy()
            roa_df.columns = ['stock_code', 'date', 'roa']
            print("✅ 计算ROA因子")
            return roa_df
        else:
            return pd.DataFrame()

    def calculate_gross_profit_margin(self) -> pd.DataFrame:
        """
        计算毛利率

        Returns:
            毛利率DataFrame
        """
        if 'fina_indicator' not in self.financial_data:
            return pd.DataFrame()

        df = self.financial_data['fina_indicator'].copy()

        if 'grossprofit_margin' in df.columns:
            margin_df = df[['ts_code', 'end_date', 'grossprofit_margin']].copy()
            margin_df.columns = ['stock_code', 'date', 'gross_profit_margin']
            print("✅ 计算毛利率因子")
            return margin_df
        else:
            return pd.DataFrame()

    def calculate_net_profit_margin(self) -> pd.DataFrame:
        """
        计算净利率

        Returns:
            净利率DataFrame
        """
        if 'fina_indicator' not in self.financial_data:
            return pd.DataFrame()

        df = self.financial_data['fina_indicator'].copy()

        if 'netprofit_margin' in df.columns:
            margin_df = df[['ts_code', 'end_date', 'netprofit_margin']].copy()
            margin_df.columns = ['stock_code', 'date', 'net_profit_margin']
            print("✅ 计算净利率因子")
            return margin_df
        else:
            return pd.DataFrame()

    # --------------------------------------------------------
    # 成长能力因子
    # --------------------------------------------------------

    def calculate_revenue_growth(self) -> pd.DataFrame:
        """
        计算营收增长率

        Returns:
            营收增长率DataFrame
        """
        if 'fina_indicator' not in self.financial_data:
            return pd.DataFrame()

        df = self.financial_data['fina_indicator'].copy()

        if 'or_yoy' in df.columns:  # 营业收入同比增长率
            growth_df = df[['ts_code', 'end_date', 'or_yoy']].copy()
            growth_df.columns = ['stock_code', 'date', 'revenue_growth']
            print("✅ 计算营收增长率因子")
            return growth_df
        else:
            return pd.DataFrame()

    def calculate_profit_growth(self) -> pd.DataFrame:
        """
        计算利润增长率

        Returns:
            利润增长率DataFrame
        """
        if 'fina_indicator' not in self.financial_data:
            return pd.DataFrame()

        df = self.financial_data['fina_indicator'].copy()

        if 'op_yoy' in df.columns:  # 营业利润同比增长率
            growth_df = df[['ts_code', 'end_date', 'op_yoy']].copy()
            growth_df.columns = ['stock_code', 'date', 'profit_growth']
            print("✅ 计算利润增长率因子")
            return growth_df
        else:
            return pd.DataFrame()

    # --------------------------------------------------------
    # 估值因子
    # --------------------------------------------------------

    def calculate_pe_ratio(self, price_data: pd.DataFrame = None) -> pd.DataFrame:
        """
        计算市盈率PE

        Args:
            price_data: 价格数据 (可选)

        Returns:
            PE数据DataFrame
        """
        if 'fina_indicator' not in self.financial_data:
            return pd.DataFrame()

        df = self.financial_data['fina_indicator'].copy()

        if 'pe' in df.columns:
            pe_df = df[['ts_code', 'end_date', 'pe']].copy()
            pe_df.columns = ['stock_code', 'date', 'pe']
            print("✅ 计算PE因子")
            return pe_df
        else:
            return pd.DataFrame()

    def calculate_pb_ratio(self) -> pd.DataFrame:
        """
        计算市净率PB

        Returns:
            PB数据DataFrame
        """
        if 'fina_indicator' not in self.financial_data:
            return pd.DataFrame()

        df = self.financial_data['fina_indicator'].copy()

        if 'pb' in df.columns:
            pb_df = df[['ts_code', 'end_date', 'pb']].copy()
            pb_df.columns = ['stock_code', 'date', 'pb']
            print("✅ 计算PB因子")
            return pb_df
        else:
            return pd.DataFrame()

    # --------------------------------------------------------
    # 偿债能力因子
    # --------------------------------------------------------

    def calculate_debt_ratio(self) -> pd.DataFrame:
        """
        计算资产负债率

        Returns:
            资产负债率DataFrame
        """
        if 'balancesheet' not in self.financial_data:
            return pd.DataFrame()

        bs_df = self.financial_data['balancesheet'].copy()

        # 计算资产负债率 = 总负债 / 总资产
        if 'total_liab' in bs_df.columns and 'total_assets' in bs_df.columns:
            bs_df['debt_ratio'] = bs_df['total_liab'] / bs_df['total_assets']
            debt_df = bs_df[['ts_code', 'end_date', 'debt_ratio']].copy()
            debt_df.columns = ['stock_code', 'date', 'debt_ratio']
            print("✅ 计算资产负债率因子")
            return debt_df
        else:
            return pd.DataFrame()

    def calculate_current_ratio(self) -> pd.DataFrame:
        """
        计算流动比率

        Returns:
            流动比率DataFrame
        """
        if 'balancesheet' not in self.financial_data:
            return pd.DataFrame()

        bs_df = self.financial_data['balancesheet'].copy()

        # 流动比率 = 流动资产 / 流动负债
        if 'total_cur_assets' in bs_df.columns and 'total_cur_liab' in bs_df.columns:
            bs_df['current_ratio'] = bs_df['total_cur_assets'] / bs_df['total_cur_liab']
            ratio_df = bs_df[['ts_code', 'end_date', 'current_ratio']].copy()
            ratio_df.columns = ['stock_code', 'date', 'current_ratio']
            print("✅ 计算流动比率因子")
            return ratio_df
        else:
            return pd.DataFrame()

    # --------------------------------------------------------
    # 综合因子
    # --------------------------------------------------------

    def calculate_all_factors(self) -> pd.DataFrame:
        """
        计算所有财务因子

        Returns:
            综合因子DataFrame
        """
        print("\n📊 计算所有财务因子...")
        print("="*80)

        factors = {}

        # 盈利能力
        factors['roe'] = self.calculate_roe()
        factors['roa'] = self.calculate_roa()
        factors['gross_profit_margin'] = self.calculate_gross_profit_margin()
        factors['net_profit_margin'] = self.calculate_net_profit_margin()

        # 成长能力
        factors['revenue_growth'] = self.calculate_revenue_growth()
        factors['profit_growth'] = self.calculate_profit_growth()

        # 估值
        factors['pe'] = self.calculate_pe_ratio()
        factors['pb'] = self.calculate_pb_ratio()

        # 偿债能力
        factors['debt_ratio'] = self.calculate_debt_ratio()
        factors['current_ratio'] = self.calculate_current_ratio()

        # 合并所有因子
        all_factors = []
        for factor_name, factor_df in factors.items():
            if not factor_df.empty:
                factor_df = factor_df.copy()
                factor_df['factor_name'] = factor_name
                all_factors.append(factor_df)

        if all_factors:
            combined = pd.concat(all_factors, ignore_index=True)
            print(f"\n✅ 计算完成，共 {len(combined)} 条因子记录")
            print("="*80)
            return combined
        else:
            print("\n⚠️ 没有可用的因子数据")
            return pd.DataFrame()


# ============================================================
# 示例函数
# ============================================================

def example_1_download_financial_data():
    """示例1: 下载财务数据"""
    print("\n" + "="*80)
    print("示例1: 下载财务数据")
    print("="*80)

    try:
        # 初始化下载器
        downloader = TuShareFinancialDataDownloader()

        # 下载平安银行的财务数据
        all_data = downloader.download_all_financial_data(
            ts_code="000001.SZ",
            start_date="20230101",
            end_date="20241231"
        )

        # 查看财务指标
        if 'fina_indicator' in all_data and not all_data['fina_indicator'].empty:
            print("\n财务指标预览:")
            print(all_data['fina_indicator'].head())

    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        print("💡 提示: 请确保设置了TUSHARE_TOKEN环境变量")


def example_2_calculate_factors():
    """示例2: 计算财务因子"""
    print("\n" + "="*80)
    print("示例2: 计算财务因子")
    print("="*80)

    # 这里使用模拟数据演示
    print("💡 使用实际财务数据计算因子...")

    # 模拟财务指标数据
    mock_data = {
        'fina_indicator': pd.DataFrame({
            'ts_code': ['000001.SZ'] * 4,
            'end_date': ['2024-03-31', '2024-06-30', '2024-09-30', '2024-12-31'],
            'roe': [12.5, 13.2, 11.8, 14.1],
            'roa': [1.2, 1.3, 1.1, 1.4],
            'grossprofit_margin': [45.2, 46.1, 44.8, 47.3],
            'netprofit_margin': [25.3, 26.1, 24.9, 27.2],
            'or_yoy': [8.5, 9.2, 7.8, 10.1],
            'op_yoy': [12.3, 13.5, 11.2, 14.8],
            'pe': [8.5, 9.2, 7.8, 8.9],
            'pb': [1.2, 1.3, 1.1, 1.25]
        })
    }

    # 计算因子
    calculator = FinancialFactorCalculator(mock_data)

    # 计算ROE
    roe_df = calculator.calculate_roe()
    if not roe_df.empty:
        print("\nROE因子:")
        print(roe_df)

    # 计算所有因子
    all_factors = calculator.calculate_all_factors()
    if not all_factors.empty:
        print("\n所有因子汇总:")
        print(all_factors.head(10))


def example_3_financial_factor_pipeline():
    """示例3: 完整的财务因子流水线"""
    print("\n" + "="*80)
    print("示例3: 财务因子处理流水线")
    print("="*80)

    print("\n步骤:")
    print("1. 从TuShare下载财务数据")
    print("2. 清洗和预处理数据")
    print("3. 计算各类财务因子")
    print("4. 标准化和去极值")
    print("5. 保存为Qlib可用格式")
    print("6. 集成到Qlib策略中")

    print("\n💡 详细实现请参考完整文档")


# ============================================================
# 主函数
# ============================================================

def main():
    """主函数"""
    print("\n🎯 TuShare财务数据集成示例")
    print("="*80)
    print("本示例演示如何:")
    print("1. 从TuShare下载个股财务数据")
    print("2. 计算常用财务因子")
    print("3. 集成到Qlib量化策略")
    print("="*80)

    # 示例1: 下载财务数据
    example_1_download_financial_data()

    # 示例2: 计算财务因子
    example_2_calculate_factors()

    # 示例3: 完整流水线
    example_3_financial_factor_pipeline()

    print("\n" + "="*80)
    print("✅ 所有示例运行完成！")
    print("="*80)

    print("\n💡 支持的财务数据类型:")
    print("   ✅ 利润表 (收入、成本、利润等)")
    print("   ✅ 资产负债表 (资产、负债、权益等)")
    print("   ✅ 现金流量表 (经营、投资、筹资现金流)")
    print("   ✅ 财务指标 (ROE、ROA、毛利率等)")
    print("   ✅ 分红送股 (分红、送股、配股等)")
    print("   ✅ 业绩预告 (预告净利润、增长率等)")

    print("\n📊 常用财务因子:")
    print("   盈利能力: ROE、ROA、毛利率、净利率")
    print("   成长能力: 营收增长率、利润增长率")
    print("   估值指标: PE、PB、PS")
    print("   偿债能力: 资产负债率、流动比率")
    print("   运营能力: 总资产周转率、存货周转率")

    print("\n🚀 下一步:")
    print("   1. 设置TUSHARE_TOKEN环境变量")
    print("   2. 运行示例下载数据")
    print("   3. 计算所需因子")
    print("   4. 集成到Qlib策略")


if __name__ == "__main__":
    main()
