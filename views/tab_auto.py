import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from utils.data_fetcher import get_daily_hfq_data
from backtest.optimizer import optimize_strategy, apply_advanced_filters
from backtest.engine import run_backtest, plot_equity_curve
from strategies.base import StrategyRegistry
from configs.settings import get_backtest_config

bt_conf = get_backtest_config()


def run_single_param_backtest(raw_data, strategy_type, param_dict, global_filters, initial_capital, pos_ratio):
    strategy = StrategyRegistry.get(strategy_type)
    strat_df = strategy.generate_signals(raw_data, **param_dict)

    index_data = get_daily_hfq_data(bt_conf.BENCHMARK_CODE, raw_data.index[0].strftime('%Y%m%d'),
                                    raw_data.index[-1].strftime('%Y%m%d')) if global_filters['use_index'] else None
    strat_df = apply_advanced_filters(strat_df, index_data, global_filters)

    if 'position_diff' not in strat_df.columns:
        strat_df['position_diff'] = strat_df['signal'].diff().fillna(0)
    strat_df['valid_buy'] = (strat_df['position_diff'] == 1) & strat_df['filter_pass']
    strat_df['valid_sell'] = (strat_df['position_diff'] == -1)

    strat_df['action'] = np.nan
    strat_df.loc[strat_df['valid_buy'], 'action'] = 1
    strat_df.loc[strat_df['valid_sell'], 'action'] = 0
    strat_df['final_signal'] = strat_df['action'].ffill().fillna(0)
    strat_df['position_diff'] = strat_df['final_signal'].diff().fillna(0)

    return run_backtest(strat_df, initial_capital, pos_ratio, global_filters)


def render_auto_tab(symbol, start_date, end_date, initial_capital, global_filters, strategy_type):
    st.markdown(f"### 🤖 {strategy_type} - 参数寻优与稳定性检验")

    strategy = StrategyRegistry.get(strategy_type)
    if not strategy:
        st.error("策略未注册！")
        return

    st.info(f"💡 **寻优目标**：{strategy.description}")

    with st.expander("🎯 自定义寻优搜索空间与步长", expanded=True):
        # 🚀 分离数值型(网格寻优轴)与布尔型(静态设置项)
        opt_params = {k: v for k, v in strategy.params.items() if not isinstance(v.default, bool)}
        bool_params = {k: v for k, v in strategy.params.items() if isinstance(v.default, bool)}

        opt_keys = list(opt_params.keys())[:2]
        if len(opt_keys) < 2:
            st.warning("该策略可调数值参数不足2个，无法进行二维网格寻优。")
            return

        col_p1, col_p2 = st.columns(2)
        grid_values = []

        for i, key in enumerate(opt_keys):
            p_def = opt_params[key]
            with (col_p1 if i == 0 else col_p2):
                desc = p_def.description or key
                def_min = p_def.min_val if p_def.min_val is not None else int(p_def.default * 0.5)
                def_max = p_def.max_val if p_def.max_val is not None else int(p_def.default * 2.0)

                if isinstance(p_def.default, float):
                    p_range = st.slider(f"{desc} 范围", float(def_min), float(def_max),
                                        (float(p_def.default * 0.8), float(p_def.default * 1.2)), key=f"a_r_{key}")
                    p_step = st.number_input(f"{desc} 步长", 0.01, 1.0, float(p_def.step), key=f"a_s_{key}")
                    grid_values.append(list(np.arange(p_range[0], p_range[1] + p_step * 0.1, p_step)))
                else:
                    p_range = st.slider(f"{desc} 范围", int(def_min), int(def_max),
                                        (int(p_def.default * 0.8), int(p_def.default * 1.2)), key=f"a_r_{key}")
                    p_step = st.number_input(f"{desc} 步长", 1, max(10, int((def_max - def_min) / 5)), int(p_def.step),
                                             key=f"a_s_{key}")
                    grid_values.append(list(range(p_range[0], p_range[1] + 1, p_step)))

        # 🚀 渲染静态策略开关，并通过“单元素列表”巧妙注入到网格空间中！
        if bool_params:
            st.divider()
            st.write("🛠️ **静态策略开关** (应用到所有寻优组合)")
            bool_cols = st.columns(len(bool_params))
            for i, (p_name, p_def) in enumerate(bool_params.items()):
                with bool_cols[i]:
                    val = st.toggle(p_def.description or p_name, value=p_def.default, key=f"a_{strategy_type}_{p_name}")
                    opt_keys.append(p_name)
                    grid_values.append([val])  # 注入到笛卡尔积中，不增加计算量

        total_comb = len(grid_values[0]) * len(grid_values[1])

    st.divider()
    st.subheader("🔬 稳定性体检：样本外盲测 (OOS)")
    enable_oos = st.toggle("🛡️ 开启多参数盲测排行榜 (检验前 10 名真实性)", value=False, key="a_oos_toggle")
    if enable_oos:
        train_ratio = st.slider("训练集占比", 0.5, 0.9, 0.7, 0.05, key="a_oos_ratio")

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        pos_ratio = st.number_input("寻优单次仓位", 0.1, 1.0, 1.0, 0.1, key="a_pos")
    with c2:
        st.markdown(
            f"<div style='margin-top: 32px;'>📊 预计扫描：<strong style='color:red;'>{total_comb}</strong> 个网格点</div>",
            unsafe_allow_html=True)
    with c3:
        st.write("");
        run_opt = st.button("🔥 开启暴力扫描", use_container_width=True, type="primary", key="a_run")

    if run_opt:
        raw_data = get_daily_hfq_data(symbol, start_date, end_date)
        if raw_data is None or raw_data.empty:
            st.error("❌ 无法获取数据")
            return

        if enable_oos:
            split_idx = int(len(raw_data) * train_ratio)
            train_raw = raw_data.iloc[:split_idx]
            test_raw = raw_data.iloc[split_idx:]
            st.warning(
                f"🪓 数据已切分！【训练集】至 {train_raw.index[-1].strftime('%Y-%m-%d')} | 【测试集】从 {test_raw.index[0].strftime('%Y-%m-%d')} 至今")
        else:
            train_raw = raw_data
            split_idx = 0

        with st.spinner('建立多进程计算池...'):
            progress_bar = st.progress(0, text="🚀 正在多进程扫描参数空间...")

            def update_progress(p):
                progress_bar.progress(p, text=f"扫描进度: {int(p * 100)}%")

            results_df, la, lb = optimize_strategy(
                train_raw, strategy_type, initial_capital, global_filters, pos_ratio,
                opt_keys, grid_values, start_date, end_date, progress_callback=update_progress
            )
            progress_bar.empty()

            if results_df is None or results_df.empty or '收益率 (%)' not in results_df.columns:
                st.error("❌ 参数寻优失败，未产生有效交易")
                return

            max_abs = results_df['收益率 (%)'].abs().max() or 1
            plot_df = results_df.pivot(index=lb, columns=la, values='收益率 (%)')
            fig = go.Figure(data=go.Heatmap(z=plot_df.values, x=plot_df.columns, y=plot_df.index, colorscale='RdYlGn_r',
                                            zmin=-max_abs, zmax=max_abs))
            fig.update_layout(title="训练集参数收益分布 (红区代表参数平原，越宽越稳)", xaxis_title=la, yaxis_title=lb)
            st.plotly_chart(fig, use_container_width=True)

            if enable_oos:
                st.subheader("📋 前 10 名参数 OOS 盲测排行榜")
                top_10 = results_df.sort_values('夏普比率', ascending=False).head(10).copy()
                oos_results = []
                for idx, row in top_10.iterrows():
                    param_dict = {opt_keys[0]: row[la], opt_keys[1]: row[lb]}
                    # 补充静态参数用于单点测试
                    for bk in bool_params:
                        param_dict[bk] = row.get(bk, bool_params[bk].default)

                    bt_test = run_single_param_backtest(raw_data, strategy_type, param_dict, global_filters,
                                                        initial_capital, pos_ratio)

                    test_part = bt_test.iloc[split_idx:]
                    if test_part.empty or len(test_part) < 2:
                        test_ret, test_sharpe = 0, 0
                    else:
                        test_ret = ((test_part['strategy_equity'].iloc[-1] / test_part['strategy_equity'].iloc[
                            0]) - 1) * 100
                        test_sharpe = test_part.attrs.get('sharpe_ratio', 0)

                    oos_results.append({
                        la: row[la], lb: row[lb],
                        "训练收益 (%)": row['收益率 (%)'], "盲测收益 (%)": round(test_ret, 2),
                        "盲测夏普": round(test_sharpe, 2),
                        "状态": "✅ 通过" if test_ret > 0 else "❌ 崩盘"
                    })

                st.dataframe(pd.DataFrame(oos_results).style.map(
                    lambda x: 'color: red' if x == '✅ 通过' else 'color: green' if x == '❌ 崩盘' else '',
                    subset=['状态']), use_container_width=True)
            else:
                st.subheader("📋 全局寻优排行榜")
                st.dataframe(results_df.sort_values('收益率 (%)', ascending=False), use_container_width=True)