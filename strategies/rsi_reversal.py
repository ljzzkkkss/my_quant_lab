import pandas as pd
import numpy as np


def apply_rsi_strategy(df, lower_bound=30, upper_bound=70, rsi_period=14):
    """
    RSI 均值回归策略：超卖抄底，超买逃顶
    """
    df = df.copy()

    # 1. 计算 RSI
    delta = df['收盘'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
    rs = gain / loss
    df['rsi_line'] = 100 - (100 / (1 + rs))

    # 2. 生成信号 (低于下轨买入，高于上轨卖出)
    df['signal'] = 0
    df.loc[df['rsi_line'] < lower_bound, 'signal'] = 1  # 超卖，持仓
    df.loc[df['rsi_line'] > upper_bound, 'signal'] = 0  # 超买，空仓

    # 3. 信号延续
    df['signal'] = df['signal'].replace(to_replace=0, method='ffill')
    # 处理第一笔卖出之前的状态
    df['signal'] = df['signal'].fillna(0)

    return df