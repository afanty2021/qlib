#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的Qlib ALSTM模型训练演示

该脚本使用Qlib的默认数据进行ALSTM模型训练，并生成基础的可视化报告。
"""

import warnings
warnings.filterwarnings("ignore")

import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

# 设置matplotlib后端
plt.switch_backend('Agg')  # 使用非交互式后端

# 导入Qlib
import qlib
from qlib.constant import REG_CN
from qlib.utils import init_instance_by_config
from qlib.workflow import R
from qlib.workflow.record_temp import SignalRecord, PortAnaRecord, SigAnaRecord
from qlib.tests.data import GetData
from qlib.tests.config import CSI300_BENCH

def main():
    print("=" * 60)
    print("🚀 Qlib ALSTM 模型训练演示")
    print("=" * 60)

    # 1. 环境初始化
    print("📊 正在初始化Qlib环境...")
    provider_uri = "~/.qlib/qlib_data/cn_data"

    # 初始化Qlib
    try:
        GetData().qlib_data(target_dir=provider_uri, region=REG_CN, exists_skip=True)
        qlib.init(provider_uri=provider_uri, region=REG_CN)
        print("✅ Qlib环境初始化完成")
    except Exception as e:
        print(f"❌ Qlib初始化失败: {e}")
        return

    # 2. 创建ALSTM配置
    print("⚙️ 正在创建ALSTM模型配置...")

    model_config = {
        "class": "ALSTM",
        "module_path": "qlib.contrib.model.pytorch_alstm_ts",
        "kwargs": {
            "d_feat": 20,
            "hidden_size": 64,
            "num_layers": 2,
            "dropout": 0.0,
            "n_epochs": 20,  # 减少轮数以便快速演示
            "lr": 1e-3,
            "early_stop": 5,
            "batch_size": 800,
            "metric": "loss",
            "loss": "mse",
            "n_jobs": 4,
            "GPU": -1,  # 使用CPU
            "rnn_type": "GRU",
        }
    }

    dataset_config = {
        "class": "TSDatasetH",
        "module_path": "qlib.data.dataset",
        "kwargs": {
            "handler": {
                "class": "Alpha158",
                "module_path": "qlib.contrib.data.handler",
                "kwargs": {
                    "start_time": "2017-01-01",
                    "end_time": "2020-08-01",
                    "fit_start_time": "2017-01-01",
                    "fit_end_time": "2018-12-31",
                    "instruments": "csi300",
                }
            },
            "segments": {
                "train": ("2017-01-01", "2018-12-31"),
                "valid": ("2019-01-01", "2019-12-31"),
                "test": ("2020-01-01", "2020-08-01")
            },
            "step_len": 20
        }
    }

    # 3. 初始化模型和数据集
    try:
        model = init_instance_by_config(model_config)
        dataset = init_instance_by_config(dataset_config)
        print("✅ 模型和数据集初始化完成")
    except Exception as e:
        print(f"❌ 模型初始化失败: {e}")
        return

    # 4. 训练模型
    print("🎯 正在开始模型训练...")
    experiment_name = f"alstm_demo_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    try:
        with R.start(experiment_name=experiment_name):
            # 训练模型
            print("🔄 训练中...")
            model.fit(dataset)
            print("✅ 模型训练完成")

            # 生成预测信号
            print("📊 生成预测信号...")
            recorder = R.get_recorder()
            sr = SignalRecord(model, dataset, recorder)
            sr.generate()

            # 信号分析
            print("📈 信号分析...")
            sar = SigAnaRecord(recorder)
            sar.generate()

            # 回测分析
            print("🎯 回测分析...")
            port_analysis_config = {
                "strategy": {
                    "class": "TopkDropoutStrategy",
                    "module_path": "qlib.contrib.strategy.signal_strategy",
                    "kwargs": {
                        "signal": (model, dataset),
                        "topk": 50,
                        "n_drop": 5,
                    },
                },
                "backtest": {
                    "start_time": "2020-01-01",
                    "end_time": "2020-08-01",
                    "account": 100000000,
                    "benchmark": CSI300_BENCH,
                    "exchange_kwargs": {
                        "freq": "day",
                        "limit_threshold": 0.095,
                        "deal_price": "close",
                        "open_cost": 0.0005,
                        "close_cost": 0.0015,
                        "min_cost": 5,
                    },
                },
                "executor": {
                    "class": "SimulatorExecutor",
                    "module_path": "qlib.backtest.executor",
                    "kwargs": {
                        "time_per_step": "day",
                        "generate_portfolio_metrics": True,
                    },
                },
            }

            par = PortAnaRecord(recorder, port_analysis_config, "day")
            par.generate()

            print("✅ 回测分析完成")

            # 5. 生成简单的可视化
            generate_simple_visualization(recorder, experiment_name)

            # 6. 打印结果摘要
            print_results_summary(experiment_name)

    except Exception as e:
        print(f"❌ 训练过程失败: {e}")
        import traceback
        traceback.print_exc()

def generate_simple_visualization(recorder, experiment_name):
    """生成简单的可视化"""
    print("🎨 正在生成可视化...")

    try:
        # 获取预测结果
        pred_df = recorder.load_object("pred.pkl")

        # 创建图表
        fig, axes = plt.subplots(2, 2, figsize=(12, 8))
        fig.suptitle(f'ALSTM Training Results - {experiment_name}', fontsize=14)

        # 1. 预测信号分布
        ax1 = axes[0, 0]
        if hasattr(pred_df, 'values'):
            pred_values = pred_df.values.flatten()
            ax1.hist(pred_values, bins=30, alpha=0.7, color='skyblue')
            ax1.set_title('Prediction Distribution')
            ax1.set_xlabel('Prediction Value')
            ax1.set_ylabel('Frequency')

        # 2. 时间序列样本
        ax2 = axes[0, 1]
        if hasattr(pred_df, 'values') and len(pred_df) > 100:
            sample_data = pred_df.values[:100].flatten()
            ax2.plot(sample_data, color='coral', linewidth=1)
            ax2.set_title('Prediction Time Series (First 100 samples)')
            ax2.set_xlabel('Time Step')
            ax2.set_ylabel('Prediction')

        # 3. 预测值散点图
        ax3 = axes[1, 0]
        if hasattr(pred_df, 'values'):
            pred_values = pred_df.values.flatten()[:1000]
            ax3.scatter(range(len(pred_values)), pred_values, alpha=0.5, s=1)
            ax3.set_title('Prediction Scatter Plot')
            ax3.set_xlabel('Sample Index')
            ax3.set_ylabel('Prediction Value')

        # 4. 统计信息
        ax4 = axes[1, 1]
        ax4.axis('off')

        stats_text = f"""
        Model Configuration:
        - Model: ALSTM
        - Features: 20
        - Hidden Size: 64
        - Layers: 2
        - Time Window: 20

        Dataset Info:
        - Training: 2017-2018
        - Validation: 2019
        - Test: 2020
        - Universe: CSI300

        Performance:
        - Top-K Strategy: 50 stocks
        - Initial Capital: 100M CNY
        - Rebalance: Daily
        - Status: Completed

        Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """

        ax4.text(0.05, 0.95, stats_text, transform=ax4.transAxes,
                fontsize=9, verticalalignment='top', fontfamily='monospace')

        plt.tight_layout()

        # 保存图表
        os.makedirs("alstm_results", exist_ok=True)
        chart_path = f"alstm_results/{experiment_name}_results.png"
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()  # 关闭图表以节省内存

        print(f"📊 可视化已保存: {chart_path}")

    except Exception as e:
        print(f"⚠️ 可视化生成失败: {e}")

def print_results_summary(experiment_name):
    """打印结果摘要"""
    print("\n" + "=" * 60)
    print("🎉 ALSTM模型训练完成!")
    print("=" * 60)

    print(f"\n📊 实验信息:")
    print(f"   • 实验名称: {experiment_name}")
    print(f"   • 模型类型: ALSTM (Attention-based LSTM)")
    print(f"   • 训练数据: 2017-2018年沪深300")
    print(f"   • 测试数据: 2020年")

    print(f"\n🎯 模型配置:")
    print(f"   • 特征维度: 20 (Alpha158)")
    print(f"   • 隐藏层大小: 64")
    print(f"   • LSTM层数: 2")
    print(f"   • 时间窗口: 20天")

    print(f"\n💼 策略配置:")
    print(f"   • 选股策略: TopK-Dropout")
    print(f"   • 持仓数量: 50只")
    print(f"   • 调仓频率: 每日")
    print(f"   • 初始资金: 1亿元")

    print(f"\n📁 生成文件:")
    print(f"   • 实验结果: ./mlruns/{experiment_name}")
    print(f"   • 可视化图表: ./alstm_results/{experiment_name}_results.png")

    print(f"\n🔬 模型特色:")
    print(f"   1. 注意力机制增强的LSTM网络")
    print(f"   2. Alpha158因子特征工程")
    print(f"   3. 时间序列预测建模")
    print(f"   4. 动态选股策略")
    print(f"   5. 完整的回测评估框架")

    print("\n" + "=" * 60)
    print("✅ 请查看生成的可视化图表和MLflow实验记录")
    print("=" * 60)

if __name__ == "__main__":
    main()