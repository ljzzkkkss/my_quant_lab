import pandas as pd
import numpy as np
import plotly.graph_objects as go
from typing import Dict, Any, Optional, Tuple, List
from configs.settings import get_trading_config
from configs.settings import get_backtest_config

# ========== 全局交易配置 ==========
trading_conf = get_trading_config()
bt_conf = get_backtest_config()

def run_backtest(
    df: pd.DataFrame,
    initial_capital: float = 1000000.0,
    position_ratio: float = trading_conf.DEFAULT_POSITION_RATIO,
    take_profit: float = trading_conf.DEFAULT_TAKE_PROFIT,
    stop_loss: float = trading_conf.DEFAULT_STOP_LOSS,
    slippage: float = trading_conf.DEFAULT_SLIPPAGE
) -> pd.DataFrame:
    """
    向量化回测引擎 - 支持滑点模拟

    参数:
        df: 包含 OHLCV 和 signal/position_diff 列的数据
        initial_capital: 初始资金
        position_ratio: 仓位比例
        take_profit: 止盈比例
        stop_loss: 止损比例
        slippage: 滑点比例 (默认 0.1%)

    返回:
        包含回测结果的 DataFrame
    """
    bt_df = df.copy()
    n = len(bt_df)

    prices = bt_df['收盘'].values

    # 预分配数组
    equity_arr = np.zeros(n)
    buy_price_arr = np.zeros(n)

    # 状态变量
    cash = initial_capital
    holdings = 0
    buy_price = 0.0

    # 记录交易用于统计
    trade_profits: List[float] = []
    sell_reasons = [''] * n

    pos_diff_arr = bt_df['position_diff'].fillna(0).values if 'position_diff' in bt_df.columns else np.zeros(n)

    # ========== 主循环 (保留必要的循环逻辑，因为交易有状态依赖) ==========
    # 注意：由于止盈止损依赖于持仓成本，完全向量化会导致逻辑复杂且难以维护
    # 这里使用优化的循环 + 向量化预处理结合

    for i in range(n):
        price = prices[i]
        pos_diff = pos_diff_arr[i]

        # 应用滑点：买入价上浮，卖出价下浮
        buy_price_adj = price * (1 + slippage)
        sell_price_adj = price * (1 - slippage)

        force_sell = False
        sell_reason = ""

        # --- 🛡️ 实战止盈止损判定 ---
        if holdings > 0:
            unrealized_pct = (price - buy_price) / buy_price

            if unrealized_pct <= stop_loss:
                force_sell = True
                sell_reason = f"触发止损 ({unrealized_pct * 100:.1f}%)"
            elif unrealized_pct >= take_profit:
                force_sell = True
                sell_reason = f"触发止盈 ({unrealized_pct * 100:.1f}%)"
            elif pos_diff == -1:
                force_sell = True
                sell_reason = "策略信号平仓"

        # --- 真实买入逻辑 (100 股整数倍 + 滑点) ---
        if pos_diff == 1 and cash > 0 and holdings == 0:
            invest_amount = cash * position_ratio
            max_shares = int(invest_amount / buy_price_adj)
            shares_to_buy = (max_shares // 100) * 100

            if shares_to_buy > 0:
                trade_value = shares_to_buy * buy_price_adj
                commission = max(trading_conf.MIN_COMMISSION, trade_value * trading_conf.BUY_FEE_RATE)
                total_cost = trade_value + commission

                if cash >= total_cost:
                    cash -= total_cost
                    holdings = shares_to_buy
                    buy_price = buy_price_adj  # 记录含滑点的成本价

        # --- 真实卖出逻辑 (含滑点) ---
        elif force_sell and holdings > 0:
            trade_value = holdings * sell_price_adj
            commission = max(trading_conf.MIN_COMMISSION, trade_value * trading_conf.SELL_FEE_RATE)
            net_income = trade_value - commission

            profit_pct = (net_income - (holdings * buy_price)) / (holdings * buy_price)
            trade_profits.append(profit_pct)

            cash += net_income
            holdings = 0
            sell_reasons[i] = sell_reason

        # 记录状态
        equity_arr[i] = cash + holdings * price  # 权益按中间价计算
        buy_price_arr[i] = buy_price

    # 批量赋值
    bt_df['strategy_equity'] = equity_arr
    bt_df['sell_reason'] = sell_reasons

    # --- 基准计算 (开局满仓模拟，同样受 100 股限制) ---
    first_price = bt_df['收盘'].iloc[0]
    bench_max_shares = int(initial_capital / first_price)
    bench_shares = (bench_max_shares // 100) * 100

    if bench_shares > 0:
        bench_cost = bench_shares * first_price
        bench_comm = max(trading_conf.MIN_COMMISSION, bench_cost * trading_conf.BUY_FEE_RATE)

        if initial_capital < bench_cost + bench_comm:
            bench_shares -= 100

        if bench_shares > 0:
            bench_cost = bench_shares * first_price
            bench_comm = max(trading_conf.MIN_COMMISSION, bench_cost * trading_conf.BUY_FEE_RATE)
            bench_cash = initial_capital - bench_cost - bench_comm
            bt_df['benchmark_equity'] = bench_cash + bench_shares * bt_df['收盘']
        else:
            bt_df['benchmark_equity'] = initial_capital
    else:
        bt_df['benchmark_equity'] = initial_capital

    # ==========================================
    # 🚨 安全计算统计指标 (拦截 NaN)
    # ==========================================
    bt_df['cum_max'] = bt_df['strategy_equity'].cummax()
    bt_df['drawdown'] = (bt_df['strategy_equity'] - bt_df['cum_max']) / bt_df['cum_max']

    daily_ret = bt_df['strategy_equity'].pct_change().fillna(0)
    std_ret = daily_ret.std()

    if pd.isna(std_ret) or std_ret == 0 or len(daily_ret) < 2:
        sharpe = 0.0
    else:
        sharpe = float((daily_ret.mean() / std_ret) * np.sqrt(bt_conf.TRADING_DAYS_PER_YEAR))
        if pd.isna(sharpe) or np.isinf(sharpe):
            sharpe = 0.0

    win_trades = [t for t in trade_profits if t > 0]
    loss_trades = [t for t in trade_profits if t <= 0]

    win_rate = (len(win_trades) / len(trade_profits) * 100) if trade_profits else 0.0

    avg_win = float(np.mean(win_trades)) if win_trades else 0.0
    avg_loss = float(abs(np.mean(loss_trades))) if loss_trades else 0.0

    if avg_loss > 0:
        pl_ratio = avg_win / avg_loss
    elif avg_win > 0:
        pl_ratio = avg_win * 100.0
    else:
        pl_ratio = 0.0

    max_dd = float(bt_df['drawdown'].min() * 100)
    if pd.isna(max_dd):
        max_dd = 0.0

    bt_df.attrs.update({
        'max_drawdown': round(max_dd, 2),
        'sharpe_ratio': round(sharpe, 2),
        'win_rate': round(win_rate, 2),
        'pl_ratio': round(pl_ratio, 2),
        'trade_count': len(trade_profits)
    })
    return bt_df


def run_portfolio_backtest(
    all_stocks_data: Dict[str, pd.DataFrame],
    initial_capital: float = 1000000.0,
    max_positions: int = 5.0,
    take_profit: float = trading_conf.DEFAULT_TAKE_PROFIT,
    stop_loss: float = trading_conf.DEFAULT_STOP_LOSS,
    dynamic_sizing: bool = True,
    slippage: float = trading_conf.DEFAULT_SLIPPAGE
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    组合回测引擎 - 支持多股轮动

    参数:
        all_stocks_data: {股票代码：DataFrame} 字典
        initial_capital: 初始资金
        max_positions: 最大持仓数
        take_profit: 止盈比例
        stop_loss: 止损比例
        dynamic_sizing: 是否动态调整仓位（复利）
        slippage: 滑点比例

    返回:
        (净值曲线 DataFrame, 持仓明细 DataFrame, 交易记录 DataFrame)
    """
    all_dates = sorted(pd.to_datetime(list(next(iter(all_stocks_data.values())).index)))

    cash = initial_capital
    active_positions: Dict[str, Dict[str, Any]] = {}
    portfolio_value = []
    holdings_history = []
    trade_log = []

    for date in all_dates:
        # --- A. 卖出逻辑 ---
        symbols_to_remove = []
        for sym, pos in active_positions.items():
            df = all_stocks_data[sym]
            if date not in df.index:
                continue

            curr_price = df.loc[date, '收盘']
            unrealized_ret = (curr_price - pos['buy_price']) / pos['buy_price']

            sell_trigger = False
            reason = ""
            if unrealized_ret >= take_profit:
                sell_trigger = True
                reason = "硬性止盈"
            elif unrealized_ret <= stop_loss:
                sell_trigger = True
                reason = "硬性止损"
            elif df.loc[date, 'position_diff'] == -1:
                sell_trigger = True
                reason = "策略平仓"

            if sell_trigger:
                # 应用滑点
                sell_price_adj = curr_price * (1 - slippage)
                sell_val = pos['shares'] * sell_price_adj
                commission = max(trading_conf.MIN_COMMISSION, sell_val * trading_conf.SELL_FEE_RATE)
                cash += (sell_val - commission)
                trade_log.append({
                    '日期': date,
                    '股票': sym,
                    '动作': '🔴 卖出',
                    '成交价': curr_price,
                    '股数': pos['shares'],
                    '金额': round(sell_val, 2),
                    '原因': reason
                })
                symbols_to_remove.append(sym)

        for sym in symbols_to_remove:
            del active_positions[sym]

        # --- B. 动态买入逻辑 (复利计算) ---
        current_holdings_val_temp = sum(
            [p['shares'] * all_stocks_data[s].loc[date, '收盘'] for s, p in active_positions.items()
             if date in all_stocks_data[s].index]
        )
        current_total_equity = cash + current_holdings_val_temp

        if len(active_positions) < max_positions:
            pos_budget = (current_total_equity / max_positions) if dynamic_sizing else (initial_capital / max_positions)

            for sym, df in all_stocks_data.items():
                if sym in active_positions or date not in df.index:
                    continue
                if df.loc[date, 'position_diff'] == 1 and df.loc[date, 'final_signal'] == 1:
                    buy_price = df.loc[date, '收盘']
                    # 应用滑点
                    buy_price_adj = buy_price * (1 + slippage)
                    shares = (pos_budget // buy_price_adj // 100) * 100

                    if shares > 0:
                        actual_cost = shares * buy_price_adj
                        comm = max(trading_conf.MIN_COMMISSION, actual_cost * trading_conf.BUY_FEE_RATE)
                        if cash >= (actual_cost + comm):
                            cash -= (actual_cost + comm)
                            active_positions[sym] = {'shares': shares, 'buy_price': buy_price_adj}
                            trade_log.append({
                                '日期': date,
                                '股票': sym,
                                '动作': '🟢 买入',
                                '成交价': buy_price,
                                '股数': shares,
                                '金额': round(actual_cost, 2),
                                '原因': '动态分仓'
                            })
                            if len(active_positions) >= max_positions:
                                break

        # --- C. 每日镜像记录 ---
        day_holdings_val = 0
        for sym, pos in active_positions.items():
            p = all_stocks_data[sym].loc[date, '收盘']
            v = pos['shares'] * p
            day_holdings_val += v
            holdings_history.append({
                'date': date,
                '股票': sym,
                '股数': pos['shares'],
                '价值': round(v, 2)
            })

        total_val = cash + day_holdings_val
        portfolio_value.append({
            'date': date,
            'total_value': total_val,
            'cash': round(cash, 2),
            'holdings_count': len(active_positions)
        })

    res_df = pd.DataFrame(portfolio_value).set_index('date')
    details_df = pd.DataFrame(holdings_history)

    # 补算历史占比
    if not details_df.empty:
        details_df['占比'] = details_df.apply(
            lambda row: f"{(row['价值'] / res_df.loc[row['date'], 'total_value'] * 100):.2f}%", axis=1
        )

    return res_df, details_df, pd.DataFrame(trade_log)


def plot_equity_curve(bt_df: pd.DataFrame, title: str = "策略 vs 基准 净值曲线") -> go.Figure:
    """绘制净值曲线对比图"""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=bt_df.index,
        y=bt_df['benchmark_equity'],
        name='基准 (一直持有)',
        line=dict(color='gray', dash='dash')
    ))
    fig.add_trace(go.Scatter(
        x=bt_df.index,
        y=bt_df['strategy_equity'],
        name='策略净值',
        line=dict(color='red', width=2)
    ))
    fig.update_layout(
        title=title,
        template='plotly_white',
        hovermode='x unified'
    )
    return fig
