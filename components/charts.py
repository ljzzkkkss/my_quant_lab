import plotly.graph_objects as go


def plot_interactive_kline(df, short_window=5, long_window=20, title="K线信号解析"):
    fig = go.Figure()

    # 绘制基础 K 线
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['开盘'], high=df['最高'], low=df['最低'], close=df['收盘'], name="K线"
    ))

    # 动态匹配并绘制策略指标线 (有什么画什么，防报错)
    if 'SMA_short' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_short'], mode='lines', name='短期均线',
                                 line=dict(color='orange', width=1.5)))
    if 'SMA_long' in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df['SMA_long'], mode='lines', name='长期均线', line=dict(color='blue', width=1.5)))
    if 'Upper' in df.columns and 'Lower' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['Upper'], mode='lines', name='布林上轨',
                                 line=dict(color='rgba(255,0,0,0.5)', dash='dot')))
        fig.add_trace(go.Scatter(x=df.index, y=df['Lower'], mode='lines', name='布林下轨',
                                 line=dict(color='rgba(0,128,0,0.5)', dash='dot')))

    # 绘制买卖点
    buy_signals = df[df['position_diff'] > 0]
    sell_signals = df[df['position_diff'] < 0]

    if not buy_signals.empty:
        fig.add_trace(go.Scatter(
            x=buy_signals.index, y=buy_signals['最低'] * 0.95, mode='markers',
            marker=dict(symbol='triangle-up', size=12, color='red'), name='建立仓位'
        ))
    if not sell_signals.empty:
        fig.add_trace(go.Scatter(
            x=sell_signals.index, y=sell_signals['最高'] * 1.05, mode='markers',
            marker=dict(symbol='triangle-down', size=12, color='green'), name='清仓出局'
        ))

    fig.update_layout(title=title, template='plotly_white', xaxis_rangeslider_visible=False, hovermode='x unified')
    return fig