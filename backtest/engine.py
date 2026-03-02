import pandas as pd
import numpy as np
import plotly.graph_objects as go
from typing import Dict, Any, Tuple, List
from configs.settings import get_trading_config, get_backtest_config

trading_conf = get_trading_config()
bt_conf = get_backtest_config()


def run_backtest(
        df: pd.DataFrame,
        initial_capital: float,
        position_ratio: float,
        global_filters: Dict
) -> pd.DataFrame:
    # 🚀 从全局参数动态读取前端配置的交易成本
    filters = global_filters or {}
    tp = filters.get('tp', trading_conf.DEFAULT_TAKE_PROFIT)
    sl = filters.get('sl', trading_conf.DEFAULT_STOP_LOSS)
    slippage = filters.get('slippage', trading_conf.DEFAULT_SLIPPAGE)
    buy_fee = filters.get('buy_fee', trading_conf.BUY_FEE_RATE)
    sell_fee = filters.get('sell_fee', trading_conf.SELL_FEE_RATE)
    min_comm = filters.get('min_comm', trading_conf.MIN_COMMISSION)
    min_shares = filters.get('min_shares', trading_conf.MIN_SHARES_MULTIPLE)

    bt_df = df.copy()
    n = len(bt_df)

    # 🚀 获取真实的高开低收，解决跳空盲区
    closes = bt_df['收盘'].values
    opens = bt_df['开盘'].values if '开盘' in bt_df.columns else closes
    highs = bt_df['最高'].values if '最高' in bt_df.columns else closes
    lows = bt_df['最低'].values if '最低' in bt_df.columns else closes
    pos_diff_arr = bt_df['position_diff'].fillna(0).values if 'position_diff' in bt_df.columns else np.zeros(n)

    equity_arr = np.zeros(n)
    buy_price_arr = np.zeros(n)

    cash = initial_capital
    holdings = 0
    buy_price = 0.0
    trade_profits: List[float] = []
    sell_reasons = [''] * n

    for i in range(n):
        price = closes[i]
        open_p = opens[i]
        high_p = highs[i]
        low_p = lows[i]
        pos_diff = pos_diff_arr[i]

        buy_price_adj = price * (1 + slippage)
        force_sell = False
        sell_reason = ""
        execute_price = price

        if holdings > 0:
            # 🚀 止损检测：用盘中最低价 (Low) 而不是收盘价！
            unrealized_low = (low_p - buy_price) / buy_price
            unrealized_high = (high_p - buy_price) / buy_price

            if unrealized_low <= sl:
                force_sell = True
                # 防御机制：如果跳空低开直接击穿止损位，你只能绝望地按开盘价跑路
                sl_price = buy_price * (1 + sl)
                execute_price = min(open_p, sl_price)
                sell_reason = f"盘中触发止损 ({unrealized_low * 100:.1f}%)"
            elif unrealized_high >= tp:
                force_sell = True
                # 防御机制：如果跳空高开直接越过止盈，运气好按更好的开盘价卖出
                tp_price = buy_price * (1 + tp)
                execute_price = max(open_p, tp_price)
                sell_reason = f"盘中触发止盈 ({unrealized_high * 100:.1f}%)"
            elif pos_diff == -1:
                force_sell = True
                execute_price = price
                sell_reason = "策略平仓信号"

        if pos_diff == 1 and cash > 0 and holdings == 0:
            invest_amount = cash * position_ratio
            max_shares = int(invest_amount / buy_price_adj)
            shares_to_buy = (max_shares // min_shares) * min_shares

            if shares_to_buy > 0:
                trade_value = shares_to_buy * buy_price_adj
                commission = max(min_comm, trade_value * buy_fee)
                total_cost = trade_value + commission

                if cash >= total_cost:
                    cash -= total_cost
                    holdings = shares_to_buy
                    buy_price = buy_price_adj

        elif force_sell and holdings > 0:
            real_sell_price = execute_price * (1 - slippage)
            trade_value = holdings * real_sell_price
            commission = max(min_comm, trade_value * sell_fee)
            net_income = trade_value - commission

            profit_pct = (net_income - (holdings * buy_price)) / (holdings * buy_price)
            trade_profits.append(profit_pct)

            cash += net_income
            holdings = 0
            sell_reasons[i] = sell_reason

        equity_arr[i] = cash + holdings * price
        buy_price_arr[i] = buy_price

    bt_df['strategy_equity'] = equity_arr
    bt_df['sell_reason'] = sell_reasons

    # --- 基准计算 ---
    first_price = closes[0]
    bench_max_shares = int(initial_capital / first_price)
    bench_shares = (bench_max_shares // min_shares) * min_shares

    if bench_shares > 0:
        bench_cost = bench_shares * first_price
        bench_comm = max(min_comm, bench_cost * buy_fee)
        if initial_capital < bench_cost + bench_comm:
            bench_shares -= min_shares

        if bench_shares > 0:
            bench_cost = bench_shares * first_price
            bench_comm = max(min_comm, bench_cost * buy_fee)
            bench_cash = initial_capital - bench_cost - bench_comm
            bt_df['benchmark_equity'] = bench_cash + bench_shares * bt_df['收盘']
        else:
            bt_df['benchmark_equity'] = initial_capital
    else:
        bt_df['benchmark_equity'] = initial_capital

    # ==========================================
    # 安全计算统计指标
    # ==========================================
    bt_df['cum_max'] = bt_df['strategy_equity'].cummax()
    bt_df['drawdown'] = (bt_df['strategy_equity'] - bt_df['cum_max']) / bt_df['cum_max']

    daily_ret = bt_df['strategy_equity'].pct_change().fillna(0)
    std_ret = daily_ret.std()

    # 🚀 夏普比率修复：扣除无风险利率
    daily_rf = bt_conf.RISK_FREE_RATE / bt_conf.TRADING_DAYS_PER_YEAR
    excess_ret = daily_ret - daily_rf

    if pd.isna(std_ret) or std_ret == 0 or len(daily_ret) < 2:
        sharpe = 0.0
    else:
        sharpe = float((excess_ret.mean() / std_ret) * np.sqrt(bt_conf.TRADING_DAYS_PER_YEAR))
        if pd.isna(sharpe) or np.isinf(sharpe):
            sharpe = 0.0

    win_trades = [t for t in trade_profits if t > 0]
    loss_trades = [t for t in trade_profits if t <= 0]
    win_rate = (len(win_trades) / len(trade_profits) * 100) if trade_profits else 0.0

    avg_win = float(np.mean(win_trades)) if win_trades else 0.0
    avg_loss = float(abs(np.mean(loss_trades))) if loss_trades else 0.0

    # 防除零极限修复
    if avg_loss > 0:
        pl_ratio = avg_win / avg_loss
    else:
        pl_ratio = 99.99 if avg_win > 0 else 0.0

    max_dd = float(bt_df['drawdown'].min() * 100)
    if pd.isna(max_dd): max_dd = 0.0

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
        initial_capital: float,
        max_positions: int,
        global_filters: Dict,
        dynamic_sizing: bool = True
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    filters = global_filters or {}
    tp = filters.get('tp', trading_conf.DEFAULT_TAKE_PROFIT)
    sl = filters.get('sl', trading_conf.DEFAULT_STOP_LOSS)
    slippage = filters.get('slippage', trading_conf.DEFAULT_SLIPPAGE)
    buy_fee = filters.get('buy_fee', trading_conf.BUY_FEE_RATE)
    sell_fee = filters.get('sell_fee', trading_conf.SELL_FEE_RATE)
    min_comm = filters.get('min_comm', trading_conf.MIN_COMMISSION)
    min_shares = filters.get('min_shares', trading_conf.MIN_SHARES_MULTIPLE)


    all_dates = sorted(pd.to_datetime(list(next(iter(all_stocks_data.values())).index)))
    cash = initial_capital
    active_positions: Dict[str, Dict[str, Any]] = {}
    portfolio_value = []
    holdings_history = []
    trade_log = []

    for date in all_dates:
        # --- A. 卖出逻辑 (加入盘中跳空验证) ---
        symbols_to_remove = []
        for sym, pos in active_positions.items():
            df = all_stocks_data[sym]
            if date not in df.index:
                continue

            curr_price = df.loc[date, '收盘']
            open_price = df.loc[date, '开盘'] if '开盘' in df.columns else curr_price
            high_price = df.loc[date, '最高'] if '最高' in df.columns else curr_price
            low_price = df.loc[date, '最低'] if '最低' in df.columns else curr_price

            unrealized_low = (low_price - pos['buy_price']) / pos['buy_price']
            unrealized_high = (high_price - pos['buy_price']) / pos['buy_price']

            sell_trigger = False
            reason = ""
            execute_price = curr_price

            if unrealized_low <= sl:
                sell_trigger = True
                reason = "硬性止损(盘中)"
                execute_price = min(open_price, pos['buy_price'] * (1 + sl))
            elif unrealized_high >= tp:
                sell_trigger = True
                reason = "硬性止盈(盘中)"
                execute_price = max(open_price, pos['buy_price'] * (1 + tp))
            elif df.loc[date, 'position_diff'] == -1:
                sell_trigger = True
                reason = "策略平仓"

            if sell_trigger:
                sell_price_adj = execute_price * (1 - slippage)
                sell_val = pos['shares'] * sell_price_adj
                commission = max(min_comm, sell_val * sell_fee)
                cash += (sell_val - commission)
                trade_log.append({
                    '日期': date, '股票': sym, '动作': '🟢 卖出',
                    '成交价': execute_price, '股数': pos['shares'],
                    '金额': round(sell_val, 2), '原因': reason
                })
                symbols_to_remove.append(sym)

        for sym in symbols_to_remove:
            del active_positions[sym]

        # --- B. 动态买入逻辑 ---
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
                    buy_price_adj = buy_price * (1 + slippage)
                    shares = (pos_budget // buy_price_adj // min_shares) * min_shares

                    if shares > 0:
                        actual_cost = shares * buy_price_adj
                        comm = max(min_comm, actual_cost * buy_fee)
                        if cash >= (actual_cost + comm):
                            cash -= (actual_cost + comm)
                            active_positions[sym] = {'shares': shares, 'buy_price': buy_price_adj}
                            trade_log.append({
                                '日期': date, '股票': sym, '动作': '🔴 买入',
                                '成交价': buy_price, '股数': shares,
                                '金额': round(actual_cost, 2), '原因': '动态分仓'
                            })
                            if len(active_positions) >= max_positions:
                                break

        # --- C. 每日镜像记录 ---
        day_holdings_val = sum(
            [p['shares'] * all_stocks_data[s].loc[date, '收盘'] for s, p in active_positions.items()])
        for sym, pos in active_positions.items():
            holdings_history.append({
                'date': date, '股票': sym, '股数': pos['shares'],
                '价值': round(pos['shares'] * all_stocks_data[sym].loc[date, '收盘'], 2)
            })

        portfolio_value.append({
            'date': date, 'total_value': cash + day_holdings_val,
            'cash': round(cash, 2), 'holdings_count': len(active_positions)
        })

    res_df = pd.DataFrame(portfolio_value).set_index('date')
    details_df = pd.DataFrame(holdings_history)

    if not details_df.empty:
        details_df['占比'] = details_df.apply(
            lambda row: f"{(row['价值'] / res_df.loc[row['date'], 'total_value'] * 100):.2f}%", axis=1
        )
    return res_df, details_df, pd.DataFrame(trade_log)


def plot_equity_curve(bt_df: pd.DataFrame, title: str = "策略 vs 基准 净值曲线") -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=bt_df.index, y=bt_df['benchmark_equity'], name='基准 (一直持有)',
                             line=dict(color='gray', dash='dash')))
    fig.add_trace(
        go.Scatter(x=bt_df.index, y=bt_df['strategy_equity'], name='策略净值', line=dict(color='red', width=2)))
    fig.update_layout(title=title, template='plotly_white', hovermode='x unified')
    return fig