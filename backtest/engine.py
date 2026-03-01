import pandas as pd
import numpy as np
import plotly.graph_objects as go  # 引入丝滑的 Plotly 替换老旧的 matplotlib


def run_backtest(df, initial_capital=100000.0):
    """
    极简回测引擎：计算基准收益与策略收益
    """
    print("-> ⚙️ 正在启动回测引擎计算账户资金...")
    bt_df = df.copy()

    # 1. 计算基准收益率 (每天的真实涨跌幅)
    bt_df['daily_return'] = bt_df['收盘'].pct_change()

    # 2. 计算策略收益率
    bt_df['strategy_return'] = bt_df['signal'].shift(1) * bt_df['daily_return']

    # 3. 计算账户资金净值曲线 (复利计算)
    bt_df['benchmark_equity'] = initial_capital * (1 + bt_df['daily_return']).cumprod()
    bt_df['strategy_equity'] = initial_capital * (1 + bt_df['strategy_return']).cumprod()

    # 填补第一天的数据
    bt_df.iloc[0, bt_df.columns.get_loc('benchmark_equity')] = initial_capital
    bt_df.iloc[0, bt_df.columns.get_loc('strategy_equity')] = initial_capital

    # 4. 打印回测报告
    final_bench = bt_df['benchmark_equity'].iloc[-1]
    final_strat = bt_df['strategy_equity'].iloc[-1]

    bench_return = (final_bench - initial_capital) / initial_capital * 100
    strat_return = (final_strat - initial_capital) / initial_capital * 100

    print("\n" + "=" * 40)
    print("📊 量化策略回测报告")
    print("=" * 40)
    print(f"初始本金:     {initial_capital:,.2f} 元")
    print(f"基准最终资金: {final_bench:,.2f} 元 (一直持有的结果)")
    print(f"策略最终资金: {final_strat:,.2f} 元 (双均线操作的结果)")
    print("-" * 40)
    print(f"基准收益率:   {bench_return:.2f}%")
    print(f"策略收益率:   {strat_return:.2f}%")

    if strat_return > bench_return:
        print("🏆 结论：恭喜！你的策略跑赢了死拿不动的基准！")
    else:
        print("💔 结论：很遗憾，一顿操作猛如虎，不如躺平赚得多。这在震荡市很常见！")
    print("=" * 40 + "\n")

    return bt_df


def plot_equity_curve(bt_df, title="策略收益与基准收益对比"):
    """
    网页交互版：画出资金增长曲线图
    """
    print("-> 正在生成交互式资金曲线网页...")
    fig = go.Figure()

    # 画出基准线（灰色虚线）
    fig.add_trace(go.Scatter(
        x=bt_df.index, y=bt_df['benchmark_equity'],
        mode='lines', name='基准资金 (一直持有)',
        line=dict(color='gray', dash='dash', width=2)
    ))

    # 画出策略线（红色实线）
    fig.add_trace(go.Scatter(
        x=bt_df.index, y=bt_df['strategy_equity'],
        mode='lines', name='策略资金 (双均线)',
        line=dict(color='red', width=2.5)
    ))

    # 设置交互样式
    fig.update_layout(
        title=title,
        xaxis_title='日期',
        yaxis_title='账户总资金 (元)',
        hovermode='x unified',  # 开启垂直十字光标！
        template='plotly_white',  # 干净的主题
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)  # 图例放左上角
    )

    # 同样屏蔽周末的断层
    dt_all = pd.date_range(start=bt_df.index[0], end=bt_df.index[-1])
    dt_obs = [d.strftime("%Y-%m-%d") for d in bt_df.index]
    dt_breaks = [d for d in dt_all.strftime("%Y-%m-%d").tolist() if not d in dt_obs]
    fig.update_xaxes(rangebreaks=[dict(values=dt_breaks)])

    return fig;