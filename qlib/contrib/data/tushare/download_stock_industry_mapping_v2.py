#!/usr/bin/env python3
"""
个股-申万二级行业完整映射下载工具 V2

使用index_member API反向查询，获取完整的申万二级行业分类映射

使用方法：
    export TUSHARE_TOKEN="your_token"
    python download_stock_industry_mapping_v2.py
"""

import os
import sys
import pandas as pd
import json
from pathlib import Path
from datetime import datetime
import time

def download_stock_industry_mapping():
    """下载完整的个股-申万二级行业映射"""

    token = os.getenv("TUSHARE_TOKEN")
    if not token:
        print("❌ 请设置 TUSHARE_TOKEN 环境变量")
        return

    print("🎯 个股-申万二级行业完整映射下载工具 V2")
    print("="*80)

    # 初始化TuShare
    import tushare as ts
    pro = ts.pro_api(token)

    # 输出目录
    output_dir = Path("~/.qlib/qlib_data/cn_data/industry_data").expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. 加载申万二级行业列表
    print("\n📥 加载申万二级行业列表...")
    # 尝试多个可能的文件名
    industry_l2_file = None
    for filename in [
        "industry_SW2021_L2__latest.csv",
        "industry_SW2021_L2_20251229_112014.csv",
        "industry__latest.csv"
    ]:
        candidate = output_dir / filename
        if candidate.exists():
            industry_l2_file = candidate
            break

    if not industry_l2_file:
        print(f"❌ 行业列表文件不存在")
        print("可用的文件:")
        for f in output_dir.glob("industry_SW*L2*"):
            print(f"  - {f.name}")
        return

    industry_l2 = pd.read_csv(industry_l2_file)
    # 筛选L2级别的行业
    if 'level' in industry_l2.columns:
        industry_l2 = industry_l2[industry_l2['level'] == 'L2'].copy()
    # 确保有industry_code列
    if 'industry_code' not in industry_l2.columns:
        industry_l2['industry_code'] = ''
    print(f"✅ 加载 {len(industry_l2)} 个申万二级行业")

    # 2. 获取每个行业的成分股
    print("\n📥 开始获取行业成分股...")
    print("="*80)

    all_mappings = []
    total = len(industry_l2)

    for idx, row in industry_l2.iterrows():
        index_code = row['index_code']
        industry_name = row['industry_name']
        industry_code = row.get('industry_code', '')

        print(f"\n[{idx+1}/{total}] {industry_name} ({index_code})...", end=" ", flush=True)

        try:
            # 获取该行业指数的成分股
            members = pro.index_member(index_code=index_code)

            if members is not None and not members.empty:
                # 只保留当前有效的成分股
                valid_members = members[
                    (members['is_new'] == 'Y') |
                    (members['out_date'].isna())
                ]

                for _, member in valid_members.iterrows():
                    all_mappings.append({
                        'ts_code': member['con_code'],
                        'index_code': index_code,
                        'industry_code': industry_code,
                        'industry_name': industry_name,
                        'in_date': member.get('in_date', ''),
                        'is_new': member.get('is_new', '')
                    })

                print(f"✅ {len(valid_members)}只")
            else:
                print("⚠️ 无数据")

            # 避免API频率限制
            time.sleep(0.21)

        except Exception as e:
            print(f"❌ {str(e)}")
            continue

    if not all_mappings:
        print("\n❌ 未获取到任何映射数据")
        return

    # 3. 构建映射表
    print("\n📊 构建映射表...")
    mapping_df = pd.DataFrame(all_mappings)

    print(f"✅ 总映射记录: {len(mapping_df)}")
    print(f"   覆盖股票: {mapping_df['ts_code'].nunique()} 只")
    print(f"   覆盖行业: {mapping_df['industry_name'].nunique()} 个")

    # 4. 添加股票基本信息
    print("\n📊 添加股票基本信息...")
    stock_basic = pro.stock_basic(
        exchange='',
        list_status='L',
        fields='ts_code,symbol,name,area,market,list_date'
    )

    # 合并基本信息
    mapping_df = mapping_df.merge(
        stock_basic[['ts_code', 'symbol', 'name']],
        on='ts_code',
        how='left'
    )

    # 添加更新时间
    mapping_df['update_date'] = datetime.now().strftime('%Y-%m-%d')

    # 重新排序列
    mapping_df = mapping_df[[
        'ts_code', 'symbol', 'name', 'industry_code', 'industry_name',
        'index_code', 'in_date', 'is_new', 'update_date'
    ]]

    # 5. 保存数据
    print("\n💾 保存数据...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # CSV格式
    csv_file = output_dir / f"stock_industry_mapping_SW2021_complete_{timestamp}.csv"
    mapping_df.to_csv(csv_file, index=False, encoding='utf-8-sig')
    print(f"   ✅ {csv_file.name}")

    # 更新latest链接
    latest_csv = output_dir / "stock_industry_mapping_SW2021__latest.csv"
    import shutil
    shutil.copy2(csv_file, latest_csv)
    print(f"   ✅ 更新latest链接")

    # JSON字典格式
    json_dict_file = output_dir / f"stock_industry_dict_SW2021_complete_{timestamp}.json"
    stock_to_industry = {}
    for _, row in mapping_df.iterrows():
        stock_to_industry[row['ts_code']] = {
            'industry_code': row['industry_code'],
            'industry_name': row['industry_name'],
            'symbol': row['symbol'],
            'name': row['name']
        }

    with open(json_dict_file, 'w', encoding='utf-8') as f:
        json.dump(stock_to_industry, f, ensure_ascii=False, indent=2)
    print(f"   ✅ {Path(json_dict_file).name} ({len(stock_to_industry)}条)")

    # 6. 生成报告
    print("\n📊 生成报告...")
    report_lines = []
    report_lines.append("# 个股-申万二级行业完整映射报告")
    report_lines.append(f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"\n## 数据统计")
    report_lines.append(f"- 总映射记录: {len(mapping_df)}")
    report_lines.append(f"- 覆盖股票: {mapping_df['ts_code'].nunique()} 只")
    report_lines.append(f"- 覆盖行业: {mapping_df['industry_name'].nunique()} 个")

    report_lines.append(f"\n## 行业分布（Top 20）")
    industry_dist = mapping_df['industry_name'].value_counts().head(20)
    for industry, count in industry_dist.items():
        pct = count / len(mapping_df) * 100
        report_lines.append(f"{industry_dist.index.get(industry, '')+1}. {industry}: {count}只 ({pct:.2f}%)")

    report_file = output_dir / "stock_industry_mapping_complete_report.md"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))
    print(f"   ✅ {Path(report_file).name}")

    print("\n" + "="*80)
    print("✅ 下载完成！")
    print("="*80)

    print(f"\n数据文件位置: {output_dir}")
    print("\n主要文件:")
    print(f"  - {csv_file.name}")
    print(f"  - {Path(json_dict_file).name}")
    print(f"  - {Path(report_file).name}")

    return mapping_df

if __name__ == "__main__":
    download_stock_industry_mapping()
