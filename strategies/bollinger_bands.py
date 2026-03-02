"""
布林带突破策略

策略逻辑:
    - 收盘价站上中轨：看多持仓
    - 收盘价跌破中轨：看空空仓

适用场景：专抓妖股起爆点
风险点：假突破较多
"""
import pandas as pd
import numpy as np
from typing import Optional
from .base import Strategy, auto_register


def apply_bollinger_strategy(
    df: pd.DataFrame,
    window: int = 20,
    std_dev: float = 2.0
) -> pd.DataFrame:
    """
    布林带突破策略

    参数:
        df: 包含 OHLCV 数据的 DataFrame
        window: 布林带计算周期
        std_dev: 标准差倍数

    返回:
        包含 signal 和 position_diff 列的 DataFrame
    """
    strat_df = df.copy()

    # 1. 计算布林带
    strat_df['MA'] = strat_df['收盘'].rolling(window=window).mean()
    strat_df['std'] = strat_df['收盘'].rolling(window=window).std(ddof=0)
    strat_df['Upper'] = strat_df['MA'] + (std_dev * strat_df['std'])
    strat_df['Lower'] = strat_df['MA'] - (std_dev * strat_df['std'])

    # 2. 生成信号状态（1=持仓，0=空仓）
    strat_df['signal_state'] = np.nan
    # 收盘价站上中轨 -> 持仓
    strat_df.loc[strat_df['收盘'] > strat_df['MA'], 'signal_state'] = 1.0
    # 收盘价跌破中轨 -> 空仓
    strat_df.loc[strat_df['收盘'] <= strat_df['MA'], 'signal_state'] = 0.0

    # 3. 信号延续
    strat_df['signal'] = strat_df['signal_state']

    # 4. 计算仓位变化
    strat_df['position_diff'] = strat_df['signal'].diff()

    # 清理临时列
    strat_df.drop(columns=['signal_state'], inplace=True, errors='ignore')

    # 5. 绘图兼容（借用原字段名方便画图显示）
    strat_df['SMA_short'] = strat_df['Upper']
    strat_df['SMA_long'] = strat_df['Lower']

    return strat_df


@auto_register
class BollingerBandsStrategy(Strategy):
    """布林带突破策略（面向对象版本）"""

    def __init__(
        self,
        window: int = 20,
        std_dev: float = 2.0
    ):
        super().__init__()
        self.window = window
        self.std_dev = std_dev

        # 注册参数
        self.register_param(
            name='window',
            default=20,
            min_val=5,
            max_val=120,
            step=5,
            description='布林带计算周期',
            impact='计算均线的基准。调小：反应更灵敏，但假突破极多；调大：趋势更稳固，但会严重错过第一波起爆点。'
        )
        self.register_param(
            name='std_dev',
            default=2.0,
            min_val=1.0,
            max_val=3.5,
            step=0.1,
            description='标准差倍数',
            impact='定义通道宽度的乘数。调小：频繁开仓且假信号极多；调大：专抓真正的极端异动，但可能长年等不到一次开仓。'
        )

    @property
    def name(self) -> str:
        return "布林带突破策略"

    @property
    def description(self) -> str:
        return "专抓妖股起爆点；假突破较多"

    def generate_signals(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        window = kwargs.get('window', self.window)
        std = kwargs.get('std_dev', self.std_dev)

        return apply_bollinger_strategy(df, window, std)
