"""
策略抽象基类模块

定义所有策略必须实现的标准接口，确保策略的一致性和可扩展性。
"""
import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple


@dataclass
class StrategyParam:
    """策略参数定义"""
    name: str
    default: Any
    min_val: Any = None
    max_val: Any = None
    step: Any = 1
    description: str = ""


@dataclass
class StrategyResult:
    """策略执行结果"""
    data: pd.DataFrame
    signals: pd.Series
    positions: pd.Series
    metrics: Dict[str, Any] = field(default_factory=dict)


class Strategy(ABC):
    """
    策略抽象基类

    所有具体策略必须继承此类并实现抽象方法。

    使用示例:
        class DoubleMaStrategy(Strategy):
            def __init__(self, short_window=5, long_window=20):
                super().__init__()
                self.short_window = short_window
                self.long_window = long_window

            def generate_signals(self, df):
                # 实现信号生成逻辑
                pass
    """

    def __init__(self):
        self._params: Dict[str, StrategyParam] = {}
        self._initialized = False

    @property
    @abstractmethod
    def name(self) -> str:
        """策略名称"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """策略描述"""
        pass

    @property
    def params(self) -> Dict[str, StrategyParam]:
        """策略参数定义"""
        return self._params

    def register_param(
        self,
        name: str,
        default: Any,
        min_val: Any = None,
        max_val: Any = None,
        step: Any = 1,
        description: str = ""
    ):
        """注册策略参数"""
        self._params[name] = StrategyParam(
            name=name,
            default=default,
            min_val=min_val,
            max_val=max_val,
            step=step,
            description=description
        )

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """
        生成交易信号

        参数:
            df: 包含 OHLCV 数据的 DataFrame
            **kwargs: 策略特定参数

        返回:
            包含 signal 和 position_diff 列的 DataFrame
        """
        pass

    def validate_params(self, **kwargs) -> Tuple[bool, str]:
        """
        验证参数有效性

        参数:
            **kwargs: 待验证的参数

        返回:
            (是否有效，错误信息)
        """
        for param_name, param_def in self._params.items():
            if param_name in kwargs:
                value = kwargs[param_name]
                if param_def.min_val is not None and value < param_def.min_val:
                    return False, f"{param_name} 不能小于 {param_def.min_val}"
                if param_def.max_val is not None and value > param_def.max_val:
                    return False, f"{param_name} 不能大于 {param_def.max_val}"
        return True, ""

    def execute(self, df: pd.DataFrame, **kwargs) -> StrategyResult:
        """
        执行策略的完整流程

        参数:
            df: 输入数据
            **kwargs: 策略参数

        返回:
            StrategyResult 包含完整结果
        """
        # 参数验证
        is_valid, error_msg = self.validate_params(**kwargs)
        if not is_valid:
            raise ValueError(f"策略参数验证失败：{error_msg}")

        # 生成信号
        result_df = self.generate_signals(df, **kwargs)

        # 确保必要的列存在
        if 'signal' not in result_df.columns:
            result_df['signal'] = 0
        if 'position_diff' not in result_df.columns:
            result_df['position_diff'] = result_df['signal'].diff().fillna(0)

        return StrategyResult(
            data=result_df,
            signals=result_df['signal'],
            positions=result_df['position_diff'],
            metrics=self._calculate_metrics(result_df)
        )

    def _calculate_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """计算策略基础指标（可被子类重写）"""
        signals = df.get('signal', pd.Series())
        if signals.empty:
            return {}

        # 计算换手率
        position_changes = df.get('position_diff', pd.Series()).abs().sum()
        total_days = len(df)

        return {
            'signal_count': (signals != 0).sum(),
            'buy_signals': (signals == 1).sum(),
            'sell_signals': (signals == -1).sum(),
            'position_changes': position_changes,
            'turnover_rate': position_changes / total_days if total_days > 0 else 0
        }


# ========== 策略注册表 ==========
class StrategyRegistry:
    """策略注册表，用于自动发现和注册策略"""

    _strategies: Dict[str, Strategy] = {}

    @classmethod
    def register(cls, strategy: Strategy):
        """注册策略实例"""
        cls._strategies[strategy.name] = strategy

    @classmethod
    def get(cls, name: str) -> Optional[Strategy]:
        """获取策略实例"""
        return cls._strategies.get(name)

    @classmethod
    def list_strategies(cls) -> List[str]:
        """列出所有已注册的策略"""
        return list(cls._strategies.keys())

    @classmethod
    def get_description(cls, name: str) -> str:
        """获取策略描述"""
        strategy = cls.get(name)
        return strategy.description if strategy else "未知策略"


def auto_register(cls):
    """装饰器：自动注册策略类"""
    instance = cls()
    StrategyRegistry.register(instance)
    return cls
