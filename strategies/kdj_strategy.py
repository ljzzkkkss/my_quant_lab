import pandas as pd
import numpy as np


def apply_kdj_strategy(df, j_buy=0, j_sell=100, n=9):
    """KDJ 震荡反转策略 (为方便二维寻优，固定周期 N 为 9)"""
    df = df.copy()

    low_list = df['最低'].rolling(window=n, min_periods=1).min()
    high_list = df['最高'].rolling(window=n, min_periods=1).max()
    rsv = (df['收盘'] - low_list) / (high_list - low_list) * 100
    rsv = rsv.fillna(50)

    df['k'] = rsv.ewm(com=2, adjust=False).mean()
    df['d'] = df['k'].ewm(com=2, adjust=False).mean()
    df['j'] = 3 * df['k'] - 2 * df['d']

    # 生成信号：J线向上突破底线买入，向下击穿顶线卖出
    df['signal'] = 0
    df.loc[(df['j'] > j_buy) & (df['j'].shift(1) <= j_buy), 'signal'] = 1
    df.loc[(df['j'] < j_sell) & (df['j'].shift(1) >= j_sell), 'signal'] = 0

    df['signal'] = df['signal'].replace(to_replace=0, method='ffill').fillna(0)
    return df