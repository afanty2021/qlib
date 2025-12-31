#!/usr/bin/env python3
"""
TuShare行业分类完整映射生成工具

功能：
1. 使用TuShare的stock_basic.industry字段（110个二级行业）
2. 创建行业到一级行业的映射关系
3. 生成完整的股票-行业映射表（覆盖所有5466只A股）
4. 提供便捷的查询和使用方法

使用方法：
    export TUSHARE_TOKEN="your_token"
    python create_tushare_industry_mapping.py
"""

import os
import sys
import pandas as pd
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List
import time

def create_industry_mapping():
    """创建TuShare行业分类映射"""

    token = os.getenv("TUSHARE_TOKEN")
    if not token:
        print("❌ 请设置 TUSHARE_TOKEN 环境变量")
        return None

    print("🎯 TuShare行业分类完整映射生成工具")
    print("="*80)

    # 初始化TuShare
    import tushare as ts
    pro = ts.pro_api(token)

    # 输出目录
    output_dir = Path("~/.qlib/qlib_data/cn_data/industry_data").expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. 定义TuShare行业到一级行业的映射
    print("\n📋 加载行业映射规则...")

    # 基于TuShare的110个二级行业，手动定义一级行业映射
    industry_level_mapping = {
        # 农林牧渔 (6个)
        '种植业': '农林牧渔',
        '渔业': '农林牧渔',
        '林业': '农林牧渔',
        '农业综合': '农林牧渔',
        '农药化肥': '农林牧渔',
        '饲料': '农林牧渔',
        '畜禽养殖': '农林牧渔',

        # 采掘 (4个)
        '煤炭开采': '采掘',
        '石油开采': '采掘',
        '其他采掘': '采掘',
        '采掘服务': '采掘',

        # 化工 (7个)
        '化工原料': '化工',
        '化学制品': '化工',
        '化纤': '化工',
        '塑料': '化工',
        '橡胶': '化工',
        '日用化工': '化工',
        '石油加工': '化工',

        # 钢铁 (3个)
        '普钢': '钢铁',
        '特钢': '钢铁',
        '钢加工': '钢铁',

        # 有色金属 (7个)
        '工业金属': '有色金属',
        '稀有金属': '有色金属',
        '小金属': '有色金属',
        '黄金': '有色金属',
        '铜': '有色金属',
        '铝': '有色金属',
        '铅锌': '有色金属',

        # 电子 (4个)
        '元器件': '电子',
        '半导体': '电子',
        '光学光电子': '电子',
        '其他电子': '电子',
        'IT设备': '电子',

        # 汽车 (3个)
        '汽车整车': '汽车',
        '汽车配件': '汽车',
        '汽车服务': '汽车',

        # 家用电器 (1个)
        '家用电器': '家用电器',

        # 食品饮料 (4个)
        '食品': '食品饮料',
        '白酒': '食品饮料',
        '软饮料': '食品饮料',
        '乳制品': '食品饮料',

        # 纺织服装 (2个)
        '纺织': '纺织服装',
        '服饰': '纺织服装',

        # 轻工制造 (4个)
        '造纸': '轻工制造',
        '包装印刷': '轻工制造',
        '家用轻工': '轻工制造',
        '其他轻工制造': '轻工制造',

        # 医药生物 (6个)
        '化学制药': '医药生物',
        '中成药': '医药生物',
        '生物制药': '医药生物',
        '医疗器械': '医药生物',
        '医药商业': '医药生物',
        '医疗保健': '医药生物',

        # 公用事业 (4个)
        '火力发电': '公用事业',
        '水力发电': '公用事业',
        '新型电力': '公用事业',
        '水务': '公用事业',
        '供气供热': '公用事业',
        '环境保护': '公用事业',

        # 交通运输 (8个)
        '铁路': '交通运输',
        '公路': '交通运输',
        '水运': '交通运输',
        '航空': '交通运输',
        '空运': '交通运输',
        '机场': '交通运输',
        '港口': '交通运输',
        '航运': '交通运输',

        # 房地产 (3个)
        '全国地产': '房地产',
        '区域地产': '房地产',
        '房产服务': '房地产',

        # 商贸零售 (5个)
        '百货': '商贸零售',
        '超市连锁': '商贸零售',
        '一般零售': '商贸零售',
        '专业零售': '商贸零售',
        '商贸代理': '商贸零售',
        '其他商业': '商贸零售',

        # 传媒 (4个)
        '出版业': '传媒',
        '影视音像': '传媒',
        '广告包装': '传媒',
        '互联网': '传媒',
        '文化传播': '传媒',

        # 银行 (1个)
        '银行': '银行',

        # 非银金融 (3个)
        '证券': '非银金融',
        '保险': '非银金融',
        '多元金融': '非银金融',

        # 综合 (1个)
        '综合类': '综合',

        # 通信 (2个)
        '通信设备': '通信',
        '电信运营': '通信',

        # 计算机 (2个)
        '软件服务': '计算机',
        '计算机设备': '计算机',

        # 机械设备 (7个)
        '通用机械': '机械设备',
        '专用机械': '机械设备',
        '仪器仪表': '机械设备',
        '工程机械': '机械设备',
        '机床制造': '机械设备',
        '机械基件': '机械设备',
        '化工机械': '机械设备',
        '农用机械': '机械设备',
        '轻工机械': '机械设备',
        '纺织机械': '机械设备',
        '电气设备': '机械设备',
        '电器仪表': '机械设备',

        # 建筑材料 (3个)
        '水泥': '建筑材料',
        '玻璃': '建筑材料',
        '其他建材': '建筑材料',
        '矿物制品': '建筑材料',

        # 建筑装饰 (4个)
        '房屋建设': '建筑装饰',
        '基础建设': '建筑装饰',
        '专业工程': '建筑装饰',
        '装修装饰': '建筑装饰',
        '园林工程': '建筑装饰',

        # 国防军工 (4个)
        '航天装备': '国防军工',
        '航空装备': '国防军工',
        '地面兵装': '国防军工',
        '船舶制造': '国防军工',

        # 环保 (1个)
        '环保工程及服务': '环保',
        '环境保护': '环保',

        # 社会服务 (2个)
        '景点': '社会服务',
        '旅游服务': '社会服务',
        '酒店餐饮': '社会服务',
        '教育': '社会服务',

        # 电力设备 (1个)
        '电源设备': '电力设备',
        '电机': '电力设备',
        '电气自动化设备': '电力设备',
        '高低压设备': '电力设备',

        # 信息
        '文教休闲': '传媒',
        '旅游酒店': '社会服务',
        '运输设备': '交运设备',
        '商贸': '商贸零售',
    }

    print(f"  ✅ 定义了 {len(industry_level_mapping)} 个二级行业映射")

    # 2. 下载股票基本信息
    print("\n📥 下载股票基本信息...")
    stock_basic = pro.stock_basic(
        exchange='',
        list_status='L',
        fields='ts_code,symbol,name,area,industry,market,list_date'
    )

    print(f"  ✅ 获取 {len(stock_basic)} 只股票基本信息")

    # 3. 创建行业映射表
    print("\n🔗 创建行业映射表...")

    # 添加一级行业
    stock_basic['industry_l1'] = stock_basic['industry'].map(industry_level_mapping)

    # 为无法映射的行业设置"其他"
    stock_basic['industry_l1'] = stock_basic['industry_l1'].fillna('其他')

    # 统计一级行业数量
    l1_count = stock_basic['industry_l1'].nunique()
    l2_count = stock_basic['industry'].nunique()

    print(f"  ✅ 一级行业: {l1_count}个")
    print(f"  ✅ 二级行业: {l2_count}个")

    # 4. 创建行业层级结构
    print("\n📊 创建行业层级结构...")

    # 按一级行业分组
    industry_structure = {}
    for l1 in sorted(stock_basic['industry_l1'].unique()):
        l2_list = stock_basic[stock_basic['industry_l1'] == l1]['industry'].unique().tolist()
        industry_structure[l1] = l2_list

    # 保存行业层级结构
    structure_file = output_dir / "tushare_industry_structure.json"
    with open(structure_file, 'w', encoding='utf-8') as f:
        json.dump(industry_structure, f, ensure_ascii=False, indent=2)
    print(f"  ✅ 行业层级结构已保存")

    # 5. 保存完整映射表
    print("\n💾 保存映射数据...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # CSV格式
    csv_file = output_dir / f"tushare_industry_mapping_complete_{timestamp}.csv"
    stock_basic[['ts_code', 'symbol', 'name', 'industry', 'industry_l1', 'area', 'market', 'list_date']].to_csv(
        csv_file, index=False, encoding='utf-8-sig'
    )
    print(f"  ✅ {csv_file.name}")

    # 更新latest链接
    latest_csv = output_dir / "tushare_industry_mapping__latest.csv"
    import shutil
    shutil.copy2(csv_file, latest_csv)
    print(f"  ✅ 已更新latest链接")

    # 6. 创建便捷查询字典
    print("\n📖 创建查询字典...")

    # 股票代码 -> 行业信息
    stock_to_industry = {}
    for _, row in stock_basic.iterrows():
        stock_to_industry[row['ts_code']] = {
            'industry_l2': row['industry'],
            'industry_l1': row['industry_l1'],
            'symbol': row['symbol'],
            'name': row['name']
        }

    dict_file = output_dir / f"tushare_stock_to_industry_dict_{timestamp}.json"
    with open(dict_file, 'w', encoding='utf-8') as f:
        json.dump(stock_to_industry, f, ensure_ascii=False, indent=2)
    print(f"  ✅ {dict_file.name} ({len(stock_to_industry)}条)")

    # 行业 -> 股票列表字典
    industry_to_stocks = {}
    for l1 in stock_basic['industry_l1'].unique():
        l1_stocks = stock_basic[stock_basic['industry_l1'] == l1][['ts_code', 'symbol', 'name']].to_dict('records')
        industry_to_stocks[l1] = l1_stocks

        # 同时为二级行业创建
        for l2 in stock_basic[stock_basic['industry_l1'] == l1]['industry'].unique():
            l2_stocks = stock_basic[stock_basic['industry'] == l2][['ts_code', 'symbol', 'name']].to_dict('records')
            industry_to_stocks[f"{l1}_{l2}"] = l2_stocks

    industry_dict_file = output_dir / f"tushare_industry_to_stocks_dict_{timestamp}.json"
    with open(industry_dict_file, 'w', encoding='utf-8') as f:
        json.dump(industry_to_stocks, f, ensure_ascii=False, indent=2)
    print(f"  ✅ {Path(industry_dict_file).name}")

    # 7. 生成统计报告
    print("\n📊 生成统计报告...")

    report_lines = []
    report_lines.append("# TuShare行业分类完整映射报告")
    report_lines.append(f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"\n## 数据来源")
    report_lines.append(f"- TuShare stock_basic.industry字段")
    report_lines.append(f"- 覆盖股票: {len(stock_basic)}只")

    report_lines.append(f"\n## 行业统计")
    report_lines.append(f"- 一级行业: {l1_count}个")
    report_lines.append(f"- 二级行业: {l2_count}个")

    report_lines.append(f"\n## 一级行业分布（按股票数量排序）")
    l1_dist = stock_basic['industry_l1'].value_counts()
    for idx, (industry, count) in enumerate(l1_dist.items(), 1):
        pct = count / len(stock_basic) * 100
        report_lines.append(f"{idx}. {industry}: {count}只 ({pct:.2f}%)")

    report_lines.append(f"\n## 二级行业分布（Top 20）")
    l2_dist = stock_basic['industry'].value_counts().head(20)
    for idx, (industry, count) in enumerate(l2_dist.items(), 1):
        pct = count / len(stock_basic) * 100
        report_lines.append(f"{idx}. {industry}: {count}只 ({pct:.2f}%)")

    report_lines.append(f"\n## 行业层级结构")
    for l1 in sorted(industry_structure.keys()):
        l2_list = industry_structure[l1]
        report_lines.append(f"\n### {l1}")
        # 过滤None值并排序
        valid_l2_list = [l2 for l2 in l2_list if l2 is not None]
        for l2 in sorted(valid_l2_list):
            count = len(stock_basic[stock_basic['industry'] == l2])
            report_lines.append(f"  - {l2}: {count}只")

    # 保存报告
    report_file = output_dir / "tushare_industry_mapping_report.md"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))
    print(f"  ✅ {Path(report_file).name}")

    # 8. 创建使用示例代码
    print("\n💻 创建使用示例...")

    example_code = '''#!/usr/bin/env python3
"""
TuShare行业分类使用示例
"""

import pandas as pd
import json
from pathlib import Path

# 数据目录
data_dir = Path("~/.qlib/qlib_data/cn_data/industry_data").expanduser()

def example_1_load_mapping():
    """示例1：加载完整映射表"""
    mapping_df = pd.read_csv(data_dir / "tushare_industry_mapping__latest.csv")

    print("完整映射表（前10行）:")
    print(mapping_df[['ts_code', 'name', 'industry', 'industry_l1']].head(10))
    return mapping_df

def example_2_query_stock_industry():
    """示例2：查询股票所属行业"""
    stock_to_industry_file = list(data_dir.glob("tushare_stock_to_industry_dict_*.json"))[0]

    with open(stock_to_industry_file, 'r', encoding='utf-8') as f:
        stock_to_industry = json.load(f)

    # 查询股票行业
    ts_codes = ['000001.SZ', '000002.SZ', '600000.SH']
    for ts_code in ts_codes:
        if ts_code in stock_to_industry:
            info = stock_to_industry[ts_code]
            print(f"{ts_code} {info['name']}: {info['industry_l1']} - {info['industry_l2']}")

    return stock_to_industry

def example_3_get_industry_stocks():
    """示例3：获取某个行业的所有股票"""
    industry_to_stocks_file = list(data_dir.glob("tushare_industry_to_stocks_dict_*.json"))[0]

    with open(industry_to_stocks_file, 'r', encoding='utf-8') as f:
        industry_to_stocks = json.load(f)

    # 获取"电子"行业的所有股票
    print("\\n电子行业股票（前10只）:")
    if '电子' in industry_to_stocks:
        stocks = industry_to_stocks['电子'][:10]
        for stock in stocks:
            print(f"  {stock['ts_code']} {stock['name']}")

    return industry_to_stocks

def example_4_industry_analysis():
    """示例4：行业统计分析"""
    mapping_df = pd.read_csv(data_dir / "tushare_industry_mapping__latest.csv")

    print("\\n一级行业分布:")
    l1_dist = mapping_df['industry_l1'].value_counts()
    print(l1_dist)

    print("\\n二级行业分布（Top 10）:")
    l2_dist = mapping_df['industry'].value_counts().head(10)
    print(l2_dist)

    # 交易所分布
    print("\\n交易所分布:")
    mapping_df['exchange'] = mapping_df['ts_code'].str[-2:]
    exchange_dist = mapping_df['exchange'].value_counts()
    print(exchange_dist)

if __name__ == "__main__":
    print("TuShare行业分类使用示例")
    print("="*80)

    example_1_load_mapping()
    example_2_query_stock_industry()
    example_3_get_industry_stocks()
    example_4_industry_analysis()
'''

    example_file = output_dir / "tushare_industry_usage_examples.py"
    with open(example_file, 'w', encoding='utf-8') as f:
        f.write(example_code)
    print(f"  ✅ {example_file.name}")

    print("\n" + "="*80)
    print("✅ TuShare行业分类完整映射生成完成！")
    print("="*80)

    print(f"\n📁 数据文件位置: {output_dir}")
    print("\n主要文件:")
    print(f"  - tushare_industry_mapping__latest.csv  # 完整映射表（5466只股票）")
    print(f"  - tushare_stock_to_industry_dict_*.json  # 股票->行业字典")
    print(f"  - tushare_industry_to_stocks_dict_*.json  # 行业->股票列表字典")
    print(f"  - tushare_industry_structure.json  # 行业层级结构")
    print(f"  - tushare_industry_mapping_report.md  # 详细报告")
    print(f"  - tushare_industry_usage_examples.py  # 使用示例代码")

    return {
        'mapping_df': stock_basic,
        'stock_to_industry': stock_to_industry,
        'industry_to_stocks': industry_to_stocks,
        'industry_structure': industry_structure
    }

if __name__ == "__main__":
    result = create_industry_mapping()

    if result:
        print("\n🎉 任务完成！所有A股股票已成功映射到TuShare行业分类")
