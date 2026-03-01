import pandas as pd
import numpy as np
import plotly.graph_objects as go


def run_backtest(df, initial_capital=100000.0, position_ratio=1.0):
    """
    量化回测引擎：支持仓位管理、手续费计算、胜率及盈亏比统计
    """
    bt_df = df.copy()

    # 基础收益计算
    bt_df['daily_return'] = bt_df['收盘'].pct_change()
    bt_df['strategy_return'] = bt_df['signal'].shift(1) * bt_df['daily_return']

    # 模拟手续费 (买入0.03%, 卖出0.08%)
    buy_fee, sell_fee = 0.0003, 0.0008
    bt_df['trade_cost'] = 0.0
    bt_df.loc[bt_df['position_diff'] == 1, 'trade_cost'] = -buy_fee
    bt_df.loc[bt_df['position_diff'] == -1, 'trade_cost'] = -sell_fee

    # 应用仓位管理
    bt_df['real_ret'] = (bt_df['strategy_return'] + bt_df['trade_cost']) * position_ratio

    # 计算净值曲线
    bt_df['benchmark_equity'] = initial_capital * (1 + bt_df['daily_return']).cumprod()
    bt_df['strategy_equity'] = initial_capital * (1 + bt_df['real_ret']).cumprod()

    # 指标计算：回撤
    bt_df['cum_max'] = bt_df['strategy_equity'].cummax()
    bt_df['drawdown'] = (bt_df['strategy_equity'] - bt_df['cum_max']) / bt_df['cum_max']
    max_dd = bt_df['drawdown'].min() * 100

    # 指标计算：夏普比率
    daily_ret = bt_df['real_ret'].dropna()
    sharpe = (daily_ret.mean() / daily_ret.std() * np.sqrt(252)) if daily_ret.std() != 0 else 0

    # ==========================================
    # 📈 核心统计：交易闭环分析 (胜率/盈亏比)
    # ==========================================
    trades = []
    buy_price = 0
    is_holding = False

    for _, row in bt_df.iterrows():
        if row['position_diff'] == 1:
            buy_price = row['收盘'] * (1 + buy_fee)  # 计入买入成本
            is_holding = True
        elif row['position_diff'] == -1 and is_holding:
            sell_price = row['收盘'] * (1 - sell_fee)  # 计入卖出成本
            profit_pct = (sell_price - buy_price) / buy_price
            trades.append(profit_pct)
            is_holding = False

    # 计算胜率
    win_trades = [t for t in trades if t > 0]
    loss_trades = [t for t in trades if t <= 0]
    win_rate = (len(win_trades) / len(trades) * 100) if trades else 0

    # 计算盈亏比 (平均盈利 / 平均亏损的绝对值)
    avg_win = np.mean(win_trades) if win_trades else 0
    avg_loss = abs(np.mean(loss_trades)) if loss_trades else 0
    if len(loss_trades) == 0:
        if len(win_trades) > 0:
            # 如果全胜，盈亏比给个 999 代表无穷大，或者直接给平均盈利
            pl_ratio = round(avg_win * 100, 2)  # 这里用盈利幅度暂代
        else:
            pl_ratio = 0.0
    else:
        pl_ratio = (avg_win / avg_loss) if avg_loss != 0 else 0

    # 封装元数据
    bt_df.attrs['max_drawdown'] = max_dd
    bt_df.attrs['sharpe_ratio'] = sharpe
    bt_df.attrs['win_rate'] = win_rate
    bt_df.attrs['pl_ratio'] = pl_ratio
    bt_df.attrs['trade_count'] = len(trades)

    return bt_df


def plot_equity_curve(bt_df, title="策略净值曲线"):
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(x=bt_df.index, y=bt_df['benchmark_equity'], name='基准收益', line=dict(color='gray', dash='dash')))
    fig.add_trace(
        go.Scatter(x=bt_df.index, y=bt_df['strategy_equity'], name='策略收益', line=dict(color='red', width=2)))
    fig.update_layout(title=title, template='plotly_white', hovermode='x unified')
    return fig