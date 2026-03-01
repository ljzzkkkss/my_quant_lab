import pandas as pd
import numpy as np


def apply_double_ma_strategy(df, short_window=5, long_window=20):
    """
    双均线策略逻辑模块
    :param df: 包含收盘价的 DataFrame (由 data_fetcher 提供)
    :param short_window: 短期均线周期
    :param long_window: 长期均线周期
    :return: 带有信号的 DataFrame
    """
    # 1. 深度拷贝一份数据，避免修改原始数据
    strat_df = df.copy()

    # 2. 计算简单移动平均线 (SMA)
    strat_df['SMA_short'] = strat_df['收盘'].rolling(window=short_window).mean()
    strat_df['SMA_long'] = strat_df['收盘'].rolling(window=long_window).mean()

    # 3. 生成持仓信号
    # 当短线 > 长线，信号为 1 (看多)；否则为 0 (看空)
    # np.where 是量化中处理信号的神器，速度极快
    strat_df['signal'] = 0.0
    strat_df['signal'] = np.where(strat_df['SMA_short'] > strat_df['SMA_long'], 1.0, 0.0)

    # 4. 计算买卖点 (Signal Crossovers)
    # 今天的信号减去昨天的信号：
    # 1 - 0 = 1  (金叉，买入)
    # 0 - 1 = -1 (死叉，卖出)
    strat_df['position_diff'] = strat_df['signal'].diff()

    return strat_df


if __name__ == "__main__":
    # --- 单元测试：伪造一点数据来验证逻辑是否正确 ---
    print("正在运行策略模块单元测试...")
    dates = pd.date_range(start='2023-01-01', periods=30)
    fake_data = pd.DataFrame({
        '收盘': np.random.uniform(100, 110, size=30)
    }, index=dates)

    result = apply_double_ma_strategy(fake_data, 5, 10)
    print(result[['收盘', 'SMA_short', 'SMA_long', 'signal', 'position_diff']].tail())