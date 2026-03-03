"""
RSI 极值反转策略

策略逻辑:
    - RSI 低于下轨（如 30）：超卖，买入持仓
    - RSI 高于上轨（如 70）：超买，卖出空仓

适用场景：震荡市印钞机
风险点：单边暴跌易腰斩
"""
import pandas as pd
import numpy as np
from typing import Optional
from .base import Strategy, auto_register


def apply_rsi_strategy(
    df: pd.DataFrame,
    lower_bound: float = 30,
    upper_bound: float = 70,
    rsi_period: int = 14
) -> pd.DataFrame:
    """
    RSI 均值回归策略：超卖抄底，超买逃顶

    参数:
        df: 包含 OHLCV 数据的 DataFrame
        lower_bound: RSI 超卖阈值（买入线）
        upper_bound: RSI 超买阈值（卖出线）
        rsi_period: RSI 计算周期

    返回:
        包含 signal 和 position_diff 列的 DataFrame
    """
    df = df.copy()

    # 1. 计算 RSI
    delta = df['收盘'].diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1 / rsi_period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1 / rsi_period, adjust=False).mean()
    # 避免除零
    rs = gain / loss.replace(0, np.nan)
    df['rsi_line'] = 100 - (100 / (1 + rs))

    # 2. 生成信号状态（1=持仓，0=空仓）
    df['signal_state'] = np.nan
    df.loc[df['rsi_line'] < lower_bound, 'signal_state'] = 1.0  # 超卖，建立持仓状态
    df.loc[df['rsi_line'] > upper_bound, 'signal_state'] = 0.0  # 超买，建立空仓状态

    # 3. 信号延续：用前值填充 NaN，形成连续状态
    df['signal'] = df['signal_state'].ffill().fillna(0)

    # 4. 计算仓位变化（用于标识买卖点）
    df['position_diff'] = df['signal'].diff()

    # 清理临时列
    df.drop(columns=['signal_state'], inplace=True, errors='ignore')

    return df


@auto_register
class RSIStrategy(Strategy):
    """RSI 极值反转策略（面向对象版本）"""

    def __init__(
        self,
        lower_bound: float = 30,
        upper_bound: float = 70,
        rsi_period: int = 14
    ):
        super().__init__()
        self.lower_bound = lower_bound
        self.upper_bound = upper_bound
        self.rsi_period = rsi_period
        # 注册参数
        self.register_param(
            name='lower_bound',
            default=30,
            min_val=10,
            max_val=50,
            step=2,
            description='超卖阈值（低于此值买入）',
            impact='触发抄底的红线。调大(如40)：更容易成交，但也容易抄在半山腰；调小(如20)：买点极其安全，但会踏空绝大多数波段。'
        )
        self.register_param(
            name='upper_bound',
            default=70,
            min_val=50,
            max_val=95,
            step=2,
            description='超买阈值（高于此值卖出）',
            impact='触发逃顶的红线。调小(如60)：容易过早卖飞主升浪；调大(如80)：能吃到更多鱼身，但容易在顶点随波逐流产生利润回撤。'
        )
        self.register_param(
            name='rsi_period',
            default=14,
            min_val=5,
            max_val=30,
            step=1,
            description='RSI 计算周期',
            impact='调小：指标剧烈波动，来回打脸；调大：平滑震荡，但会产生严重的滞后。'
        )

    @property
    def name(self) -> str:
        return "RSI 极值反转策略"

    @property
    def description(self) -> str:
        return "震荡市印钞机；单边暴跌易腰斩"

    def generate_signals(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        lower = float(kwargs.get('lower_bound', self.lower_bound))
        upper = float(kwargs.get('upper_bound', self.upper_bound))
        period = int(kwargs.get('rsi_period', self.rsi_period))

        return apply_rsi_strategy(df, lower, upper, period)
