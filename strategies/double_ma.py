import pandas as pd
import numpy as np


def apply_double_ma_strategy(df, short_window=5, long_window=20, use_macd_filter=True):
    """
    终极版：双均线 + MACD 动能过滤策略
    """
    data = df.copy()

    # 1. 计算基础双均线
    data['SMA_short'] = data['收盘'].rolling(window=short_window).mean()
    data['SMA_long'] = data['收盘'].rolling(window=long_window).mean()

    # 2. 纯手工计算 MACD (经典参数：12, 26, 9)
    # 计算短期(12日)和长期(26日)的指数移动平均线 (EMA)
    exp1 = data['收盘'].ewm(span=12, adjust=False).mean()
    exp2 = data['收盘'].ewm(span=26, adjust=False).mean()
    data['DIF'] = exp1 - exp2  # 快线
    data['DEA'] = data['DIF'].ewm(span=9, adjust=False).mean()  # 慢线
    data['MACD'] = (data['DIF'] - data['DEA']) * 2  # MACD 柱子

    # 3. 产生原始的均线交叉状态 (1 为多头，0 为空头)
    data['ma_signal'] = 0.0
    data.loc[data['SMA_short'] > data['SMA_long'], 'ma_signal'] = 1.0

    # 找到均线刚发生交叉的那一天
    data['ma_cross'] = data['ma_signal'].diff()

    # 4. 【核心灵魂】：引入 MACD 过滤机制
    if use_macd_filter:
        # 买入条件：均线发生金叉 (1.0) 并且 同一天的 MACD 柱子在水上 (大于 0)
        buy_condition = (data['ma_cross'] == 1.0) & (data['MACD'] > 0)

        # 卖出条件：均线发生死叉 (-1.0)，无条件逃顶
        sell_condition = (data['ma_cross'] == -1.0)

        # 重新构建最终的真实操作指令
        data['real_action'] = np.nan
        data.loc[buy_condition, 'real_action'] = 1.0  # 确认买入
        data.loc[sell_condition, 'real_action'] = 0.0  # 确认清仓

        # 用前向填充 (ffill) 把 1 和 0 铺满，形成真实的持仓状态 (signal)
        data['signal'] = data['real_action'].ffill().fillna(0)

        # 重新计算真正发生买卖动作的具体日期，用于画图的红绿箭头
        data['position_diff'] = data['signal'].diff()
    else:
        # 如果关闭过滤，就退化成最原始的双均线策略
        data['signal'] = data['ma_signal']
        data['position_diff'] = data['ma_cross']

    return data