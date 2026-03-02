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
    filters = global_filters or {}
    tp = filters.get('tp', trading_conf.DEFAULT_TAKE_PROFIT)
    sl = filters.get('sl', trading_conf.DEFAULT_STOP_LOSS)
    slippage = filters.get('slippage', trading_conf.DEFAULT_SLIPPAGE)
    buy_fee = filters.get('buy_fee', trading_conf.BUY_FEE_RATE)
    sell_fee = filters.get('sell_fee', trading_conf.SELL_FEE_RATE)
    min_comm = filters.get('min_comm', trading_conf.MIN_COMMISSION)
    min_shares = filters.get('min_shares', trading_conf.MIN_SHARES_MULTIPLE)

    # 🚀 追踪止损参数
    use_trailing = filters.get('use_trailing', trading_conf.DEFAULT_USE_TRAILING_STOP)
    trail_act = filters.get('trail_act', trading_conf.DEFAULT_TRAILING_ACTIVATION)
    trail_rate = filters.get('trail_rate', trading_conf.DEFAULT_TRAILING_RATE)

    bt_df = df.copy()
    n = len(bt_df)

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
    highest_since_buy = 0.0  # 🚀 新增：建仓以来的最高价

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
            # 🚀 动态更新持仓期间的最高价
            if high_p > highest_since_buy:
                highest_since_buy = high_p

            unrealized_low = (low_p - buy_price) / buy_price
            unrealized_high = (high_p - buy_price) / buy_price
            max_profit_pct = (highest_since_buy - buy_price) / buy_price

            # 🚀 1. 首先判定追踪止损 (当盈利曾达标，且回撤破线)
            if use_trailing and max_profit_pct >= trail_act:
                trail_stop_price = highest_since_buy * (1 - trail_rate)
                if low_p <= trail_stop_price:
                    force_sell = True
                    execute_price = min(open_p, trail_stop_price)
                    sell_reason = f"追踪止损 (峰值回撤 {trail_rate * 100:.1f}%)"

            # 2. 如果未触发追踪，继续判定绝对止损、止盈或策略平仓
            if not force_sell:
                if unrealized_low <= sl:
                    force_sell = True
                    execute_price = min(open_p, buy_price * (1 + sl))
                    sell_reason = f"硬性止损 ({unrealized_low * 100:.1f}%)"
                elif unrealized_high >= tp:
                    force_sell = True
                    execute_price = max(open_p, buy_price * (1 + tp))
                    sell_reason = f"硬性止盈 ({unrealized_high * 100:.1f}%)"
                elif pos_diff == -1:
                    force_sell = True
                    execute_price = price
                    sell_reason = "策略平仓信号"

        # --- 买入 ---
        if pos_diff == 1 and cash > 0 and holdings == 0:
            max_shares = int((cash * position_ratio) / buy_price_adj)
            shares_to_buy = (max_shares // min_shares) * min_shares

            if shares_to_buy > 0:
                trade_value = shares_to_buy * buy_price_adj
                commission = max(min_comm, trade_value * buy_fee)
                if cash >= (trade_value + commission):
                    cash -= (trade_value + commission)
                    holdings = shares_to_buy
                    buy_price = buy_price_adj
                    highest_since_buy = buy_price_adj  # 初始化最高价

        # --- 卖出 ---
        elif force_sell and holdings > 0:
            sell_price_adj = execute_price * (1 - slippage)
            trade_value = holdings * sell_price_adj
            commission = max(min_comm, trade_value * sell_fee)
            net_income = trade_value - commission

            profit_pct = (net_income - (holdings * buy_price)) / (holdings * buy_price)
            trade_profits.append(profit_pct)

            cash += net_income
            holdings = 0
            highest_since_buy = 0.0  # 重置最高价
            sell_reasons[i] = sell_reason

        equity_arr[i] = cash + holdings * price
        buy_price_arr[i] = buy_price

    bt_df['strategy_equity'] = equity_arr
    bt_df['sell_reason'] = sell_reasons

    # --- 基准计算 ---
    first_price = closes[0]
    bench_shares = (int(initial_capital / first_price) // min_shares) * min_shares

    if bench_shares > 0:
        bench_cost = bench_shares * first_price
        bench_comm = max(min_comm, bench_cost * buy_fee)
        bt_df['benchmark_equity'] = initial_capital - bench_cost - bench_comm + bench_shares * bt_df['收盘']
    else:
        bt_df['benchmark_equity'] = initial_capital

    bt_df['cum_max'] = bt_df['strategy_equity'].cummax()
    bt_df['drawdown'] = (bt_df['strategy_equity'] - bt_df['cum_max']) / bt_df['cum_max']

    daily_ret = bt_df['strategy_equity'].pct_change().fillna(0)
    std_ret = daily_ret.std()

    daily_rf = bt_conf.RISK_FREE_RATE / bt_conf.TRADING_DAYS_PER_YEAR
    excess_ret = daily_ret - daily_rf

    sharpe = float((excess_ret.mean() / std_ret) * np.sqrt(bt_conf.TRADING_DAYS_PER_YEAR)) if std_ret > 0 and len(
        daily_ret) > 1 else 0.0

    win_trades = [t for t in trade_profits if t > 0]
    loss_trades = [t for t in trade_profits if t <= 0]
    win_rate = (len(win_trades) / len(trade_profits) * 100) if trade_profits else 0.0
    avg_win = float(np.mean(win_trades)) if win_trades else 0.0
    avg_loss = float(abs(np.mean(loss_trades))) if loss_trades else 0.0
    pl_ratio = avg_win / avg_loss if avg_loss > 0 else (99.99 if avg_win > 0 else 0.0)

    bt_df.attrs.update({
        'max_drawdown': round(float(bt_df['drawdown'].min() * 100) if not pd.isna(bt_df['drawdown'].min()) else 0.0, 2),
        'sharpe_ratio': round(sharpe if not pd.isna(sharpe) and not np.isinf(sharpe) else 0.0, 2),
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
        dynamic_sizing: bool = True,
        allocation_method: str = "等权资金模型"
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    filters = global_filters or {}
    tp = filters.get('tp', trading_conf.DEFAULT_TAKE_PROFIT)
    sl = filters.get('sl', trading_conf.DEFAULT_STOP_LOSS)
    slippage = filters.get('slippage', trading_conf.DEFAULT_SLIPPAGE)
    buy_fee = filters.get('buy_fee', trading_conf.BUY_FEE_RATE)
    sell_fee = filters.get('sell_fee', trading_conf.SELL_FEE_RATE)
    min_comm = filters.get('min_comm', trading_conf.MIN_COMMISSION)
    min_shares = filters.get('min_shares', trading_conf.MIN_SHARES_MULTIPLE)

    use_trailing = filters.get('use_trailing', trading_conf.DEFAULT_USE_TRAILING_STOP)
    trail_act = filters.get('trail_act', trading_conf.DEFAULT_TRAILING_ACTIVATION)
    trail_rate = filters.get('trail_rate', trading_conf.DEFAULT_TRAILING_RATE)

    all_dates = sorted(pd.to_datetime(list(next(iter(all_stocks_data.values())).index)))
    cash = initial_capital
    active_positions: Dict[str, Dict[str, Any]] = {}
    portfolio_value, holdings_history, trade_log = [], [], []

    for date in all_dates:
        # --- A. 卖出逻辑 ---
        symbols_to_remove = []
        for sym, pos in active_positions.items():
            df = all_stocks_data[sym]
            if date not in df.index: continue

            curr_price = df.loc[date, '收盘']
            open_price = df.loc[date, '开盘'] if '开盘' in df.columns else curr_price
            high_price = df.loc[date, '最高'] if '最高' in df.columns else curr_price
            low_price = df.loc[date, '最低'] if '最低' in df.columns else curr_price

            # 🚀 刷新该股的历史最高峰值
            if high_price > pos['highest_price']:
                pos['highest_price'] = high_price

            unrealized_low = (low_price - pos['buy_price']) / pos['buy_price']
            unrealized_high = (high_price - pos['buy_price']) / pos['buy_price']
            max_profit_pct = (pos['highest_price'] - pos['buy_price']) / pos['buy_price']

            sell_trigger, reason, execute_price = False, "", curr_price

            # 🚀 1. 组合视角的动态跟踪判定
            if use_trailing and max_profit_pct >= trail_act:
                trail_stop_price = pos['highest_price'] * (1 - trail_rate)
                if low_price <= trail_stop_price:
                    sell_trigger = True
                    reason = f"追踪止损(峰值回撤{trail_rate * 100:.0f}%)"
                    execute_price = min(open_price, trail_stop_price)

            # 2. 若未追踪平仓，则判定常规防线
            if not sell_trigger:
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
                sell_val = pos['shares'] * execute_price * (1 - slippage)
                cash += (sell_val - max(min_comm, sell_val * sell_fee))
                trade_log.append(
                    {'日期': date, '股票': sym, '动作': '🟢 卖出', '成交价': execute_price, '股数': pos['shares'],
                     '金额': round(sell_val, 2), '原因': reason})
                symbols_to_remove.append(sym)

        for sym in symbols_to_remove: del active_positions[sym]

        # --- B. 动态买入 ---
        cur_eq = cash + sum(p['shares'] * all_stocks_data[s].loc[date, '收盘'] for s, p in active_positions.items() if
                            date in all_stocks_data[s].index)

        if len(active_positions) < max_positions:
            pos_budget = (cur_eq / max_positions) if dynamic_sizing else (initial_capital / max_positions)

            for sym, df in all_stocks_data.items():
                if sym in active_positions or date not in df.index: continue
                if df.loc[date, 'position_diff'] == 1 and df.loc[date, 'final_signal'] == 1:
                    buy_price = df.loc[date, '收盘']
                    buy_price_adj = buy_price * (1 + slippage)

                    if allocation_method == "ATR 风险平价模型" and 'atr' in df.columns and not pd.isna(
                            df.loc[date, 'atr']) and df.loc[date, 'atr'] > 0:
                        risk_budget = cur_eq * 0.02
                        shares = min(risk_budget / df.loc[date, 'atr'], pos_budget / buy_price_adj)
                    else:
                        shares = pos_budget / buy_price_adj

                    shares = (int(shares) // min_shares) * min_shares

                    if shares > 0:
                        cost = shares * buy_price_adj
                        if cash >= (cost + max(min_comm, cost * buy_fee)):
                            cash -= (cost + max(min_comm, cost * buy_fee))
                            # 🚀 买入时初始化该股的最高价
                            active_positions[sym] = {'shares': shares, 'buy_price': buy_price_adj,
                                                     'highest_price': buy_price_adj}
                            trade_log.append(
                                {'日期': date, '股票': sym, '动作': '🔴 买入', '成交价': buy_price, '股数': shares,
                                 '金额': round(cost, 2), '原因': f'建仓 ({allocation_method})'})
                            if len(active_positions) >= max_positions: break

        # --- C. 日终核算 ---
        day_val = sum(p['shares'] * all_stocks_data[s].loc[date, '收盘'] for s, p in active_positions.items())
        for sym, pos in active_positions.items():
            holdings_history.append({'date': date, '股票': sym, '股数': pos['shares'],
                                     '价值': round(pos['shares'] * all_stocks_data[sym].loc[date, '收盘'], 2)})
        portfolio_value.append({'date': date, 'total_value': cash + day_val, 'cash': round(cash, 2),
                                'holdings_count': len(active_positions)})

    res_df = pd.DataFrame(portfolio_value).set_index('date')
    details_df = pd.DataFrame(holdings_history)
    if not details_df.empty:
        details_df['占比'] = details_df.apply(
            lambda row: f"{(row['价值'] / res_df.loc[row['date'], 'total_value'] * 100):.2f}%", axis=1)
    return res_df, details_df, pd.DataFrame(trade_log)


def plot_equity_curve(bt_df: pd.DataFrame, title: str = "策略 vs 基准 净值曲线") -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=bt_df.index, y=bt_df['benchmark_equity'], name='基准 (一直持有)',
                             line=dict(color='gray', dash='dash')))
    fig.add_trace(
        go.Scatter(x=bt_df.index, y=bt_df['strategy_equity'], name='策略净值', line=dict(color='red', width=2)))
    fig.update_layout(title=title, template='plotly_white', hovermode='x unified')
    return fig