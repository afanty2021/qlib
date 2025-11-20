#  Copyright (c) Microsoft Corporation.
#  Licensed under the MIT License.

"""
Qlib 代码工作流示例

这是 Qlib 的完整工作流示例，展示了如何通过代码（而非配置文件）
来构建完整的量化研究流程。

=== 两种接口方式 ===

Qlib 提供了两种不同的使用接口：

1) 配置文件接口：
   - 用户可以通过简单的 YAML 配置文件定义量化研究工作流
   - 使用方式：`qrun XXX.yaml`
   - 优点：配置简单、易于分享、适合标准化流程

2) 代码构建接口：
   - Qlib 采用模块化设计，支持像搭积木一样用代码创建研究工作流
   - 本文件就是这种接口的完整示例
   - 优点：灵活性高、易于调试、适合定制化研究

=== 工作流程概述 ===

本示例涵盖完整的量化研究流程：
1. 环境初始化：数据准备和 Qlib 配置
2. 模型训练：使用 LightGBM 进行机器学习建模
3. 信号生成：基于训练好的模型生成交易信号
4. 信号分析：评估信号的预测能力
5. 回测分析：基于信号进行历史回测
6. 结果评估：生成详细的业绩分析报告

=== 主要组件说明 ===

- GetData: 数据下载和准备工具
- Model: 机器学习模型（示例使用 LightGBM）
- Dataset: 数据集处理和管理
- Strategy: 交易策略实现
- Executor: 交易执行器
- Recorder: 实验记录和结果保存

=== 使用指南 ===

运行方式：
```bash
cd examples
python workflow_by_code.py
```

自定义修改：
- 修改数据源：更改 provider_uri 和 region 参数
- 更换模型：在 CSI300_GBDT_TASK 中修改模型配置
- 调整策略：修改 port_analysis_config 中的策略参数
- 扩展分析：添加自定义的分析模块

注意事项：
- 确保有足够的磁盘空间存储数据
- 首次运行会自动下载和准备数据
- 可以根据需要调整时间范围和股票池
"""

import qlib
from qlib.constant import REG_CN
from qlib.utils import init_instance_by_config, flatten_dict
from qlib.workflow import R
from qlib.workflow.record_temp import SignalRecord, PortAnaRecord, SigAnaRecord
from qlib.tests.data import GetData
from qlib.tests.config import CSI300_BENCH, CSI300_GBDT_TASK


if __name__ == "__main__":
    # ==================== 环境初始化 ====================

    # 使用默认数据源配置
    provider_uri = "~/.qlib/qlib_data/cn_data"  # 数据存储目录

    # 自动下载和准备数据（如果不存在）
    # GetData 会检查本地数据，如果存在则跳过下载
    GetData().qlib_data(target_dir=provider_uri, region=REG_CN, exists_skip=True)

    # 初始化 Qlib 环境
    # 设置数据源路径和区域（中国A股市场）
    qlib.init(provider_uri=provider_uri, region=REG_CN)

    # ==================== 模型和数据集准备 ====================

    # 根据配置初始化机器学习模型
    # CSI300_GBDT_TASK 定义了使用 LightGBM 的完整配置
    model = init_instance_by_config(CSI300_GBDT_TASK["model"])

    # 根据配置初始化数据集
    # 数据集包含特征工程和标签处理的完整流程
    dataset = init_instance_by_config(CSI300_GBDT_TASK["dataset"])

    # ==================== 回测配置 ====================

    # 构建完整的回测分析配置
    port_analysis_config = {
        # 交易执行器配置
        "executor": {
            "class": "SimulatorExecutor",                    # 使用模拟执行器
            "module_path": "qlib.backtest.executor",
            "kwargs": {
                "time_per_step": "day",                      # 每日执行一次
                "generate_portfolio_metrics": True,         # 生成组合指标
            },
        },

        # 交易策略配置
        "strategy": {
            "class": "TopkDropoutStrategy",                 # TopkDropout 策略
            "module_path": "qlib.contrib.strategy.signal_strategy",
            "kwargs": {
                "signal": (model, dataset),                 # 使用模型和数据集生成信号
                "topk": 50,                                 # 选择排名前50的股票
                "n_drop": 5,                                # 每次调仓时随机丢弃5只股票
            },
        },

        # 回测参数配置
        "backtest": {
            "start_time": "2017-01-01",                     # 回测开始时间
            "end_time": "2020-08-01",                       # 回测结束时间
            "account": 100000000,                          # 初始资金（1亿）
            "benchmark": CSI300_BENCH,                      # 基准指数（沪深300）
            "exchange_kwargs": {                            # 交易所参数
                "freq": "day",                              # 交易频率（日级）
                "limit_threshold": 0.095,                   # 涨跌停限制（9.5%）
                "deal_price": "close",                      # 成交价格（收盘价）
                "open_cost": 0.0005,                        # 开仓手续费（0.05%）
                "close_cost": 0.0015,                       # 平仓手续费（0.15%）
                "min_cost": 5,                              # 最小手续费（5元）
            },
        },
    }

      # ==================== 数据集预览（可选） ====================
    # 演示数据集的独立使用方式
    example_df = dataset.prepare("train")  # 准备训练数据
    print(example_df.head())  # 打印前几行数据预览

    # ==================== 实验管理和执行 ====================

    # 启动实验管理器
    # R 是 Qlib 的工作流管理器，负责实验跟踪和结果保存
    with R.start(experiment_name="workflow"):
        # 1. 记录实验参数
        # 将配置参数扁平化后记录到实验中，便于后续分析
        R.log_params(**flatten_dict(CSI300_GBDT_TASK))

        # 2. 模型训练
        # 使用准备好的数据集训练机器学习模型
        model.fit(dataset)

        # 3. 保存模型参数
        # 将训练好的模型保存到实验记录中
        R.save_objects(**{"params.pkl": model})

        # 4. 生成预测信号
        # 使用训练好的模型生成交易信号
        recorder = R.get_recorder()  # 获取当前实验的记录器
        sr = SignalRecord(model, dataset, recorder)  # 创建信号记录器
        sr.generate()  # 生成预测信号

        # 5. 信号分析
        # 评估预测信号的质量和统计特性
        sar = SigAnaRecord(recorder)  # 创建信号分析记录器
        sar.generate()  # 生成信号分析报告

        # 6. 组合回测分析
        # 基于预测信号进行历史回测，评估策略表现
        # 关于自定义预测的回测，请参考：
        # https://qlib.readthedocs.io/en/latest/component/recorder.html#record-template
        par = PortAnaRecord(recorder, port_analysis_config, "day")  # 创建组合分析记录器
        par.generate()  # 生成回测分析报告

    # ==================== 实验完成 ====================
    # 实验结果会自动保存到指定的目录中，包括：
    # - 模型参数文件
    # - 预测信号数据
    # - 信号分析报告
    # - 回测结果和业绩分析
    #
    # 用户可以通过 R.get_recorder() 来访问和分析实验结果
