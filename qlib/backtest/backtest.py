# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Qlib 回测引擎核心模块

本模块提供完整的量化策略回测功能，包括：
1. 回测主循环和数据处理
2. 策略与执行器的交互机制
3. 嵌套决策执行支持
4. 交易数据收集和分析

核心组件：
- backtest_loop(): 标准回测主循环
- collect_data_loop(): 数据收集模式（用于强化学习）
- 内置进度跟踪和性能监控

使用方式：
    from qlib.backtest import backtest

    # 执行完整回测
    portfolio_metrics, indicator_metrics = backtest(
        start_time='2020-01-01',
        end_time='2020-12-31',
        strategy=your_strategy,
        executor=your_executor
    )
"""

from __future__ import annotations

from typing import Dict, TYPE_CHECKING, Generator, Optional, Tuple, Union, cast

import pandas as pd

from qlib.backtest.decision import BaseTradeDecision
from qlib.backtest.report import Indicator

if TYPE_CHECKING:
    from qlib.strategy.base import BaseStrategy
    from qlib.backtest.executor import BaseExecutor

from tqdm.auto import tqdm  # 进度条显示

from ..utils.time import Freq

# 类型定义
# 组合指标：策略名称 -> (DataFrame数据, 配置字典)
PORT_METRIC = Dict[str, Tuple[pd.DataFrame, dict]]
# 指标数据：策略名称 -> (DataFrame数据, Indicator对象)
INDICATOR_METRIC = Dict[str, Tuple[pd.DataFrame, Indicator]]


def backtest_loop(
    start_time: Union[pd.Timestamp, str],
    end_time: Union[pd.Timestamp, str],
    trade_strategy: BaseStrategy,
    trade_executor: BaseExecutor,
) -> Tuple[PORT_METRIC, INDICATOR_METRIC]:
    """
    回测主循环函数 - 处理最外层策略与执行器的交互

    这是标准回测的主要入口点，负责协调策略和执行器完成
    完整的回测流程。支持嵌套决策执行模式。

    Args:
        start_time (Union[pd.Timestamp, str]): 回测开始时间
        end_time (Union[pd.Timestamp, str]): 回测结束时间
        trade_strategy (BaseStrategy): 交易策略对象
        trade_executor (BaseExecutor): 交易执行器对象

    Returns:
        Tuple[PORT_METRIC, INDICATOR_METRIC]:
            - PORT_METRIC: 组合指标数据，记录交易组合的详细信息
              格式: {策略名称: (DataFrame数据, 配置字典)}
            - INDICATOR_METRIC: 指标数据，包含计算的交易指标
              格式: {策略名称: (DataFrame数据, Indicator对象)}

    Note:
        - 这是一个高级封装函数，实际工作由 collect_data_loop 完成
        - 返回的组合指标可用于详细的业绩分析和归因
        - 支持多策略并行回测和嵌套执行模式

    Example:
        >>> from qlib.backtest import backtest_loop
        >>> from qlib.strategy import TopkDropoutStrategy
        >>> from qlib.backtest.executor import SimulatorExecutor
        >>>
        >>> strategy = TopkDropoutStrategy(...)
        >>> executor = SimulatorExecutor(...)
        >>> portfolio_metrics, indicator_metrics = backtest_loop(
        ...     start_time='2020-01-01',
        ...     end_time='2020-12-31',
        ...     trade_strategy=strategy,
        ...     trade_executor=executor
        ... )
    """
    # 初始化返回值字典，用于收集回测过程中的数据
    return_value: dict = {}

    # 调用数据收集循环执行实际的回测逻辑
    # 迭代生成器但不处理中间决策（仅用于触发回测流程）
    for _decision in collect_data_loop(
        start_time, end_time, trade_strategy, trade_executor, return_value
    ):
        pass  # 标准回测模式下不需要处理中间决策

    # 从返回值中提取组合指标和交易指标
    portfolio_dict = cast(PORT_METRIC, return_value.get("portfolio_dict"))
    indicator_dict = cast(INDICATOR_METRIC, return_value.get("indicator_dict"))

    return portfolio_dict, indicator_dict


def collect_data_loop(
    start_time: Union[pd.Timestamp, str],
    end_time: Union[pd.Timestamp, str],
    trade_strategy: BaseStrategy,
    trade_executor: BaseExecutor,
    return_value: dict | None = None,
) -> Generator[BaseTradeDecision, Optional[BaseTradeDecision], None]:
    """
    数据收集循环生成器 - 用于强化学习训练的决策数据收集

    这是 Qlib 回测引擎的核心函数，实现了完整的交易模拟循环。
    支持嵌套执行模式，可用于强化学习训练数据收集。

    Args:
        start_time (Union[pd.Timestamp, str]): 回测开始时间（闭区间）
            **注意**: 时间范围应用于最外层执行器的日历
        end_time (Union[pd.Timestamp, str]): 回测结束时间（闭区间）
            **注意**: 时间范围应用于最外层执行器的日历
            **示例**: 对于 日执行器(分钟级执行器) 的嵌套结构，
            设置 end_time="2020-03-01" 将包含 2020-03-01 的所有分钟
        trade_strategy (BaseStrategy): 最外层的投资组合策略
        trade_executor (BaseExecutor): 最外层的执行器
        return_value (dict, optional): 用于回测循环的返回值容器

    Yields:
        BaseTradeDecision: 每个时间步的交易决策

    Returns:
        Generator: 生成器对象，支持决策数据收集和状态更新

    Note:
        === 核心执行流程 ===
        1. 初始化执行器和策略
        2. 按照交易日历逐步执行：
           - 策略生成交易决策
           - 执行器处理决策并收集数据
           - 策略更新状态
        3. 支持嵌套执行（多层次时间尺度）
        4. 实时进度跟踪和日志记录

        === 强化学习支持 ===
        - 可作为环境与强化学习算法交互
        - 收集状态-动作-奖励序列
        - 支持自定义奖励函数设计

        === 嵌套执行示例 ===
        外层策略（资产配置）-> 内层策略（具体交易）
        日级别决策 -> 分钟级别执行

    Example:
        >>> # 用于强化学习训练
        >>> env = collect_data_loop(start, end, strategy, executor)
        >>> for decision in env:
        ...     action = rl_agent.decide(state)
        ...     observation = env.send(action)
        ...     reward = calculate_reward(observation)
    """
    # 重置执行器状态，设置回测时间范围
    trade_executor.reset(start_time=start_time, end_time=end_time)
    # 重置策略状态，传入执行器的层级基础设施
    trade_strategy.reset(level_infra=trade_executor.get_level_infra())

    # 初始化进度条
    with tqdm(
        total=trade_executor.trade_calendar.get_trade_len(), desc="backtest loop"
    ) as bar:
        _execute_result = None  # 上一步的执行结果

        # 主回测循环：按交易日历逐步执行
        while not trade_executor.finished():
            # 1. 策略根据上一步执行结果生成交易决策
            _trade_decision: BaseTradeDecision = trade_strategy.generate_trade_decision(
                _execute_result
            )

            # 2. 执行器处理交易决策并收集数据
            #    yield from 实现了嵌套执行器的数据收集
            _execute_result = yield from trade_executor.collect_data(
                _trade_decision, level=0
            )

            # 3. 策略执行后处理步骤（更新内部状态等）
            trade_strategy.post_exe_step(_execute_result)

            # 4. 更新进度条
            bar.update(1)
        # 策略的上层执行后处理步骤（用于嵌套策略的协调）
        trade_strategy.post_upper_level_exe_step()

    # 处理回测结果数据的收集和整理
    if return_value is not None:
        # 获取所有层级的执行器（支持嵌套执行）
        all_executors = trade_executor.get_all_executors()

        # 初始化结果容器
        portfolio_dict: PORT_METRIC = {}    # 组合指标数据
        indicator_dict: INDICATOR_METRIC = {}  # 交易指标数据

        # 遍历所有执行器，收集不同时间尺度的数据
        for executor in all_executors:
            # 根据执行器的时间频率生成唯一键
            # 例如：日级执行器 -> "day", 分钟级执行器 -> "1min"
            key = "{}{}".format(*Freq.parse(executor.time_per_step))

            # 收集组合指标（如果启用）
            if executor.trade_account.is_port_metr_enabled():
                portfolio_dict[key] = executor.trade_account.get_portfolio_metrics()

            # 收集交易指标数据
            indicator_df = (
                executor.trade_account.get_trade_indicator().generate_trade_indicators_dataframe()
            )
            indicator_obj = executor.trade_account.get_trade_indicator()
            indicator_dict[key] = (indicator_df, indicator_obj)

        # 将收集的数据更新到返回值容器中
        return_value.update(
            {"portfolio_dict": portfolio_dict, "indicator_dict": indicator_dict}
        )
