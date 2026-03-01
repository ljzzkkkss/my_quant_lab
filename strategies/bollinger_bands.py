import pandas as pd


def apply_bollinger_strategy(df, window=20, std_dev=2):
    """
    布林带突破策略：
    1. 计算中轨(MA)、上轨、下轨
    2. 突破下轨买入，跌破中轨/触碰上轨卖出 (流派众多，这里采用趋势突破型)
    """
    strat_df = df.copy()
    strat_df['MA'] = strat_df['收盘'].rolling(window=window).mean()
    strat_df['std'] = strat_df['收盘'].rolling(window=window).std()
    strat_df['Upper'] = strat_df['MA'] + (std_dev * strat_df['std'])  # 修正变量名
    strat_df['Lower'] = strat_df['MA'] - (std_dev * strat_df['std'])

    strat_df['signal'] = 0.0
    # 策略：收盘价站上中轨看多，跌破中轨看空
    strat_df.loc[strat_df['收盘'] > strat_df['MA'], 'signal'] = 1.0
    strat_df['position_diff'] = strat_df['signal'].diff()

    # 绘图兼容
    strat_df['SMA_short'] = strat_df['Upper']  # 借用原字段名方便画图显示
    strat_df['SMA_long'] = strat_df['Lower']
    return strat_df