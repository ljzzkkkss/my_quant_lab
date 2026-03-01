import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 导入我们的后端核心模块
from utils.data_fetcher import get_daily_hfq_data
from strategies.double_ma import apply_double_ma_strategy
from backtest.engine import run_backtest, plot_equity_curve

st.set_page_config(page_title="量化策略实验室", page_icon="📈", layout="wide")


def plot_interactive_kline(df, short_window, long_window, title="交互式 K 线图"):
    """
    支持动态参数名的交互式 K 线图
    """
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.8, 0.2])

    fig.add_trace(go.Candlestick(
        x=df.index, open=df['开盘'], high=df['最高'], low=df['最低'], close=df['收盘'],
        name='K线', increasing_line_color='red', decreasing_line_color='green'
    ), row=1, col=1)

    # 【动态命名图例】：根据你前端输入的参数，自动改变线段名称
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_short'], mode='lines', name=f'{short_window}日均线',
                             line=dict(color='orange', width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_long'], mode='lines', name=f'{long_window}日均线',
                             line=dict(color='blue', width=1.5)), row=1, col=1)

    buy_signals = df[df['position_diff'] == 1.0]
    sell_signals = df[df['position_diff'] == -1.0]

    fig.add_trace(go.Scatter(
        x=buy_signals.index, y=buy_signals['最低'] * 0.98,
        mode='markers', name='买入',
        marker=dict(symbol='triangle-up', color='red', size=14, line=dict(width=1, color='DarkSlateGrey'))
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=sell_signals.index, y=sell_signals['最高'] * 1.02,
        mode='markers', name='卖出',
        marker=dict(symbol='triangle-down', color='green', size=14, line=dict(width=1, color='DarkSlateGrey'))
    ), row=1, col=1)

    colors = ['red' if row['收盘'] >= row['开盘'] else 'green' for index, row in df.iterrows()]
    fig.add_trace(go.Bar(x=df.index, y=df['成交量'], name='成交量', marker_color=colors), row=2, col=1)

    fig.update_layout(
        title=title, yaxis_title='价格 (元)', yaxis2_title='成交量',
        xaxis_rangeslider_visible=False, hovermode='x unified',
        template='plotly_white', margin=dict(l=50, r=50, t=60, b=50)
    )

    dt_all = pd.date_range(start=df.index[0], end=df.index[-1])
    dt_obs = [d.strftime("%Y-%m-%d") for d in df.index]
    dt_breaks = [d for d in dt_all.strftime("%Y-%m-%d").tolist() if not d in dt_obs]
    fig.update_xaxes(rangebreaks=[dict(values=dt_breaks)])

    return fig


# ==========================================
# 前端 UI 构建与交互逻辑
# ==========================================
st.title("📈 核心策略回测控制台")
st.markdown("通过左侧面板调整参数并点击运行，回测引擎将实时计算资金曲线。")

with st.sidebar:
    st.header("⚙️ 引擎配置")

    symbol = st.text_input("股票代码", value="600519")

    col_date1, col_date2 = st.columns(2)
    with col_date1:
        start_date = st.text_input("开始日期", value="20230101")
    with col_date2:
        end_date = st.text_input("结束日期", value="20231231")

    st.markdown("---")
    st.subheader("📊 均线策略参数")

    # 【新增参数控制】：让用户可以在侧边栏调整均线周期
    col_ma1, col_ma2 = st.columns(2)
    with col_ma1:
        short_window = st.number_input("短期均线 (日)", min_value=2, max_value=60, value=5, step=1)
    with col_ma2:
        long_window = st.number_input("长期均线 (日)", min_value=5, max_value=250, value=20, step=1)

    st.markdown("---")
    initial_capital = st.number_input("初始回测资金 (元)", min_value=1000.0, value=100000.0, step=10000.0,
                                      format="%.2f")

    run_button = st.button("🚀 开始执行回测", use_container_width=True, type="primary")

if run_button:
    # 防止短期均线大于等于长期均线的无效输入
    if short_window >= long_window:
        st.sidebar.error("⚠️ 逻辑错误：短期均线必须小于长期均线！")
    else:
        with st.spinner('后端引擎正在获取数据并执行回测计算...'):

            # 1. 获取数据
            raw_data = get_daily_hfq_data(symbol, start_date, end_date)

            if raw_data is None or raw_data.empty:
                st.error("❌ 获取数据失败，请检查股票代码或日期格式！")
            else:
                # 2. 动态传入你在侧边栏设置的短期和长期天数
                strategy_data = apply_double_ma_strategy(raw_data, short_window=short_window, long_window=long_window)

                # 3. 回测算账
                bt_results = run_backtest(strategy_data, initial_capital=initial_capital)

                final_bench = bt_results['benchmark_equity'].iloc[-1]
                final_strat = bt_results['strategy_equity'].iloc[-1]
                bench_return = (final_bench - initial_capital) / initial_capital * 100
                strat_return = (final_strat - initial_capital) / initial_capital * 100

                st.subheader("📊 收益看板")
                metric_col1, metric_col2, metric_col3 = st.columns(3)

                with metric_col1:
                    st.metric(label="初始本金", value=f"¥ {initial_capital:,.2f}")

                with metric_col2:
                    st.metric(label="基准期末资金 (躺平持股)",
                              value=f"¥ {final_bench:,.2f}",
                              delta=f"{bench_return:.2f}% (基准收益)")

                with metric_col3:
                    delta_color = "normal" if strat_return > bench_return else "inverse"
                    st.metric(label=f"策略期末资金 ({short_window}/{long_window}均线)",
                              value=f"¥ {final_strat:,.2f}",
                              delta=f"{strat_return:.2f}% (策略收益)",
                              delta_color=delta_color)

                if strat_return > bench_return:
                    st.success(f"🏆 结论：恭喜！在 {short_window}日/{long_window}日 组合下，策略成功跑赢了基准！")
                else:
                    st.warning("💔 结论：策略跑输基准。震荡市中频繁止损导致了本金磨损，建议尝试修改均线周期。")

                st.markdown("---")

                st.subheader("📈 K线与买卖信号图")
                # 把参数传给画图函数，用于渲染正确的图例
                kline_fig = plot_interactive_kline(strategy_data, short_window, long_window,
                                                   title=f"A股: {symbol} - 交互式信号分析")
                st.plotly_chart(kline_fig, use_container_width=True)

                st.subheader("💰 资金收益对冲曲线")
                equity_fig = plot_equity_curve(bt_results, title="策略资金 vs 基准资金")
                st.plotly_chart(equity_fig, use_container_width=True)