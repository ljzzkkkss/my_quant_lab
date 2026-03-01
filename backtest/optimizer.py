import pandas as pd
import streamlit as st
import numpy as np
from strategies.double_ma import apply_double_ma_strategy
from strategies.bollinger_bands import apply_bollinger_strategy
from strategies.rsi_reversal import apply_rsi_strategy
from strategies.macd_strategy import apply_macd_strategy
from strategies.kdj_strategy import apply_kdj_strategy
from backtest.engine import run_backtest
from utils.data_fetcher import get_daily_hfq_data

def apply_advanced_filters(df, index_df, filters):
    # 保持高级过滤逻辑不变
    delta = df['收盘'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    df['vol_ma5'] = df['成交量'].rolling(5).mean()
    df['volume_ratio'] = df['成交量'] / df['vol_ma5'].shift(1)

    ma20 = df['收盘'].rolling(20).mean()
    df['slope'] = (ma20 - ma20.shift(3)) / ma20.shift(3) * 100

    df['index_ok'] = True
    if filters.get('use_index') and index_df is not None:
        idx_ma20 = index_df['收盘'].rolling(20).mean()
        index_status = (index_df['收盘'] > idx_ma20)
        df['index_ok'] = index_status.reindex(df.index, method='ffill').fillna(False)

    df['filter_pass'] = (
            (df['volume_ratio'] >= filters.get('vol_ratio', 0)) &
            (df['rsi'] <= filters.get('rsi_limit', 100)) &
            (df['slope'] >= filters.get('slope_min', -999)) &
            (df['index_ok'] == True)
    )
    return df

def optimize_strategy(raw_data, strategy_type, initial_capital, global_filters, position_ratio, p1_range, p2_range, start_date, end_date):
    results = []

    index_data = None
    if global_filters.get('use_index'):
        index_data = get_daily_hfq_data("510300", start_date, end_date)

    # 1. 动态构建所有策略的网格
    if strategy_type == "双均线动能策略":
        param_grid = [(s, l) for s in range(p1_range[0], p1_range[1] + 1, p1_range[2]) for l in range(p2_range[0], p2_range[1] + 1, p2_range[2]) if s < l]
        la, lb = "短期均线", "长期均线"
    elif strategy_type == "布林带突破策略":
        param_grid = [(w, round(float(s), 2)) for w in range(p1_range[0], p1_range[1] + 1, p1_range[2]) for s in np.arange(p2_range[0], p2_range[1] + 0.01, p2_range[2])]
        la, lb = "计算周期", "标准差倍数"
    elif strategy_type == "RSI极值反转策略":
        param_grid = [(lower, upper) for lower in range(p1_range[0], p1_range[1] + 1, p1_range[2]) for upper in range(p2_range[0], p2_range[1] + 1, p2_range[2]) if lower < upper]
        la, lb = "抄底阈值", "逃顶阈值"
    elif strategy_type == "MACD趋势策略":
        param_grid = [(fast, slow) for fast in range(p1_range[0], p1_range[1] + 1, p1_range[2]) for slow in range(p2_range[0], p2_range[1] + 1, p2_range[2]) if fast < slow]
        la, lb = "快线周期", "慢线周期"
    elif strategy_type == "KDJ震荡策略":
        param_grid = [(buy, sell) for buy in range(p1_range[0], p1_range[1] + 1, p1_range[2]) for sell in range(p2_range[0], p2_range[1] + 1, p2_range[2]) if buy < sell]
        la, lb = "超卖买入线", "超买卖出线"
    else: return None, None, None

    if not param_grid: return None, None, None

    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(param_grid)

    for i, (v1, v2) in enumerate(param_grid):
        status_text.text(f"🚀 正在扫描第 {i + 1}/{total} 组参数...")

        # 2. 补全调用分支逻辑
        if strategy_type == "双均线动能策略": strat_df = apply_double_ma_strategy(raw_data, v1, v2, global_filters.get('use_macd'))
        elif strategy_type == "布林带突破策略": strat_df = apply_bollinger_strategy(raw_data, v1, v2)
        elif strategy_type == "RSI极值反转策略": strat_df = apply_rsi_strategy(raw_data, v1, v2)
        elif strategy_type == "MACD趋势策略": strat_df = apply_macd_strategy(raw_data, v1, v2)
        elif strategy_type == "KDJ震荡策略": strat_df = apply_kdj_strategy(raw_data, v1, v2)

        strat_df = apply_advanced_filters(strat_df, index_data, global_filters)
        strat_df['final_signal'] = np.where(strat_df['filter_pass'], strat_df['signal'], 0)
        strat_df['position_diff'] = strat_df['final_signal'].diff().fillna(0)

        bt_results = run_backtest(strat_df, initial_capital, position_ratio, take_profit=global_filters.get('tp', 0.15), stop_loss=global_filters.get('sl', -0.08))

        results.append({
            la: v1, lb: v2,
            '收益率(%)': round((bt_results['strategy_equity'].iloc[-1] / initial_capital - 1) * 100, 2),
            '最大回撤(%)': bt_results.attrs.get('max_drawdown', 0),
            '夏普比率': bt_results.attrs.get('sharpe_ratio', 0),
            '胜率(%)': bt_results.attrs.get('win_rate', 0),
            '盈亏比': bt_results.attrs.get('pl_ratio', 0)
        })
        progress_bar.progress((i + 1) / total)

    progress_bar.empty(); status_text.empty()
    return pd.DataFrame(results).fillna(0), la, lb