import pandas as pd
import numpy as np
import plotly.graph_objects as go


def run_backtest(df, initial_capital=100000.0, position_ratio=1.0, take_profit=0.15, stop_loss=-0.08):
    bt_df = df.copy()

    buy_fee_rate = 0.0003  # 买入佣金 万三
    sell_fee_rate = 0.0008  # 卖出佣金+印花税 万八
    min_commission = 5.0  # 最低 5 元门槛

    cash = initial_capital
    holdings = 0
    strategy_equity = []
    trades = []
    buy_price = 0

    for date, row in bt_df.iterrows():
        pos_diff = row.get('position_diff', 0)
        price = row['收盘']

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

        # --- 真实买入逻辑 (核心修改：严格限制 100 股整数倍) ---
        if pos_diff == 1 and cash > 0 and holdings == 0:
            invest_amount = cash * position_ratio
            max_shares = int(invest_amount / price)

            # 【核心规则】：买入必须是100股的整数倍
            shares_to_buy = (max_shares // 100) * 100

            if shares_to_buy > 0:
                trade_value = shares_to_buy * price
                commission = max(min_commission, trade_value * buy_fee_rate)
                total_cost = trade_value + commission

                # 如果加上手续费超出了现金，就少买一手(100股)
                if cash < total_cost:
                    shares_to_buy -= 100
                    if shares_to_buy > 0:
                        trade_value = shares_to_buy * price
                        commission = max(min_commission, trade_value * buy_fee_rate)
                        total_cost = trade_value + commission

                if shares_to_buy > 0:
                    cash -= total_cost
                    holdings += shares_to_buy
                    buy_price = total_cost / shares_to_buy

                    # --- 真实卖出逻辑 ---
        elif force_sell and holdings > 0:
            trade_value = holdings * price
            commission = max(min_commission, trade_value * sell_fee_rate)
            net_income = trade_value - commission

            profit_pct = (net_income - (holdings * buy_price)) / (holdings * buy_price)
            trades.append(profit_pct)

            cash += net_income
            holdings = 0

            bt_df.at[date, 'position_diff'] = -1
            bt_df.at[date, 'sell_reason'] = sell_reason

        strategy_equity.append(cash + holdings * price)

    bt_df['strategy_equity'] = strategy_equity

    # --- 基准计算 (开局满仓模拟，同样受 100 股限制) ---
    first_price = bt_df['收盘'].iloc[0]
    bench_max_shares = int(initial_capital / first_price)
    bench_shares = (bench_max_shares // 100) * 100  # 【核心规则】：基准也必须是 100 股整数倍

    if bench_shares > 0:
        bench_cost = bench_shares * first_price
        bench_comm = max(min_commission, bench_cost * buy_fee_rate)

        # 扣除手续费后如果钱不够，少买 100 股
        if initial_capital < bench_cost + bench_comm:
            bench_shares -= 100

        if bench_shares > 0:
            bench_cost = bench_shares * first_price
            bench_comm = max(min_commission, bench_cost * buy_fee_rate)
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
    if pd.isna(std_ret) or std_ret == 0:
        sharpe = 0.0
    else:
        sharpe = float((daily_ret.mean() / std_ret) * np.sqrt(252))
        if pd.isna(sharpe) or np.isinf(sharpe):
            sharpe = 0.0

    win_trades = [t for t in trades if t > 0]
    loss_trades = [t for t in trades if t <= 0]

    win_rate = (len(win_trades) / len(trades) * 100) if trades else 0.0

    avg_win = float(np.mean(win_trades)) if win_trades else 0.0
    avg_loss = float(abs(np.mean(loss_trades))) if loss_trades else 0.0

    if avg_loss > 0:
        pl_ratio = avg_win / avg_loss
    elif avg_win > 0:
        pl_ratio = avg_win * 100.0
    else:
        pl_ratio = 0.0

    max_dd = float(bt_df['drawdown'].min() * 100)
    if pd.isna(max_dd): max_dd = 0.0

    bt_df.attrs.update({
        'max_drawdown': round(max_dd, 2),
        'sharpe_ratio': round(sharpe, 2),
        'win_rate': round(win_rate, 2),
        'pl_ratio': round(pl_ratio, 2),
        'trade_count': len(trades)
    })
    return bt_df


def run_portfolio_backtest(all_stocks_data, initial_capital=1000000.0, max_positions=5, take_profit=0.15,
                           stop_loss=-0.08, dynamic_sizing=True):
    # 提取所有股票共有的交易日并排序
    all_dates = sorted(pd.to_datetime(list(next(iter(all_stocks_data.values())).index)))

    cash = initial_capital
    active_positions = {}
    portfolio_value = []
    holdings_history = []
    trade_log = []

    for date in all_dates:
        # --- A. 卖出逻辑 ---
        symbols_to_remove = []
        for sym, pos in active_positions.items():
            df = all_stocks_data[sym]
            if date not in df.index: continue

            curr_price = df.loc[date, '收盘']
            unrealized_ret = (curr_price - pos['buy_price']) / pos['buy_price']

            sell_trigger = False
            reason = ""
            if unrealized_ret >= take_profit:
                sell_trigger = True;
                reason = "硬性止盈"
            elif unrealized_ret <= stop_loss:
                sell_trigger = True;
                reason = "硬性止损"
            elif df.loc[date, 'position_diff'] == -1:
                sell_trigger = True;
                reason = "策略平仓"

            if sell_trigger:
                sell_val = pos['shares'] * curr_price
                commission = max(5.0, sell_val * 0.0008)
                cash += (sell_val - commission)
                trade_log.append({
                    '日期': date, '股票': sym, '动作': '🔴 卖出',
                    '成交价': curr_price, '股数': pos['shares'],
                    '金额': round(sell_val, 2), '原因': reason
                })
                symbols_to_remove.append(sym)
        for sym in symbols_to_remove: del active_positions[sym]

        # --- B. 动态买入逻辑 (复利计算) ---
        current_holdings_val_temp = sum(
            [p['shares'] * all_stocks_data[s].loc[date, '收盘'] for s, p in active_positions.items() if
             date in all_stocks_data[s].index])
        current_total_equity = cash + current_holdings_val_temp

        if len(active_positions) < max_positions:
            pos_budget = (current_total_equity / max_positions) if dynamic_sizing else (initial_capital / max_positions)

            for sym, df in all_stocks_data.items():
                if sym in active_positions or date not in df.index: continue
                if df.loc[date, 'position_diff'] == 1 and df.loc[date, 'final_signal'] == 1:
                    buy_price = df.loc[date, '收盘']
                    shares = (pos_budget // buy_price // 100) * 100

                    if shares > 0:
                        actual_cost = shares * buy_price
                        comm = max(5.0, actual_cost * 0.0003)
                        if cash >= (actual_cost + comm):
                            cash -= (actual_cost + comm)
                            active_positions[sym] = {'shares': shares, 'buy_price': buy_price}
                            trade_log.append({
                                '日期': date, '股票': sym, '动作': '🟢 买入',
                                '成交价': buy_price, '股数': shares,
                                '金额': round(actual_cost, 2), '原因': '动态分仓'
                            })
                            if len(active_positions) >= max_positions: break

        # --- C. 每日镜像记录 ---
        day_holdings_val = 0
        for sym, pos in active_positions.items():
            p = all_stocks_data[sym].loc[date, '收盘']
            v = pos['shares'] * p
            day_holdings_val += v
            holdings_history.append({'date': date, '股票': sym, '股数': pos['shares'], '价值': round(v, 2)})

        total_val = cash + day_holdings_val
        portfolio_value.append({
            'date': date, 'total_value': total_val,
            'cash': round(cash, 2), 'holdings_count': len(active_positions)
        })

    res_df = pd.DataFrame(portfolio_value).set_index('date')
    details_df = pd.DataFrame(holdings_history)

    # 补算历史占比
    if not details_df.empty:
        details_df['占比'] = details_df.apply(
            lambda row: f"{(row['价值'] / res_df.loc[row['date'], 'total_value'] * 100):.2f}%", axis=1)

    return res_df, details_df, pd.DataFrame(trade_log)
def plot_equity_curve(bt_df, title="策略 vs 基准 净值曲线"):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=bt_df.index, y=bt_df['benchmark_equity'], name='基准(一直持有)',
                             line=dict(color='gray', dash='dash')))
    fig.add_trace(
        go.Scatter(x=bt_df.index, y=bt_df['strategy_equity'], name='策略净值', line=dict(color='red', width=2)))
    fig.update_layout(title=title, template='plotly_white', hovermode='x unified')
    return fig
