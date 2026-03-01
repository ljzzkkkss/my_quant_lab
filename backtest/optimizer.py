import pandas as pd
import streamlit as st
import numpy as np
from strategies.double_ma import apply_double_ma_strategy
from strategies.bollinger_bands import apply_bollinger_strategy
from backtest.engine import run_backtest
from utils.data_fetcher import get_daily_hfq_data


def apply_advanced_filters(df, index_df, filters):
    """
    内部过滤引擎：将基础信号与高级维度融合
    """
    # 1. 计算 RSI (14日)
    delta = df['收盘'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # 2. 计算成交量放大倍数 (量比)
    df['vol_ma5'] = df['成交量'].rolling(5).mean()
    df['volume_ratio'] = df['成交量'] / df['vol_ma5'].shift(1)

    # 3. 计算均线斜率 (以20日线为例)
    ma20 = df['收盘'].rolling(20).mean()
    df['slope'] = (ma20 - ma20.shift(3)) / ma20.shift(3) * 100

    # 4. 大盘滤镜状态
    df['index_ok'] = True
    if filters.get('use_index') and index_df is not None:
        # 对齐索引，判断大盘是否在20日均线上方
        idx_ma20 = index_df['收盘'].rolling(20).mean()
        index_status = (index_df['收盘'] > idx_ma20)
        df['index_ok'] = index_status.reindex(df.index, method='ffill').fillna(False)

    # 综合判定：所有过滤器必须同时通过
    df['filter_pass'] = (
            (df['volume_ratio'] >= filters.get('vol_ratio', 0)) &
            (df['rsi'] <= filters.get('rsi_limit', 100)) &
            (df['slope'] >= filters.get('slope_min', -999)) &
            (df['index_ok'] == True)
    )
    return df


def optimize_strategy(raw_data, strategy_type, initial_capital, global_filters, position_ratio, p1_range, p2_range,
                      start_date, end_date):
    """
    全量寻优引擎
    """
    results = []

    # 0. 获取大盘择时数据 (沪深300)
    index_data = None
    if global_filters.get('use_index'):
        index_data = get_daily_hfq_data("000300", start_date, end_date)

    # 1. 构建参数网格
    if strategy_type == "双均线动能策略":
        param_grid = [(s, l) for s in range(p1_range[0], p1_range[1] + 1, p1_range[2])
                      for l in range(p2_range[0], p2_range[1] + 1, p2_range[2]) if s < l]
        label_a, label_b = "短期均线", "长期均线"
    else:
        std_steps = np.arange(p2_range[0], p2_range[1] + 0.01, p2_range[2])
        param_grid = [(w, round(float(s), 2)) for w in range(p1_range[0], p1_range[1] + 1, p1_range[2])
                      for s in std_steps]
        label_a, label_b = "计算周期", "标准差倍数"

    if not param_grid:
        return None, None, None

    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(param_grid)

    for i, (v1, v2) in enumerate(param_grid):
        status_text.text(f"🚀 正在扫描第 {i + 1}/{total} 组参数...")

        # 2. 计算基础信号
        if strategy_type == "双均线动能策略":
            strat_df = apply_double_ma_strategy(raw_data, v1, v2, global_filters.get('use_macd'))
        else:
            strat_df = apply_bollinger_strategy(raw_data, v1, v2)

        # 3. 应用五维高级过滤
        strat_df = apply_advanced_filters(strat_df, index_data, global_filters)

        # 4. 融合信号：过滤不通过则不准持仓 (强制设为0)
        strat_df['final_signal'] = np.where(strat_df['filter_pass'], strat_df['signal'], 0)
        # 重新计算仓位变化以适应过滤后的信号
        strat_df['position_diff'] = strat_df['final_signal'].diff()

        # 5. 执行回测
        bt_results = run_backtest(strat_df, initial_capital, position_ratio)

        # 6. 收集数据
        results.append({
            label_a: v1,
            label_b: v2,
            '收益率(%)': round((bt_results['strategy_equity'].iloc[-1] / initial_capital - 1) * 100, 2),
            '最大回撤(%)': round(bt_results.attrs.get('max_drawdown', 0), 2),
            '夏普比率': round(bt_results.attrs.get('sharpe_ratio', 0), 2),
            '胜率(%)': round(bt_results.attrs.get('win_rate', 0), 2),
            '盈亏比': round(bt_results.attrs.get('pl_ratio', 0), 2)
        })

        progress_bar.progress((i + 1) / total)

    progress_bar.empty()
    status_text.empty()

    return pd.DataFrame(results), label_a, label_b