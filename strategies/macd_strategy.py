"""
MACD 趋势策略

策略逻辑:
    - DIF 上穿 DEA（金叉）：买入
    - DIF 下穿 DEA（死叉）：卖出

适用场景：波段稳健抗骗线
风险点：信号滞后
"""
import pandas as pd
import numpy as np
from typing import Optional
from .base import Strategy, auto_register
from configs.settings import get_filter_config
filter_conf = get_filter_config()


def apply_macd_strategy(
    df: pd.DataFrame,
    fast_period: int = filter_conf.MACD_FAST,
    slow_period: int = filter_conf.MACD_SLOW,
    signal_period: int = filter_conf.MACD_SIGNAL
) -> pd.DataFrame:
    """
    MACD 趋势波段策略

    参数:
        df: 包含 OHLCV 数据的 DataFrame
        fast_period: 快线 EMA 周期
        slow_period: 慢线 EMA 周期
        signal_period: 信号线周期

    返回:
        包含 signal 和 position_diff 列的 DataFrame
    """
    df = df.copy()

    # 1. 计算 MACD
    ema_fast = df['收盘'].ewm(span=fast_period, adjust=False).mean()
    ema_slow = df['收盘'].ewm(span=slow_period, adjust=False).mean()

    df['dif'] = ema_fast - ema_slow
    df['dea'] = df['dif'].ewm(span=signal_period, adjust=False).mean()
    df['macd'] = (df['dif'] - df['dea']) * 2

    # 2. 生成信号状态（1=持仓，0=空仓）
    df['signal_state'] = np.nan
    # 金叉：DIF 从下方上穿 DEA
    df.loc[(df['dif'] > df['dea']) & (df['dif'].shift(1) <= df['dea'].shift(1)), 'signal_state'] = 1.0
    # 死叉：DIF 从上方下穿 DEA
    df.loc[(df['dif'] < df['dea']) & (df['dif'].shift(1) >= df['dea'].shift(1)), 'signal_state'] = 0.0

    # 3. 信号延续
    df['signal'] = df['signal_state'].ffill().fillna(0)

    # 4. 计算仓位变化
    df['position_diff'] = df['signal'].diff()

    # 清理临时列
    df.drop(columns=['signal_state'], inplace=True, errors='ignore')

    return df


@auto_register
class MACDStrategy(Strategy):
    """MACD 趋势策略（面向对象版本）"""

    def __init__(
        self,
        fast_period: int = filter_conf.MACD_FAST,
        slow_period: int = filter_conf.MACD_SLOW,
        signal_period: int = filter_conf.MACD_SIGNAL
    ):
        super().__init__()
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

        # 注册参数
        self.register_param(
            name='fast_period',
            default=12,
            min_val=5,
            max_val=40,
            step=2,
            description='快线 EMA 周期',
            impact='调小：对短期价格变化极其敏感，跟风快，但容易被庄家骗线。'
        )
        self.register_param(
            name='slow_period',
            default=26,
            min_val=15,
            max_val=100,
            step=2,
            description='慢线 EMA 周期',
            impact='大趋势的锚点。与快线差距越大，MACD柱子越平稳，但也越滞后。'
        )
        self.register_param(
            name='signal_period',
            default=9,
            min_val=5,
            max_val=20,
            step=1,
            description='信号线周期',
            impact='调小：金叉和死叉更容易发生，交易频率增加。'
        )

    @property
    def name(self) -> str:
        return "MACD 趋势策略"

    @property
    def description(self) -> str:
        return "波段稳健抗骗线；信号滞后"

    def generate_signals(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        fast = kwargs.get('fast_period', self.fast_period)
        slow = kwargs.get('slow_period', self.slow_period)
        signal = kwargs.get('signal_period', self.signal_period)

        return apply_macd_strategy(df, fast, slow, signal)
