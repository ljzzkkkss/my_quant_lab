"""
KDJ 震荡策略

策略逻辑:
    - J 线向上突破超卖线（如 0）：买入
    - J 线向下击穿超买线（如 100）：卖出

适用场景：短线极其敏锐
风险点：遇主升浪易踏空
"""
import pandas as pd
import numpy as np
from typing import Optional
from .base import Strategy, auto_register


def apply_kdj_strategy(
    df: pd.DataFrame,
    j_buy: float = 0,
    j_sell: float = 100,
    n: int = 9
) -> pd.DataFrame:
    """
    KDJ 震荡反转策略

    参数:
        df: 包含 OHLCV 数据的 DataFrame
        j_buy: J 线超卖买入阈值
        j_sell: J 线超买卖出阈值
        n: KDJ 计算周期

    返回:
        包含 signal 和 position_diff 列的 DataFrame
    """
    df = df.copy()

    # 1. 计算 KDJ
    low_list = df['最低'].rolling(window=n, min_periods=1).min()
    high_list = df['最高'].rolling(window=n, min_periods=1).max()
    rsv = (df['收盘'] - low_list) / (high_list - low_list) * 100
    rsv = rsv.fillna(50)

    df['k'] = rsv.ewm(com=2, adjust=False).mean()
    df['d'] = df['k'].ewm(com=2, adjust=False).mean()
    df['j'] = 3 * df['k'] - 2 * df['d']

    # 2. 生成信号状态（1=持仓，0=空仓）
    df['signal_state'] = np.nan
    # J 线向上突破买入线 -> 建仓
    df.loc[(df['j'] > j_buy) & (df['j'].shift(1) <= j_buy), 'signal_state'] = 1.0
    # J 线向下击穿卖出线 -> 空仓
    df.loc[(df['j'] < j_sell) & (df['j'].shift(1) >= j_sell), 'signal_state'] = 0.0

    # 3. 信号延续
    df['signal'] = df['signal_state'].ffill().fillna(0)

    # 4. 计算仓位变化
    df['position_diff'] = df['signal'].diff()

    # 清理临时列
    df.drop(columns=['signal_state'], inplace=True, errors='ignore')

    return df


@auto_register
class KDJStrategy(Strategy):
    """KDJ 震荡策略（面向对象版本）"""

    def __init__(
        self,
        j_buy: float = 0,
        j_sell: float = 100,
        n: int = 9
    ):
        super().__init__()
        self.j_buy = j_buy
        self.j_sell = j_sell
        self.n = n

        # 注册参数
        self.register_param(
            name='j_buy',
            default=0,
            min_val=-20,
            max_val=30,
            step=5,
            description='J 线超卖买入线',
            impact='调高：频繁进场抢反弹；调低：要求出现极度恐慌才进场，适合做极致左侧。'
        )
        self.register_param(
            name='j_sell',
            default=100,
            min_val=70,
            max_val=120,
            step=5,
            description='J 线超买卖出线',
            impact='调低：见好就收，适合弱势行情；调高：吃到极限，适合多头行情。'
        )
        self.register_param(
            name='n',
            default=9,
            min_val=5,
            max_val=30,
            step=1,
            description='KDJ 计算周期',
            impact='短线极其敏锐，失真度高。调大会削弱KDJ的短线特色，趋向于普通的 RSI。'
        )

    @property
    def name(self) -> str:
        return "KDJ 震荡策略"

    @property
    def description(self) -> str:
        return "短线极其敏锐；遇主升浪易踏空"

    def generate_signals(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        j_buy = self.get_param('j_buy', kwargs)
        j_sell = self.get_param('j_sell', kwargs)
        n = self.get_param('n', kwargs)

        return apply_kdj_strategy(df, j_buy, j_sell, n)
