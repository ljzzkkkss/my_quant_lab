"""
策略模块

包含 8 大经典量化策略实现：
- 双均线动能策略
- 布林带突破策略
- RSI 极值反转策略
- MACD 趋势策略
- KDJ 震荡策略
- 海龟交易法则
- 量价共振策略
- 动态网格波段策略
"""
from .base import Strategy, StrategyParam, StrategyResult, StrategyRegistry, auto_register
from .double_ma import DoubleMaStrategy, apply_double_ma_strategy
from .bollinger_bands import apply_bollinger_strategy
from .rsi_reversal import apply_rsi_strategy
from .macd_strategy import apply_macd_strategy
from .kdj_strategy import apply_kdj_strategy
from .turtle_strategy import TurtleStrategy
from .obv_momentum import OBVMomentumStrategy
from .grid_trading import SwingGridStrategy

__all__ = [
    # 基类
    'Strategy',
    'StrategyParam',
    'StrategyResult',
    'StrategyRegistry',
    'auto_register',

    # 双均线策略
    'DoubleMaStrategy',
    'apply_double_ma_strategy',

    # 布林带策略
    'apply_bollinger_strategy',
    # RSI 策略
    'apply_rsi_strategy',
    # MACD 策略
    'apply_macd_strategy',
    # KDJ 策略
    'apply_kdj_strategy',
    # 海龟交易法则
    'TurtleStrategy',
    # 量价共振策略
    'OBVMomentumStrategy',
    # 动态网格波段策略
    'SwingGridStrategy'
]
