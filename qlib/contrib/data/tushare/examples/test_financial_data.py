#!/usr/bin/env python3
"""
财务数据快速测试脚本

演示TuShare财务数据下载和因子计算
"""

import os
import sys

# 检查Token
token = os.getenv("TUSHARE_TOKEN")
if not token:
    print("❌ 请设置TUSHARE_TOKEN环境变量")
    print("   export TUSHARE_TOKEN='your_token_here'")
    sys.exit(1)

print("🎯 TuShare财务数据测试")
print("="*80)

try:
    import tushare as ts
    import pandas as pd

    # 初始化
    pro = ts.pro_api(token)
    print(f"✅ TuShare初始化成功")
    print(f"   Token: {token[:10]}...")

    # 测试1: 下载财务指标
    print("\n📊 测试1: 下载财务指标...")

    df = pro.fina_indicator(
        ts_code='000001.SZ',  # 平安银行
        start_date='20240101',
        end_date='20241231'
    )

    if df is not None and not df.empty:
        print(f"✅ 成功获取 {len(df)} 条财务指标记录")
        print("\n字段列表:")
        print(df.columns.tolist())

        print("\n数据预览:")
        print(df[['ts_code', 'end_date', 'roe', 'roa', 'grossprofit_margin', 'or_yoy']].head())

        # 保存示例
        output_file = '/tmp/financial_data_sample.csv'
        df.to_csv(output_file, index=False)
        print(f"\n💾 数据已保存到: {output_file}")

    else:
        print("⚠️ 未获取到数据")

    # 测试2: 查看可用的财务指标字段
    print("\n📊 测试2: 常用财务指标字段")
    print("="*80)

    common_fields = {
        "盈利能力": ['roe', 'roa', 'grossprofit_margin', 'netprofit_margin'],
        "成长能力": ['or_yoy', 'op_yoy', 'ebt_yoy'],
        "估值": ['pe', 'pb', 'ps'],
        "偿债能力": ['debt_to_assets', 'current_ratio', 'quick_ratio'],
        "运营能力": ['assets_turnover', 'ar_turnover', 'inv_turnover']
    }

    for category, fields in common_fields.items():
        available = [f for f in fields if f in df.columns]
        if available:
            print(f"\n{category}: {', '.join(available)}")

    # 测试3: 计算简单财务因子
    print("\n📊 测试3: 计算财务因子")
    print("="*80)

    if not df.empty:
        # 提取最新一期数据
        latest = df.iloc[-1]

        print(f"\n股票: {latest['ts_code']}")
        print(f"报告期: {latest['end_date']}")

        factors = []
        if 'roe' in df.columns:
            roe = latest['roe']
            factors.append(f"ROE: {roe:.2f}%")

        if 'roa' in df.columns:
            roa = latest['roa']
            factors.append(f"ROA: {roa:.2f}%")

        if 'grossprofit_margin' in df.columns:
            margin = latest['grossprofit_margin']
            factors.append(f"毛利率: {margin:.2f}%")

        if 'or_yoy' in df.columns:
            growth = latest['or_yoy']
            factors.append(f"营收增长: {growth:.2f}%")

        if 'pe' in df.columns:
            pe = latest['pe']
            factors.append(f"PE: {pe:.2f}")

        if 'pb' in df.columns:
            pb = latest['pb']
            factors.append(f"PB: {pb:.2f}")

        print("\n关键财务指标:")
        for factor in factors:
            print(f"  • {factor}")

    print("\n" + "="*80)
    print("✅ 测试完成！")
    print("="*80)

    print("\n💡 下一步:")
    print("   1. 批量下载多只股票的财务数据")
    print("   2. 计算综合财务因子得分")
    print("   3. 集成到Qlib量化策略中")
    print("   4. 进行回测验证")

    print("\n📖 查看完整文档:")
    print("   cat qlib/contrib/data/tushare/FINANCIAL_DATA_GUIDE.md")

    print("\n🔗 运行完整示例:")
    print("   python qlib/contrib/data/tushare/examples/financial_data_example.py")

except Exception as e:
    print(f"\n❌ 错误: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
