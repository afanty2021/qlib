#!/usr/bin/env python3
"""
行业板块和概念板块数据下载工具

功能：
1. 下载所有行业板块数据（申万、证监会、中信）
2. 下载所有概念板块数据
3. 下载指数成分股数据
4. 保存为便于分析的格式

使用方法：
    python download_industry_data.py

或使用TuShare Token：
    export TUSHARE_TOKEN="your_token"
    python download_industry_data.py
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


class IndustryDataDownloader:
    """行业板块数据下载器"""

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
            output_dir = Path(__file__).parent / "industry_data"
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 初始化API客户端
        if QLIB_AVAILABLE:
            config = TuShareConfig(token=self.token)
            self.client = TuShareAPIClient(config)
            self.use_proxied_api = True
        else:
            import tushare as ts
            self.client = ts.pro_api(self.token)
            self.use_proxied_api = False

        print(f"✅ 初始化完成")
        print(f"   输出目录: {self.output_dir}")
        print(f"   API模式: {'Qlib封装' if self.use_proxied_api else '原生TuShare'}")

    def download_industry_classification(
        self,
        sources: List[str] = ["SW2021", "ZJH", "CITIC"],
        levels: List[str] = ["L1", "L2", "L3"]
    ) -> Dict[str, pd.DataFrame]:
        """
        下载行业分类数据

        Args:
            sources: 行业分类来源列表
            levels: 行业级别列表

        Returns:
            行业分类数据字典
        """
        print("\n" + "="*80)
        print("📥 开始下载行业分类数据")
        print("="*80)

        industry_data = {}

        for source in sources:
            print(f"\n📊 下载 {source} 行业分类...")

            for level in levels:
                key = f"{source}_{level}"
                print(f"   - {level} 级别...", end=" ")

                try:
                    # 使用原生TuShare API（更稳定）
                    import tushare as ts
                    ts_client = ts.pro_api(self.token)

                    # 使用index_classify接口获取行业分类
                    df = ts_client.index_classify(
                        level=level,
                        source=source
                    )

                    if df is not None and not df.empty:
                        industry_data[key] = df
                        print(f"✅ {len(df)} 条记录")
                    else:
                        print(f"⚠️ 无数据")

                    # 避免API频率限制
                    time.sleep(0.2)

                except Exception as e:
                    print(f"❌ 失败: {str(e)}")

        print(f"\n✅ 行业分类下载完成，共获取 {len(industry_data)} 个分类")

        return industry_data

    def download_concept(self) -> pd.DataFrame:
        """
        下载概念板块数据

        Returns:
            概念板块DataFrame
        """
        print("\n" + "="*80)
        print("📥 开始下载概念板块数据")
        print("="*80)

        print("\n📊 下载概念板块列表...", end=" ")

        try:
            # 使用原生TuShare API（更稳定）
            import tushare as ts
            ts_client = ts.pro_api(self.token)
            concept_df = ts_client.concept()

            if concept_df is not None and not concept_df.empty:
                print(f"✅ {len(concept_df)} 个概念板块")
                return concept_df
            else:
                print("⚠️ 无数据")
                return pd.DataFrame()

        except Exception as e:
            print(f"❌ 失败: {str(e)}")
            return pd.DataFrame()

    def download_concept_members(
        self,
        concept_df: pd.DataFrame,
        max_concepts: int = None
    ) -> Dict[str, pd.DataFrame]:
        """
        下载概念板块成分股

        Args:
            concept_df: 概念板块DataFrame
            max_concepts: 最多下载概念数量（None表示全部）

        Returns:
            概念成分股字典
        """
        print("\n" + "="*80)
        print("📥 开始下载概念板块成分股")
        print("="*80)

        if concept_df.empty:
            print("⚠️ 概念板块数据为空")
            return {}

        concept_members = {}

        # 获取概念ID列表
        if 'id' in concept_df.columns:
            concept_ids = concept_df['id'].unique()
        elif 'concept_code' in concept_df.columns:
            concept_ids = concept_df['concept_code'].unique()
        else:
            print("⚠️ 未找到概念ID列")
            return {}

        # 限制下载数量
        if max_concepts:
            concept_ids = concept_ids[:max_concepts]

        print(f"\n📊 共 {len(concept_ids)} 个概念板块")

        for i, concept_id in enumerate(concept_ids, 1):
            concept_name = concept_df[concept_df['id'] == concept_id]['concept_name'].values[0] if 'concept_name' in concept_df.columns else concept_id
            print(f"   [{i}/{len(concept_ids)}] {concept_name} ({concept_id})...", end=" ")

            try:
                # TuShare没有直接的概念成分股接口
                # 需要通过其他方式获取
                print("⚠️ 暂不支持（需要其他接口）")
                time.sleep(0.1)

            except Exception as e:
                print(f"❌ 失败: {str(e)}")

        print(f"\n✅ 概念成分股下载完成")

        return concept_members

    def download_index_members(
        self,
        index_codes: List[str] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        下载指数成分股数据

        Args:
            index_codes: 指数代码列表

        Returns:
            指数成分股字典
        """
        print("\n" + "="*80)
        print("📥 开始下载指数成分股数据")
        print("="*80)

        if index_codes is None:
            # 默认主要指数
            index_codes = [
                "000001.SH",  # 上证综指
                "399001.SZ",  # 深证成指
                "000300.SH",  # 沪深300
                "000905.SH",  # 中证500
                "000016.SH",  # 上证50
                "399006.SZ",  # 创业板指
                "000688.SH",  # 科创50
                "000903.SH",  # 中证100
                "000852.SH",  # 中证1000
            ]

        print(f"\n📊 共 {len(index_codes)} 个指数")

        index_members = {}

        for i, index_code in enumerate(index_codes, 1):
            print(f"   [{i}/{len(index_codes)}] {index_code}...", end=" ")

            try:
                # 使用原生TuShare API（更稳定）
                import tushare as ts
                ts_client = ts.pro_api(self.token)
                df = ts_client.index_member(index_code=index_code)

                if df is not None and not df.empty:
                    index_members[index_code] = df
                    print(f"✅ {len(df)} 只成分股")
                else:
                    print("⚠️ 无数据")

                time.sleep(0.2)

            except Exception as e:
                print(f"❌ 失败: {str(e)}")

        print(f"\n✅ 指数成分股下载完成，共 {len(index_members)} 个指数")

        return index_members

    def download_index_classify(
        self,
        index_codes: List[str] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        下载指数行业分类数据

        Args:
            index_codes: 指数代码列表

        Returns:
            指数行业分类字典
        """
        print("\n" + "="*80)
        print("📥 开始下载指数行业分类数据")
        print("="*80)

        if index_codes is None:
            index_codes = ["000300.SH", "000905.SH", "000016.SH"]

        print(f"\n📊 共 {len(index_codes)} 个指数")

        index_classify = {}
        sources = ["SW2021"]
        levels = ["L1", "L2"]

        for source in sources:
            for level in levels:
                key = f"{source}_{level}"
                print(f"\n   - {source} {level}...", end=" ")

                try:
                    # 使用原生TuShare API（更稳定）
                    import tushare as ts
                    ts_client = ts.pro_api(self.token)
                    df = ts_client.index_classify(
                        level=level,
                        source=source
                    )

                    if df is not None and not df.empty:
                        index_classify[key] = df
                        print(f"✅ {len(df)} 条记录")
                    else:
                        print("⚠️ 无数据")

                    time.sleep(0.2)

                except Exception as e:
                    print(f"❌ 失败: {str(e)}")

        print(f"\n✅ 指数行业分类下载完成")

        return index_classify

    def save_data(
        self,
        industry_data: Dict[str, pd.DataFrame],
        concept_data: pd.DataFrame = None,
        index_members: Dict[str, pd.DataFrame] = None,
        index_classify: Dict[str, pd.DataFrame] = None
    ):
        """
        保存下载的数据

        Args:
            industry_data: 行业分类数据
            concept_data: 概念板块数据
            index_members: 指数成分股数据
            index_classify: 指数行业分类数据
        """
        print("\n" + "="*80)
        print("💾 开始保存数据")
        print("="*80)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 保存行业分类数据
        if industry_data:
            print(f"\n📁 保存行业分类数据...")

            # 保存单个文件
            all_industry = pd.concat(industry_data.values(), ignore_index=True)
            industry_file = self.output_dir / f"industry_all_{timestamp}.csv"
            all_industry.to_csv(industry_file, index=False, encoding='utf-8-sig')
            print(f"   ✅ {industry_file.name}")

            # 保存分类到不同文件
            for key, df in industry_data.items():
                file = self.output_dir / f"industry_{key}_{timestamp}.csv"
                df.to_csv(file, index=False, encoding='utf-8-sig')
                print(f"   ✅ {file.name} ({len(df)} 条)")

            # 保存为JSON
            json_file = self.output_dir / f"industry_all_{timestamp}.json"
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(
                    {k: v.to_dict('records') for k, v in industry_data.items()},
                    f,
                    ensure_ascii=False,
                    indent=2
                )
            print(f"   ✅ {json_file.name}")

        # 保存概念板块数据
        if concept_data is not None and not concept_data.empty:
            print(f"\n📁 保存概念板块数据...")
            concept_file = self.output_dir / f"concept_{timestamp}.csv"
            concept_data.to_csv(concept_file, index=False, encoding='utf-8-sig')
            print(f"   ✅ {concept_file.name} ({len(concept_data)} 条)")

            # 保存为JSON
            json_file = self.output_dir / f"concept_{timestamp}.json"
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(concept_data.to_dict('records'), f, ensure_ascii=False, indent=2)
            print(f"   ✅ {json_file.name}")

        # 保存指数成分股数据
        if index_members:
            print(f"\n📁 保存指数成分股数据...")

            # 合并所有指数
            all_members = []
            for index_code, df in index_members.items():
                df_copy = df.copy()
                df_copy['index_code'] = index_code
                all_members.append(df_copy)

            if all_members:
                all_members_df = pd.concat(all_members, ignore_index=True)
                members_file = self.output_dir / f"index_members_all_{timestamp}.csv"
                all_members_df.to_csv(members_file, index=False, encoding='utf-8-sig')
                print(f"   ✅ {members_file.name} ({len(all_members_df)} 条)")

                # 保存为JSON
                json_file = self.output_dir / f"index_members_all_{timestamp}.json"
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(all_members_df.to_dict('records'), f, ensure_ascii=False, indent=2)
                print(f"   ✅ {json_file.name}")

            # 单独保存每个指数
            for index_code, df in index_members.items():
                code_safe = index_code.replace('.', '_')
                file = self.output_dir / f"index_members_{code_safe}_{timestamp}.csv"
                df.to_csv(file, index=False, encoding='utf-8-sig')
                print(f"   ✅ {file.name} ({len(df)} 条)")

        # 保存指数行业分类
        if index_classify:
            print(f"\n📁 保存指数行业分类数据...")

            for key, df in index_classify.items():
                file = self.output_dir / f"index_classify_{key}_{timestamp}.csv"
                df.to_csv(file, index=False, encoding='utf-8-sig')
                print(f"   ✅ {file.name} ({len(df)} 条)")

        # 创建最新版本链接（不带时间戳）
        print(f"\n📁 创建最新版本链接...")
        self._create_latest_links()

        print(f"\n✅ 所有数据已保存到: {self.output_dir}")

    def _create_latest_links(self):
        """创建指向最新数据的链接（复制文件）"""
        # 找到最新的文件
        csv_files = list(self.output_dir.glob("*.csv"))
        json_files = list(self.output_dir.glob("*.json"))

        # 复制最新文件为不含时间戳的版本
        for file in csv_files:
            if '_latest' not in file.name:
                latest_name = file.stem.split('_')[0] + '_' + '_latest.csv'
                latest_file = self.output_dir / latest_name
                import shutil
                shutil.copy2(file, latest_file)

        for file in json_files:
            if '_latest' not in file.name:
                latest_name = file.stem.split('_')[0] + '_' + '_latest.json'
                latest_file = self.output_dir / latest_name
                import shutil
                shutil.copy2(file, latest_file)

    def generate_summary_report(self) -> str:
        """
        生成数据摘要报告

        Returns:
            报告文本
        """
        print("\n" + "="*80)
        print("📊 生成数据摘要报告")
        print("="*80)

        report_lines = []
        report_lines.append("# 行业板块数据摘要报告")
        report_lines.append(f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"\n数据目录: {self.output_dir}")

        # 统计文件
        csv_files = list(self.output_dir.glob("*.csv"))
        json_files = list(self.output_dir.glob("*.json"))

        report_lines.append(f"\n## 文件统计")
        report_lines.append(f"- CSV文件: {len(csv_files)}")
        report_lines.append(f"- JSON文件: {len(json_files)}")

        # 行业分类统计
        industry_files = [f for f in csv_files if f.name.startswith('industry_') and 'all' not in f.name]
        if industry_files:
            report_lines.append(f"\n## 行业分类数据 ({len(industry_files)} 个文件)")
            for file in sorted(industry_files):
                df = pd.read_csv(file)
                parts = file.stem.replace('industry_', '').split('_')
                source, level = parts[0], parts[1] if len(parts) > 1 else 'N/A'
                report_lines.append(f"- {source} {level}: {len(df)} 条")

        # 概念板块统计
        concept_files = [f for f in csv_files if f.name.startswith('concept_')]
        if concept_files:
            report_lines.append(f"\n## 概念板块数据")
            for file in concept_files:
                df = pd.read_csv(file)
                report_lines.append(f"- 概念板块: {len(df)} 个")

        # 指数成分股统计
        member_files = [f for f in csv_files if 'index_members_' in f.name and 'all' in f.name]
        if member_files:
            report_lines.append(f"\n## 指数成分股数据")
            for file in member_files:
                df = pd.read_csv(file)
                if 'index_code' in df.columns:
                    index_counts = df['index_code'].value_counts()
                    report_lines.append(f"- 总成分股: {len(df)} 条")
                    report_lines.append(f"- 覆盖指数: {len(index_counts)} 个")
                    for idx_code, count in index_counts.head(10).items():
                        report_lines.append(f"  - {idx_code}: {count} 只")

        # 保存报告
        report_file = self.output_dir / "data_summary_report.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))

        print(f"\n✅ 报告已保存: {report_file.name}")

        return '\n'.join(report_lines)

    def run_full_download(self):
        """执行完整下载流程"""
        print("\n" + "="*80)
        print("🚀 开始完整下载流程")
        print("="*80)

        # 1. 下载行业分类
        industry_data = self.download_industry_classification()

        # 2. 下载概念板块
        concept_data = self.download_concept()

        # 3. 下载指数成分股
        index_members = self.download_index_members()

        # 4. 下载指数行业分类
        index_classify = self.download_index_classify()

        # 5. 保存所有数据
        self.save_data(
            industry_data=industry_data,
            concept_data=concept_data,
            index_members=index_members,
            index_classify=index_classify
        )

        # 6. 生成摘要报告
        report = self.generate_summary_report()

        print("\n" + "="*80)
        print("✅ 完整下载流程完成！")
        print("="*80)

        return {
            'industry_data': industry_data,
            'concept_data': concept_data,
            'index_members': index_members,
            'index_classify': index_classify
        }


def main():
    """主函数"""
    # 检查Token
    token = os.getenv("TUSHARE_TOKEN")
    if not token:
        print("❌ 请设置 TUSHARE_TOKEN 环境变量")
        print("   export TUSHARE_TOKEN='your_token_here'")
        sys.exit(1)

    print("🎯 TuShare 行业板块数据下载工具")
    print("="*80)

    # 创建下载器
    downloader = IndustryDataDownloader(token=token)

    # 执行下载
    try:
        result = downloader.run_full_download()

        print("\n📊 下载摘要:")
        print(f"  - 行业分类: {len(result['industry_data'])} 个")
        print(f"  - 概念板块: {len(result['concept_data']) if result['concept_data'] is not None else 0} 个")
        print(f"  - 指数成分股: {len(result['index_members'])} 个指数")
        print(f"  - 指数行业分类: {len(result['index_classify'])} 个")

        print("\n✅ 所有数据下载完成！")

    except Exception as e:
        print(f"\n❌ 下载失败: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
