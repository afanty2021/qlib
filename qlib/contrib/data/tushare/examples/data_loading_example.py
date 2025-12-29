#!/usr/bin/env python3
"""
行业数据加载示例

演示如何加载和使用下载的行业板块数据进行量化投资分析
"""

import os
import sys
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional

# 添加qlib路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))


class IndustryDataManager:
    """行业数据管理器 - 用于加载和管理行业板块数据"""

    def __init__(self, data_dir: str = None):
        """
        初始化数据管理器

        Args:
            data_dir: 行业数据目录路径
        """
        if data_dir is None:
            data_dir = Path(__file__).parent.parent / "industry_data"

        self.data_dir = Path(data_dir)

        print(f"✅ 行业数据管理器初始化完成")
        print(f"   数据目录: {self.data_dir}")

    def load_industry_classification(
        self,
        source: str = "SW2021",
        level: str = "L1"
    ) -> pd.DataFrame:
        """
        加载行业分类数据

        Args:
            source: 行业分类来源 (SW2021, ZJH, CITIC)
            level: 行业级别 (L1, L2, L3)

        Returns:
            行业分类DataFrame
        """
        # 查找最新的行业分类文件
        pattern = f"industry_{source}_{level}_*.csv"
        files = list(self.data_dir.glob(pattern))

        if not files:
            raise FileNotFoundError(f"未找到行业分类文件: {pattern}")

        # 使用最新的文件
        latest_file = max(files, key=lambda f: f.stat().st_mtime)
        df = pd.read_csv(latest_file)

        print(f"✅ 加载 {source} {level} 行业分类: {len(df)} 条记录")

        return df

    def load_concept_data(self) -> pd.DataFrame:
        """
        加载概念板块数据

        Returns:
            概念板块DataFrame
        """
        # 查找最新的概念板块文件
        pattern = "concept_*.csv"
        files = list(self.data_dir.glob(pattern))

        if not files:
            raise FileNotFoundError(f"未找到概念板块文件: {pattern}")

        # 使用最新的文件
        latest_file = max(files, key=lambda f: f.stat().st_mtime)
        df = pd.read_csv(latest_file)

        print(f"✅ 加载概念板块数据: {len(df)} 条记录")

        return df

    def load_all_industries(self) -> Dict[str, pd.DataFrame]:
        """
        加载所有行业分类数据

        Returns:
            所有行业分类的字典
        """
        all_data = {}

        sources = ["SW2021", "ZJH", "CITIC"]
        levels = ["L1", "L2", "L3"]

        for source in sources:
            for level in levels:
                try:
                    key = f"{source}_{level}"
                    all_data[key] = self.load_industry_classification(source, level)
                except FileNotFoundError:
                    print(f"⚠️ 未找到 {source} {level} 数据")
                    continue

        print(f"✅ 总共加载 {len(all_data)} 个行业分类")

        return all_data

    def get_industry_mapping(
        self,
        source: str = "SW2021",
        level: str = "L1"
    ) -> Dict[str, str]:
        """
        获取行业代码到行业名称的映射

        Args:
            source: 行业分类来源
            level: 行业级别

        Returns:
            行业代码到名称的映射字典
        """
        df = self.load_industry_classification(source, level)

        # 假设DataFrame包含 industry_code 和 industry_name 列
        if 'industry_code' in df.columns and 'industry_name' in df.columns:
            mapping = dict(zip(df['industry_code'], df['industry_name']))
        elif 'index_code' in df.columns and 'index_name' in df.columns:
            mapping = dict(zip(df['index_code'], df['index_name']))
        else:
            raise ValueError("DataFrame中未找到行业代码和名称列")

        print(f"✅ 创建行业映射: {len(mapping)} 个行业")

        return mapping

    def search_industries(
        self,
        keyword: str,
        source: str = "SW2021",
        level: str = "L1"
    ) -> pd.DataFrame:
        """
        搜索包含关键词的行业

        Args:
            keyword: 搜索关键词
            source: 行业分类来源
            level: 行业级别

        Returns:
            匹配的行业DataFrame
        """
        df = self.load_industry_classification(source, level)

        # 在行业名称中搜索
        name_col = 'industry_name' if 'industry_name' in df.columns else 'index_name'
        matched = df[df[name_col].str.contains(keyword, na=False)]

        print(f"✅ 搜索 '{keyword}': 找到 {len(matched)} 个匹配行业")

        return matched

    def get_industry_tree(
        self,
        source: str = "SW2021"
    ) -> pd.DataFrame:
        """
        获取行业分层结构树

        Args:
            source: 行业分类来源

        Returns:
            包含层级关系的DataFrame
        """
        # 加载所有级别
        l1 = self.load_industry_classification(source, "L1")
        l2 = self.load_industry_classification(source, "L2")
        l3 = self.load_industry_classification(source, "L3")

        # 合并数据
        tree = pd.concat([
            l1.assign(level=1),
            l2.assign(level=2),
            l3.assign(level=3)
        ], ignore_index=True)

        print(f"✅ 构建行业树: {len(tree)} 个节点")

        return tree


def build_stock_industry_mapping(
    stock_list: List[str],
    industry_data: pd.DataFrame
) -> pd.DataFrame:
    """
    构建股票到行业的映射关系

    注意：这是一个示例函数，实际应用中需要从TuShare API获取
    股票的实际行业分类信息

    Args:
        stock_list: 股票代码列表
        industry_data: 行业分类数据

    Returns:
        股票-行业映射DataFrame
    """
    print("⚠️ 注意：这是示例函数，实际需要从TuShare获取股票行业映射")

    # 示例：随机分配行业（实际应用中应该从API获取）
    import random

    industry_codes = industry_data['industry_code'].unique() if 'industry_code' in industry_data.columns else []

    mappings = []
    for stock in stock_list:
        # 随机分配一个行业（仅用于演示）
        industry = random.choice(industry_codes) if industry_codes else "UNKNOWN"
        mappings.append({
            'stock_code': stock,
            'industry_code': industry
        })

    df = pd.DataFrame(mappings)

    print(f"✅ 构建股票-行业映射: {len(df)} 只股票")

    return df


# ============================================================
# 示例1: 基础数据加载
# ============================================================

def example_1_basic_loading():
    """示例1: 基础数据加载"""
    print("\n" + "="*80)
    print("示例1: 基础数据加载")
    print("="*80)

    # 初始化数据管理器
    manager = IndustryDataManager()

    # 加载申万一级行业
    print("\n📊 加载申万一级行业分类...")
    industry_l1 = manager.load_industry_classification("SW2021", "L1")
    print(f"   一级行业数量: {len(industry_l1)}")
    print(f"   前5个行业:")
    print(industry_l1.head().to_string(index=False))

    # 加载概念板块
    print("\n📊 加载概念板块数据...")
    concept = manager.load_concept_data()
    print(f"   概念板块数量: {len(concept)}")
    print(f"   前5个概念:")
    print(concept.head().to_string(index=False))


# ============================================================
# 示例2: 行业映射和搜索
# ============================================================

def example_2_mapping_and_search():
    """示例2: 行业映射和搜索"""
    print("\n" + "="*80)
    print("示例2: 行业映射和搜索")
    print("="*80)

    manager = IndustryDataManager()

    # 创建行业代码映射
    print("\n📊 创建行业代码映射...")
    industry_map = manager.get_industry_mapping("SW2021", "L1")

    print(f"   前10个映射:")
    for i, (code, name) in enumerate(list(industry_map.items())[:10]):
        print(f"   {code}: {name}")

    # 搜索特定行业
    print("\n🔍 搜索包含'银行'的行业...")
    bank_industries = manager.search_industries("银行", "SW2021", "L1")
    print(bank_industries.to_string(index=False))

    print("\n🔍 搜索包含'科技'的行业...")
    tech_industries = manager.search_industries("科技", "SW2021", "L1")
    print(tech_industries.to_string(index=False))


# ============================================================
# 示例3: 行业层级结构
# ============================================================

def example_3_industry_hierarchy():
    """示例3: 行业层级结构"""
    print("\n" + "="*80)
    print("示例3: 行业层级结构")
    print("="*80)

    manager = IndustryDataManager()

    # 构建行业树
    print("\n📊 构建申万行业层级结构...")
    industry_tree = manager.get_industry_tree("SW2021")

    # 统计各级行业数量
    print("\n   各级行业统计:")
    for level in [1, 2, 3]:
        count = len(industry_tree[industry_tree['level'] == level])
        print(f"   L{level}: {count} 个行业")

    # 查看完整结构
    print("\n   行业层级结构预览:")
    print(industry_tree.head(20).to_string(index=False))


# ============================================================
# 示例4: 构建股票-行业映射
# ============================================================

def example_4_stock_industry_mapping():
    """示例4: 构建股票-行业映射"""
    print("\n" + "="*80)
    print("示例4: 构建股票-行业映射")
    print("="*80)

    manager = IndustryDataManager()

    # 加载行业数据
    industry_l1 = manager.load_industry_classification("SW2021", "L1")

    # 示例股票列表
    stock_list = [
        "000001.SZ", "000002.SZ", "600000.SH", "600036.SH",
        "000858.SZ", "002594.SZ", "601318.SH", "601398.SH"
    ]

    print(f"\n📊 为 {len(stock_list)} 只股票构建行业映射...")

    # 构建映射
    stock_industry_df = build_stock_industry_mapping(stock_list, industry_l1)

    # 合并行业名称
    industry_map = manager.get_industry_mapping("SW2021", "L1")
    stock_industry_df['industry_name'] = stock_industry_df['industry_code'].map(industry_map)

    print("\n   股票-行业映射结果:")
    print(stock_industry_df.to_string(index=False))


# ============================================================
# 主函数
# ============================================================

def main():
    """主函数 - 运行所有示例"""
    print("\n🎯 行业数据加载示例")
    print("="*80)
    print("本示例演示如何加载和使用行业板块数据")
    print("="*80)

    try:
        # 示例1: 基础数据加载
        example_1_basic_loading()

        # 示例2: 行业映射和搜索
        example_2_mapping_and_search()

        # 示例3: 行业层级结构
        example_3_industry_hierarchy()

        # 示例4: 股票-行业映射
        example_4_stock_industry_mapping()

        print("\n" + "="*80)
        print("✅ 所有示例运行完成！")
        print("="*80)

        print("\n💡 使用建议:")
        print("   1. 确保已运行 download_industry_data.py 下载数据")
        print("   2. 根据实际需求修改 IndustryDataManager 类")
        print("   3. 使用 TuShare API 获取真实的股票-行业映射")
        print("   4. 将行业数据集成到您的量化策略中")

    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
