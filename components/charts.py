# components/charts.py
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def plot_interactive_kline(df, short_window, long_window, title="交互式 K 线图"):
    """专门负责渲染 K 线和买卖信号的画图组件"""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.8, 0.2])

    fig.add_trace(
        go.Candlestick(x=df.index, open=df['开盘'], high=df['最高'], low=df['最低'], close=df['收盘'], name='K线',
                       increasing_line_color='red', decreasing_line_color='green'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_short'], mode='lines', name=f'{short_window}日均线',
                             line=dict(color='orange', width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_long'], mode='lines', name=f'{long_window}日均线',
                             line=dict(color='blue', width=1.5)), row=1, col=1)

    buy_signals = df[df['position_diff'] == 1.0]
    sell_signals = df[df['position_diff'] == -1.0]

    fig.add_trace(go.Scatter(x=buy_signals.index, y=buy_signals['最低'] * 0.98, mode='markers', name='买入',
                             marker=dict(symbol='triangle-up', color='red', size=14,
                                         line=dict(width=1, color='DarkSlateGrey'))), row=1, col=1)
    fig.add_trace(go.Scatter(x=sell_signals.index, y=sell_signals['最高'] * 1.02, mode='markers', name='卖出',
                             marker=dict(symbol='triangle-down', color='green', size=14,
                                         line=dict(width=1, color='DarkSlateGrey'))), row=1, col=1)

    colors = ['red' if row['收盘'] >= row['开盘'] else 'green' for index, row in df.iterrows()]
    fig.add_trace(go.Bar(x=df.index, y=df['成交量'], name='成交量', marker_color=colors), row=2, col=1)

    fig.update_layout(title=title, yaxis_title='价格 (元)', yaxis2_title='成交量', xaxis_rangeslider_visible=False,
                      hovermode='x unified', template='plotly_white', margin=dict(l=50, r=50, t=60, b=50))

    dt_all = pd.date_range(start=df.index[0], end=df.index[-1])
    dt_obs = [d.strftime("%Y-%m-%d") for d in df.index]
    dt_breaks = [d for d in dt_all.strftime("%Y-%m-%d").tolist() if not d in dt_obs]
    fig.update_xaxes(rangebreaks=[dict(values=dt_breaks)])

    return fig