# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Qlib 策略基类模块

本模块定义了 Qlib 中所有交易策略的基础抽象类，提供：
1. 统一的策略接口规范
2. 灵活的决策生成机制
3. 支持嵌套策略和多时间尺度执行
4. 强化学习策略的专用接口

主要组件：
- BaseStrategy: 所有策略的基础抽象类
- RLStrategy: 强化学习策略基类
- RLIntStrategy: 集成强化学习解释器的策略类

设计原则：
- 分离关注点：策略逻辑与执行机制分离
- 可组合性：支持策略的嵌套和组合
- 状态管理：提供完整的策略生命周期管理
- 灵活配置：支持从配置文件初始化策略
"""

from __future__ import annotations

from abc import ABCMeta, abstractmethod
from typing import Any, Generator, Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from qlib.backtest.exchange import Exchange
    from qlib.backtest.position import BasePosition
    from qlib.backtest.executor import BaseExecutor

from typing import Tuple

from ..backtest.decision import BaseTradeDecision
from ..backtest.utils import (
    CommonInfrastructure,
    LevelInfrastructure,
    TradeCalendarManager,
)
from ..rl.interpreter import ActionInterpreter, StateInterpreter
from ..utils import init_instance_by_config

__all__ = ["BaseStrategy", "RLStrategy", "RLIntStrategy"]


class BaseStrategy:
    """
    交易策略基类

    这是 Qlib 中所有交易策略的基础抽象类，定义了策略的基本接口
    和生命周期管理。支持嵌套执行和多时间尺度策略设计。

    主要功能：
    1. 提供统一的策略决策接口
    2. 支持策略状态管理和生命周期控制
    3. 兼容嵌套执行和多层次时间尺度
    4. 提供灵活的基础设施访问接口

    核心概念：
    - 外层决策：父策略传递给当前策略的交易决策
    - 层级基础设施：当前层级专用的基础设施组件
    - 公共基础设施：所有层级共享的基础设施组件
    - 交易所对象：用于执行交易的市场模拟器

    使用场景：
    - 单一策略：独立运行的交易策略
    - 嵌套策略：作为子策略在更大框架中运行
    - 多时间尺度：处理不同时间粒度的决策

    Example:
        >>> class MyStrategy(BaseStrategy):
        ...     def generate_trade_decision(self, execute_result):
        ...         # 基于历史执行结果生成新的交易决策
        ...         return TradeDecision(...)
        >>>
        >>> strategy = MyStrategy()
        >>> strategy.reset(level_infra=infra)
        >>> decision = strategy.generate_trade_decision(None)
    """

    def __init__(
        self,
        outer_trade_decision: BaseTradeDecision = None,
        level_infra: LevelInfrastructure = None,
        common_infra: CommonInfrastructure = None,
        trade_exchange: Exchange = None,
    ) -> None:
        """
        初始化策略对象

        Args:
            outer_trade_decision (BaseTradeDecision, optional): 外层策略的交易决策
                - 这是父策略传递给当前策略的交易决策
                - 如果当前策略用于拆分交易决策，则此参数会被使用
                - 如果当前策略用于投资组合管理，则可以忽略此参数
                - 默认值：None

            level_infra (LevelInfrastructure, optional): 层级共享基础设施
                - 当前策略层级专用的基础设施组件
                - 包含该层级的交易日历等信息
                - 用于支持嵌套执行和多时间尺度策略
                - 默认值：None

            common_infra (CommonInfrastructure, optional): 公共共享基础设施
                - 所有策略层级共享的基础设施组件
                - 包含交易账户、交易所等公共资源
                - 确保不同层级的策略能访问相同的基础资源
                - 默认值：None

            trade_exchange (Exchange): 交易所对象
                - 提供市场信息、处理订单、生成报告的交易环境
                - 如果为None，将从common_infra自动获取
                - 允许在不同执行中使用不同的交易所
                - 使用场景示例：
                    * 日级执行：可以使用日级或分钟级交易所，推荐日级（更快）
                    * 分钟级执行：只能使用分钟级交易所，日级交易所不适用

        Note:
            === 参数使用指南 ===

            outer_trade_decision 的使用场景：
            - 策略拆分：将大额交易拆分为多个小额交易
            - 风险控制：根据外部约束调整交易决策
            - 资金分配：在多个子策略间分配资金

            level_infra vs common_infra：
            - level_infra：层级特定，如日级策略的日历
            - common_infra：全局共享，如统一的交易账户
            - 这种设计支持灵活的嵌套策略架构

            trade_exchange 选择原则：
            - 匹配时间频率：日级策略用日级交易所，分钟级用分钟级
            - 性能考虑：更粗粒度的交易所通常运行更快
            - 数据完整性：确保交易所提供的数据满足策略需求

        Example:
            >>> # 嵌套策略示例
            >>> outer_strategy = PortfolioStrategy()
            >>> inner_strategy = StockStrategy(
            ...     outer_trade_decision=decision,
            ...     level_infra=inner_infra,
            ...     common_infra=shared_infra
            ... )
        """

        self._reset(
            level_infra=level_infra,
            common_infra=common_infra,
            outer_trade_decision=outer_trade_decision,
        )
        self._trade_exchange = trade_exchange

    @property
    def executor(self) -> BaseExecutor:
        return self.level_infra.get("executor")

    @property
    def trade_calendar(self) -> TradeCalendarManager:
        return self.level_infra.get("trade_calendar")

    @property
    def trade_position(self) -> BasePosition:
        return self.common_infra.get("trade_account").current_position

    @property
    def trade_exchange(self) -> Exchange:
        """get trade exchange in a prioritized order"""
        return getattr(self, "_trade_exchange", None) or self.common_infra.get(
            "trade_exchange"
        )

    def reset_level_infra(self, level_infra: LevelInfrastructure) -> None:
        if not hasattr(self, "level_infra"):
            self.level_infra = level_infra
        else:
            self.level_infra.update(level_infra)

    def reset_common_infra(self, common_infra: CommonInfrastructure) -> None:
        if not hasattr(self, "common_infra"):
            self.common_infra: CommonInfrastructure = common_infra
        else:
            self.common_infra.update(common_infra)

    def reset(
        self,
        level_infra: LevelInfrastructure = None,
        common_infra: CommonInfrastructure = None,
        outer_trade_decision: BaseTradeDecision = None,
        **kwargs,
    ) -> None:
        """
        - reset `level_infra`, used to reset trade calendar, .etc
        - reset `common_infra`, used to reset `trade_account`, `trade_exchange`, .etc
        - reset `outer_trade_decision`, used to make split decision

        **NOTE**:
        split this function into `reset` and `_reset` will make following cases more convenient
        1. Users want to initialize his strategy by overriding `reset`, but they don't want to affect the `_reset`
        called when initialization
        """
        self._reset(
            level_infra=level_infra,
            common_infra=common_infra,
            outer_trade_decision=outer_trade_decision,
        )

    def _reset(
        self,
        level_infra: LevelInfrastructure = None,
        common_infra: CommonInfrastructure = None,
        outer_trade_decision: BaseTradeDecision = None,
    ):
        """
        Please refer to the docs of `reset`
        """
        if level_infra is not None:
            self.reset_level_infra(level_infra)

        if common_infra is not None:
            self.reset_common_infra(common_infra)

        if outer_trade_decision is not None:
            self.outer_trade_decision = outer_trade_decision

    @abstractmethod
    def generate_trade_decision(
        self,
        execute_result: list = None,
    ) -> Union[BaseTradeDecision, Generator[Any, Any, BaseTradeDecision]]:
        """Generate trade decision in each trading bar

        Parameters
        ----------
        execute_result : List[object], optional
            the executed result for trade decision, by default None

            - When call the generate_trade_decision firstly, `execute_result` could be None
        """
        raise NotImplementedError("generate_trade_decision is not implemented!")

    # helper methods: not necessary but for convenience
    def get_data_cal_avail_range(self, rtype: str = "full") -> Tuple[int, int]:
        """
        return data calendar's available decision range for `self` strategy
        the range consider following factors
        - data calendar in the charge of `self` strategy
        - trading range limitation from the decision of outer strategy


        related methods
        - TradeCalendarManager.get_data_cal_range
        - BaseTradeDecision.get_data_cal_range_limit

        Parameters
        ----------
        rtype: str
            - "full": return the available data index range of the strategy from `start_time` to `end_time`
            - "step": return the available data index range of the strategy of current step

        Returns
        -------
        Tuple[int, int]:
            the available range both sides are closed
        """
        cal_range = self.trade_calendar.get_data_cal_range(rtype=rtype)
        if self.outer_trade_decision is None:
            raise ValueError(f"There is not limitation for strategy {self}")
        range_limit = self.outer_trade_decision.get_data_cal_range_limit(rtype=rtype)
        return max(cal_range[0], range_limit[0]), min(cal_range[1], range_limit[1])

    """
    The following methods are used to do cross-level communications in nested execution.
    You do not need to care about them if you are implementing a single-level execution.
    """

    @staticmethod
    def update_trade_decision(
        trade_decision: BaseTradeDecision,
        trade_calendar: TradeCalendarManager,
    ) -> Optional[BaseTradeDecision]:
        """
        update trade decision in each step of inner execution, this method enable all order

        Parameters
        ----------
        trade_decision : BaseTradeDecision
            the trade decision that will be updated
        trade_calendar : TradeCalendarManager
            The calendar of the **inner strategy**!!!!!

        Returns
        -------
            BaseTradeDecision:
        """
        # default to return None, which indicates that the trade decision is not changed
        return None

    def alter_outer_trade_decision(
        self, outer_trade_decision: BaseTradeDecision
    ) -> BaseTradeDecision:
        """
        A method for updating the outer_trade_decision.
        The outer strategy may change its decision during updating.

        Parameters
        ----------
        outer_trade_decision : BaseTradeDecision
            the decision updated by the outer strategy

        Returns
        -------
            BaseTradeDecision
        """
        # default to reset the decision directly
        # NOTE: normally, user should do something to the strategy due to the change of outer decision
        return outer_trade_decision

    def post_upper_level_exe_step(self) -> None:
        """
        A hook for doing sth after the upper level executor finished its execution (for example, finalize
        the metrics collection).
        """

    def post_exe_step(self, execute_result: Optional[list]) -> None:
        """
        A hook for doing sth after the corresponding executor finished its execution.

        Parameters
        ----------
        execute_result :
            the execution result
        """


class RLStrategy(BaseStrategy, metaclass=ABCMeta):
    """RL-based strategy"""

    def __init__(
        self,
        policy,
        outer_trade_decision: BaseTradeDecision = None,
        level_infra: LevelInfrastructure = None,
        common_infra: CommonInfrastructure = None,
        **kwargs,
    ) -> None:
        """
        Parameters
        ----------
        policy :
            RL policy for generate action
        """
        super(RLStrategy, self).__init__(
            outer_trade_decision, level_infra, common_infra, **kwargs
        )
        self.policy = policy


class RLIntStrategy(RLStrategy, metaclass=ABCMeta):
    """(RL)-based (Strategy) with (Int)erpreter"""

    def __init__(
        self,
        policy,
        state_interpreter: dict | StateInterpreter,
        action_interpreter: dict | ActionInterpreter,
        outer_trade_decision: BaseTradeDecision = None,
        level_infra: LevelInfrastructure = None,
        common_infra: CommonInfrastructure = None,
        **kwargs,
    ) -> None:
        """
        Parameters
        ----------
        state_interpreter : Union[dict, StateInterpreter]
            interpreter that interprets the qlib execute result into rl env state
        action_interpreter : Union[dict, ActionInterpreter]
            interpreter that interprets the rl agent action into qlib order list
        start_time : Union[str, pd.Timestamp], optional
            start time of trading, by default None
        end_time : Union[str, pd.Timestamp], optional
            end time of trading, by default None
        """
        super(RLIntStrategy, self).__init__(
            policy, outer_trade_decision, level_infra, common_infra, **kwargs
        )

        self.policy = policy
        self.state_interpreter = init_instance_by_config(
            state_interpreter, accept_types=StateInterpreter
        )
        self.action_interpreter = init_instance_by_config(
            action_interpreter, accept_types=ActionInterpreter
        )

    def generate_trade_decision(self, execute_result: list = None) -> BaseTradeDecision:
        _interpret_state = self.state_interpreter.interpret(
            execute_result=execute_result
        )
        _action = self.policy.step(_interpret_state)
        _trade_decision = self.action_interpreter.interpret(action=_action)
        return _trade_decision
