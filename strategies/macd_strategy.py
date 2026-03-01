import pandas as pd
import numpy as np


def apply_macd_strategy(df, fast_period=12, slow_period=26, signal_period=9):
    """MACD 趋势波段策略 (为方便二维寻优，固定 signal_period 为 9)"""
    df = df.copy()

    # 计算 EMA
    ema_fast = df['收盘'].ewm(span=fast_period, adjust=False).mean()
    ema_slow = df['收盘'].ewm(span=slow_period, adjust=False).mean()

    df['dif'] = ema_fast - ema_slow
    df['dea'] = df['dif'].ewm(span=signal_period, adjust=False).mean()

    # 生成信号：金叉买入，死叉卖出
    df['signal'] = 0
    df.loc[(df['dif'] > df['dea']) & (df['dif'].shift(1) <= df['dea'].shift(1)), 'signal'] = 1
    df.loc[(df['dif'] < df['dea']) & (df['dif'].shift(1) >= df['dea'].shift(1)), 'signal'] = 0

    df['signal'] = df['signal'].replace(to_replace=0, method='ffill').fillna(0)
    return df